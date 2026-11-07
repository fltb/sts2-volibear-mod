#!/usr/bin/env python3
"""One-boot compatibility report for a packaged channel.

Boots the installed game once with the mod present and reports: version gate, mod
initialization, content registration, and every patch-install failure with the module
label the mod prints (e.g. "Steam patch failed: attack-machine"). This is the fast
per-beta-update diagnostic: one game start instead of edit->boot->next loops.
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
FAILURE_MARKERS = (
    'Exception thrown when calling mod initializer',
    'failed:', 'drift', 'signature changed', 'field changed', 'callsite changed',
    'changed:', 'is not async', 'pin missing', 'Ambiguous match',
)


def find_executable(game: Path) -> Path:
    for name in EXECUTABLES:
        path = game / name
        if path.is_file():
            return path
    raise SystemExit(f'No game executable under {game}')


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
    def first(pattern):
        match = re.search(pattern, log)
        return match.group(0).strip() if match else None

    gate = first(r'\[Volibear\] BUILD_GATE [^\r\n]*')
    load = first(r'\[Volibear\] LOAD_OK [^\r\n]*')
    content = first(r'\[Volibear\] CONTENT_OK [^\r\n]*')
    errors = []
    summary = re.search(r'COMPAT_SUMMARY failures=(\d+)', log)
    for line in log.splitlines():
        if 'COMPAT_FAIL' in line:
            text = line.strip()
            if text not in errors:
                errors.append(text)
        elif any(marker in line for marker in FAILURE_MARKERS):
            text = line.strip()
            if text not in errors:
                errors.append(text)
    channel = re.search(r'channel=([^\s]+)', gate or '')
    target = re.search(r'target=([^\s]+)', gate or '')
    return {
        'channel': channel.group(1) if channel else None,
        'target': target.group(1) if target else None,
        'gate_verified': bool(gate and 'build=verified' in gate),
        'initialized': bool(load),
        'content': content,
        'failures': errors[:24],
        'failure_count': int(summary.group(1)) if summary else len(errors),
        'passed': bool(load) and not errors,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dir', type=Path, default=None,
                        help='Installed game directory (defaults to .local/config.json game_dir)')
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--display', default='x11')
    parser.add_argument('--audio-driver', default='PulseAudio')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    game = args.game_dir
    if game is None:
        config = json.loads((ROOT / '.local/config.json').read_text(encoding='utf-8-sig'))
        game = Path(config['game_dir'])
    game = Path(game).resolve()
    log_path = ROOT / '.local/logs/compat-report.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    log = run(game, log_path, args.timeout, args.display, args.audio_driver)
    result = report(log)
    result['game_dir'] = str(game)
    result['seconds'] = round(time.time() - started, 1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
