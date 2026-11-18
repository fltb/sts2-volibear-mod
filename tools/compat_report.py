#!/usr/bin/env python3
"""Explain compatibility failures from a complete startup log or one isolated boot.

Boots the installed game once with the mod present and reports: version gate, mod
initialization, content registration, and every patch-install failure with the module
label the mod prints (e.g. "Steam patch failed: attack-machine"). Foreign patch
failures after Volibear's LOAD_OK are failures too. No mod-name allow/deny list is
used. A successful initialization check is not gameplay or multiplayer acceptance.
Declared unavailable capabilities produce a degraded report even when all required
startup markers are present; they are not counted as patch-install failures.
Unknown capability bindings keep the result inconclusive until confirmed.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTABLES = ('SlayTheSpire2', 'SlayTheSpire2.exe', 'SlayTheSpire2.x86_64')
FAILURE_PATTERN = re.compile(
    r'COMPAT_FAIL|Exception thrown (?:when calling mod initializer|while loading mod)'
    r'|depends on mods which have not been loaded'
    r'|failed to (?:apply|install|load|remove) (?:\w+\s+)?(?:patch|mod)\b'
    r'|\[(?:critical|optional)\].*?(?:\bfailed\b|✗)'
    r'|\b(?:critical |optional |dynamic )?patch(?:\(es\)|es)? (?:have )?failed\b'
    r'|\b(?:signature|field|callsite|anchor)\s+(?:(?:has|was|is)\s+)?(?:changed|missing|drift(?:ed)?|not found)\b'
    r'|\b(?:MissingMethodException|TypeLoadException|ReflectionTypeLoadException|HarmonyException)\b'
    r'|\b(?:native|Steam|Volibear)[^\r\n]*(?:failed:|\bdrift\b|is not async|pin missing|Ambiguous match)',
    re.IGNORECASE,
)
DETAIL_PATTERN = re.compile(r'(?:^|\s)(?:Description:|Error:|Exception:|Owner:|Target:|Reason:|--->|at\s|System\.\w*Exception|'
                            r'HarmonyLib\.\w*Exception|--- End of)', re.IGNORECASE)
SUMMARY_FAILURE_PATTERN = re.compile(r'patch application complete:.*?\b([1-9]\d*) failed\b', re.IGNORECASE)
ZERO_FAILURE_PATTERN = re.compile(r'\b(?:0(?:\s+of\s+\d+)?|no)\s+(?:critical |optional |dynamic )?'
                                  r'patch(?:\(es\)|es)?\s+(?:have )?failed\b', re.IGNORECASE)


def failure_details(log: str) -> list[dict]:
    """Keep the cause and target, including multiline third-party failure reports.

    Successful foreign patches sharing a target are not errors. Neither a framework
    name nor words such as "changed" in an ordinary state log imply incompatibility.
    """
    failures = []
    seen = set()
    consumed = set()
    lines = re.sub(r'\x1b\[[0-9;]*m', '', log).splitlines()
    scan_error_details = set()
    for index, line in enumerate(lines):
        if 'COMPAT_SCAN_ERROR' not in line:
            continue
        scan_error_details.add(index)
        for following in range(index + 1, len(lines)):
            if not lines[following].strip() or not DETAIL_PATTERN.search(lines[following]):
                break
            scan_error_details.add(following)
    for index, line in enumerate(lines):
        if index in scan_error_details or index in consumed or 'COMPAT_SHARED ' in line or 'COMPAT_SCAN ' in line:
            continue
        candidate = ZERO_FAILURE_PATTERN.sub('', line)
        if not (FAILURE_PATTERN.search(candidate) or SUMMARY_FAILURE_PATTERN.search(candidate)):
            continue
        header = line.strip()
        # Godot may print the same COMPAT_FAIL via both PushError and Print.
        key = header[header.index('COMPAT_FAIL'):] if 'COMPAT_FAIL' in header else header
        if key in seen:
            continue
        seen.add(key)
        context = [header]
        for following in range(index + 1, min(index + 25, len(lines))):
            detail = lines[following]
            if not detail.strip() or not DETAIL_PATTERN.search(detail):
                break
            context.append(detail.strip())
            consumed.add(following)
        text = '\n'.join(context)
        target = re.search(r'target=(.*?);\s*owner=', text)
        owner = re.search(r'(?:^|;\s*)owner=([^;\r\n]+)', text)
        peers = re.search(r'existing_transpilers=\[(.*?)\]', text)
        if target is None:
            target = re.search(r'\bTarget:\s*([^\r\n]+)', text, re.IGNORECASE)
        if owner is None:
            owner = re.search(r'\bOwner:\s*([^\r\n]+)', text, re.IGNORECASE)
        failures.append({
            'summary': header,
            'target_method': target.group(1) if target else None,
            'patch_owner': owner.group(1) if owner else None,
            'existing_transpilers': peers.group(1) if peers else None,
            'details': text,
        })
    return failures


def find_executable(game: Path) -> Path:
    for name in EXECUTABLES:
        path = game / name
        if path.is_file():
            return path
    raise SystemExit(f'No game executable under {game}')


def read_capabilities(record: dict) -> list[dict]:
    """Validate one atomic capability snapshot without inferring undeclared support."""
    capabilities = record.get('capabilities', [])
    if not isinstance(capabilities, list):
        raise ValueError('capabilities must be an array')
    seen = set()
    for capability in capabilities:
        if not isinstance(capability, dict) or any(
                not isinstance(capability.get(key), str) or not capability[key].strip()
                for key in ('capability', 'target', 'reason', 'impact')):
            raise ValueError('invalid capability assessment; capability, target, reason and impact are required')
        if capability.get('status') not in ('available', 'unavailable', 'unknown'):
            raise ValueError('invalid capability status')
        if capability['capability'] in seen:
            raise ValueError('duplicate capability assessment: ' + capability['capability'])
        seen.add(capability['capability'])
    return capabilities


def run(game: Path, log_path: Path, timeout: int, display: str, audio: str) -> str:
    (ROOT / '.local/tmp').mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='volibear-compat-', dir=str(ROOT / '.local/tmp')))
    env = {k: v for k, v in os.environ.items() if not k.startswith(('STEAM_', 'XDG_', 'HOME'))}
    env.update(HOME=str(work), XDG_DATA_HOME=str(work / 'data'), XDG_CONFIG_HOME=str(work / 'config'),
               XDG_CACHE_HOME=str(work / 'cache'), VOLIBEAR_COMPAT_DIAG='1')
    # The mods warning needs a previously accepted profile; reuse the isolated one when present.
    accepted = ROOT / '.local/tmp/vbprofile-pbe/data/SlayTheSpire2'
    if accepted.is_dir():
        shutil.copytree(accepted, work / 'data/SlayTheSpire2', dirs_exist_ok=True)
    command = [str(find_executable(game)), '--force-steam=off', '--quit-after', '2600',
               '--log-file', str(log_path.resolve()), '--display-driver', display,
               '--rendering-method', 'gl_compatibility', '--windowed', '--resolution', '1280x720',
               '--audio-driver', audio]
    try:
        completed = subprocess.run(command, env=env, timeout=timeout, capture_output=True, text=True)
        return (log_path.read_text(encoding='utf-8', errors='replace')
                if log_path.is_file() else completed.stdout + completed.stderr)
    except subprocess.TimeoutExpired:
        return log_path.read_text(encoding='utf-8', errors='replace') if log_path.is_file() else ''
    finally:
        shutil.rmtree(work, ignore_errors=True)


def report(log: str) -> dict:
    # A Godot banner is a process boundary. Without one, multiple Volibear starts
    # cannot safely be separated: an old LOAD_OK must not complete a later boot.
    boots = list(re.finditer(r'(?m)^Godot Engine v\d[^\r\n]*', log))
    discarded_boots = max(0, len(boots) - 1)
    if boots:
        log = log[boots[-1].start():]
    ambiguous_sessions = len(re.findall(r'\[Volibear\] BUILD_GATE ', log)) > 1
    def first(pattern):
        match = re.search(pattern, log)
        return match.group(0).strip() if match else None

    gate = first(r'\[Volibear\] BUILD_GATE [^\r\n]*')
    load = first(r'\[Volibear\] LOAD_OK [^\r\n]*')
    content = first(r'\[Volibear\] CONTENT_OK [^\r\n]*')
    details = failure_details(log)
    errors = [failure['summary'] for failure in details]
    summary = re.search(r'COMPAT_SUMMARY failures=(\d+)', log)
    channel = re.search(r'channel=([^\s]+)', gate or '')
    target = re.search(r'target=([^\s]+)', gate or '')
    failure_count = max(int(summary.group(1)) if summary else 0, len(errors))
    shared = []
    pending_shared = []
    scan = None
    capabilities = []
    metadata_errors = []
    for line in log.splitlines():
        if 'COMPAT_SCAN_ERROR' in line:
            metadata_errors.append(line.strip())
        for marker in ('COMPAT_SHARED ', 'COMPAT_SCAN '):
            if marker not in line:
                continue
            try:
                record = json.loads(line.split(marker, 1)[1])
                if not isinstance(record, dict):
                    raise ValueError('expected JSON object')
                if marker == 'COMPAT_SHARED ':
                    if record.get('status') != 'shared_unverified' or not isinstance(record.get('target'), str):
                        raise ValueError('invalid shared-target metadata')
                    pending_shared.append(record)
                else:
                    if record.get('status') != 'metadata_only' or any(
                            type(record.get(key)) is not int or record[key] < 0
                            for key in ('scanned_targets', 'own_targets', 'shared_targets')):
                        raise ValueError('invalid metadata summary')
                    if record['shared_targets'] != len(pending_shared):
                        raise ValueError('shared-target records are incomplete')
                    assessed = read_capabilities(record)
                    shared = pending_shared
                    pending_shared = []
                    scan = record
                    capabilities = assessed
            except (ValueError, TypeError) as error:
                metadata_errors.append(marker.strip() + ': ' + str(error))
    if pending_shared:
        shared.extend(pending_shared)
        metadata_errors.append('COMPAT_SCAN: shared targets have no closing metadata summary')
    complete = bool(gate and content and load and summary and scan)
    startup_passed = complete and failure_count == 0 and not metadata_errors and not ambiguous_sessions
    unavailable = [item for item in capabilities if item['status'] == 'unavailable']
    unknown = [item for item in capabilities if item['status'] == 'unknown']
    capability_reasons = [f"{item['capability']} [{item['status']}]: {item['reason']} Impact: {item['impact']} Target: {item['target']}"
                          for item in capabilities if item['status'] != 'available']
    passed = startup_passed and not unavailable and not unknown
    status = ('inconclusive' if ambiguous_sessions else 'unsupported' if failure_count else
              'inconclusive' if not startup_passed or unknown else 'degraded' if unavailable else 'initialization_passed')
    missing = [name for name, found in [('BUILD_GATE', gate), ('CONTENT_OK', content),
                                       ('LOAD_OK', load), ('COMPAT_SUMMARY', summary), ('COMPAT_SCAN', scan)] if not found]
    if ambiguous_sessions:
        reasons = ['Multiple Volibear startups without a reliable process boundary; provide one complete startup log.']
    elif failure_count:
        reasons = list(errors) if errors else ['COMPAT_SUMMARY reports failed modules; detailed cause is missing.']
    elif not startup_passed or unknown:
        reasons = metadata_errors + (['Missing startup evidence: ' + ', '.join(missing)] if missing else [])
    elif unavailable:
        reasons = []
    else:
        reasons = ['No reported initialization or patch failures in the supplied diagnostic log.']
    reasons.extend(capability_reasons)
    limitations = ['Startup-log evidence only; gameplay, save/load and multiplayer are not evaluated.']
    if scan and isinstance(scan.get('limitations'), str) and scan['limitations'].strip():
        limitations.append(scan['limitations'])
    if not capabilities:
        limitations.append('No capability assessments were declared; initialization evidence does not establish full feature support.')
    else:
        limitations.append('Only the listed capabilities were assessed; undeclared features are not certified.')
        limitations.extend(capability_reasons)
    return {
        'channel': channel.group(1) if channel else None,
        'target': target.group(1) if target else None,
        'gate_verified': bool(gate and 'build=verified' in gate),
        'initialized': bool(load),
        'content': content,
        'support_status': status,
        'scope': 'startup-log; gameplay/save-load/multiplayer not evaluated',
        'reasons': reasons,
        'failures': errors[:24],
        'failure_details': details[:24],
        'failures_truncated': len(details) > 24,
        'failure_count': failure_count,
        'shared_targets': shared,
        'patch_snapshot': scan,
        'capabilities': capabilities,
        'limitations': limitations,
        'metadata_errors': metadata_errors,
        'discarded_previous_boots': discarded_boots,
        'missing_evidence': missing,
        'passed': passed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--game-dir', type=Path, default=None,
                        help='Installed game directory (defaults to .local/config.json game_dir)')
    source.add_argument('--log', type=Path,
                        help='Read an existing complete startup log without launching or changing the game')
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--display', default='x11')
    parser.add_argument('--audio-driver', default='PulseAudio')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    started = time.time()
    if args.log is not None:
        log = args.log.read_text(encoding='utf-8-sig', errors='replace')
        game = None
    else:
        game = args.game_dir
        if game is None:
            config = json.loads((ROOT / '.local/config.json').read_text(encoding='utf-8-sig'))
            game = Path(config['game_dir'])
        game = Path(game).resolve()
        log_path = ROOT / '.local/logs/compat-report.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = run(game, log_path, args.timeout, args.display, args.audio_driver)
    result = report(log)
    result['game_dir'] = str(game) if game else None
    result['log_file'] = str(args.log.resolve()) if args.log else None
    result['seconds'] = round(time.time() - started, 1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
