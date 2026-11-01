"""Validate and freeze exploration launch inputs; never launches or deploys the game.

Explore approval requires the complete successful window-run report, not merely a
probe artifact emitted before a later runtime/teardown failure.
"""
import hashlib
import json
from pathlib import Path

from enemy_catalog_evidence import validate_manifest as validate_catalog
from enemy_exploration_evidence import validate_exploration, validate_selection

PUBLIC_GATES = frozenset({
    'exited_zero', 'steam_disabled', 'no_cloud_backend', 'no_runtime_errors',
    'mod_initialized', 'runtime_isolation', 'teardown_matches_stock', 'stock_control_success',
})
REQUIRED_GATES = PUBLIC_GATES | {'enemy_exploration_assertions'}
SNAPSHOT_DIRECTORY = 'enemy-exploration-inputs'
SELECTION_NAME = 'selection.json'
CATALOG_NAME = 'catalog.json'
REPORT_NAME = 'prerequisite-report.json'
MANIFEST_NAME = 'enemy-exploration.json'


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _exact(actual, expected, message):
    _require(type(actual) is type(expected) and actual == expected, message)


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result, 'Duplicate JSON key: '+key)
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError('Non-finite JSON constant: '+value)


def _read(path, label):
    try:
        raw = Path(path).read_bytes()
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_bad_constant)
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError('Cannot read valid '+label+': '+str(error)) from error
    _require(isinstance(data, dict), label+' must be a JSON object')
    return raw, data


def _validate_prerequisite(report_path, selection, catalog):
    report_path = Path(report_path).resolve()
    report_raw, report = _read(report_path, 'prerequisite runner report')
    for key, expected in dict(schema=1, mode='real-game-window', scenario='enemy-exploration',
                             game_version='0.107.1', game_commit='59260271', status='passed',
                             exit_code=0, timed_out=False).items():
        _exact(report.get(key), expected, 'Prerequisite runner report rejected: '+key)
    token = report.get('run_id')
    _require(isinstance(token, str) and bool(token.strip()), 'Prerequisite report has no run token')
    _exact(selection.get('prerequisiteToken'), token, 'Selection prerequisite token mismatch')
    checks = report.get('checks')
    _require(isinstance(checks, dict) and set(checks) == REQUIRED_GATES,
             'Prerequisite report must contain exactly eight public gates plus enemy_exploration_assertions')
    _require(all(value is True for value in checks.values()), 'Prerequisite runner gate failed/not boolean true')
    diagnostics = report.get('diagnostics')
    _require(isinstance(diagnostics, dict), 'Missing prerequisite diagnostics')
    _exact(diagnostics.get('shutdown_marker_seen'), True, 'Missing native shutdown marker')
    _exact(diagnostics.get('runtime_errors'), [], 'Prerequisite contains runtime errors')
    summary = report.get('combat_tests')
    _require(isinstance(summary, dict), 'Prerequisite report lacks bound combat summary')
    for key, expected in dict(token=token, scenario='enemy-exploration', acceptance='bounded-native-exploration-only',
                             manifest=MANIFEST_NAME, completed=True, failure=None,
                             validationErrors=[], completeAiCoverage=False, caseCount=6).items():
        _require(key in summary, 'Missing prerequisite summary field: '+key)
        _exact(summary[key], expected, 'Prerequisite summary rejected: '+key)
    artifact_path = (report_path.parent / MANIFEST_NAME).resolve()
    _require(artifact_path.parent == report_path.parent, 'Prerequisite manifest escapes report directory')
    artifact_raw, artifact = _read(artifact_path, 'prerequisite native manifest')
    _exact(summary.get('bytes'), len(artifact_raw), 'Prerequisite manifest byte length mismatch')
    _exact(summary.get('sha256'), hashlib.sha256(artifact_raw).hexdigest(), 'Prerequisite manifest SHA256 mismatch')
    _exact(artifact.get('token'), token, 'Prerequisite native token mismatch')
    _exact(artifact.get('gameVersion'), 'v'+report['game_version'], 'Prerequisite native/report version mismatch')
    _exact(artifact.get('gameCommit'), report['game_commit'], 'Prerequisite native/report commit mismatch')
    smoke_selection = artifact.get('selection')
    _require(isinstance(smoke_selection, dict) and smoke_selection.get('mode') == 'smoke',
             'Prerequisite is not four-Act/three-terminal smoke')
    errors = validate_exploration(artifact, selection=smoke_selection, catalog=catalog, run_id=token)
    _require(not errors, 'Prerequisite smoke evidence invalid: '+'; '.join(errors))
    return report_raw, artifact_raw, artifact


def prepare_run_inputs(directory, selection_path, catalog_path, prerequisite_report_path=None):
    """Return (env additions, absolute frozen selection Path, catalog dict, prerequisite dict|None).

    All source bytes are read once, validated before destination creation, and then
    copied with exclusive creation into a new input subdirectory. Existing snapshots
    are never overwritten. Caller must clear inherited VOLIBEAR_TEST_EXPLORATION_APPROVED
    before merging these additions: smoke intentionally returns no approval variable.
    """
    selection_raw, selection = _read(selection_path, 'selection')
    catalog_raw, catalog = _read(catalog_path, 'catalog')
    errors = validate_catalog(catalog, run_id=catalog.get('token'))
    _require(not errors, 'Invalid native catalog: '+'; '.join(errors))
    errors = validate_selection(selection, catalog)
    _require(not errors, 'Invalid exploration selection: '+'; '.join(errors))
    frozen = {SELECTION_NAME: selection_raw, CATALOG_NAME: catalog_raw}
    prerequisite = None
    if selection['mode'] == 'explore':
        _require(prerequisite_report_path is not None, 'Explore requires successful smoke runner report')
        report_raw, artifact_raw, prerequisite = _validate_prerequisite(prerequisite_report_path, selection, catalog)
        frozen[REPORT_NAME] = report_raw
        frozen[MANIFEST_NAME] = artifact_raw
    else:
        _require(prerequisite_report_path is None and selection.get('prerequisiteToken') is None,
                 'Smoke cannot carry prerequisite approval')
    root = Path(directory).resolve()
    destination = root / SNAPSHOT_DIRECTORY
    try:
        root.mkdir(parents=True, exist_ok=True)
        destination.mkdir(exist_ok=False)
        for name, raw in frozen.items():
            with (destination / name).open('xb') as stream:
                stream.write(raw)
    except OSError as error:
        # No destructive rollback: preserve any partial snapshot for diagnosis and
        # reject reuse of its directory. Retrying requires a fresh run directory.
        raise ValueError('Cannot create fresh frozen exploration inputs: '+str(error)) from error
    selection_snapshot = destination / SELECTION_NAME
    env = {'VOLIBEAR_TEST_MATRIX_SELECTION': str(selection_snapshot)}
    if prerequisite is not None:
        env['VOLIBEAR_TEST_EXPLORATION_APPROVED'] = prerequisite['token']
    return env, selection_snapshot, catalog, prerequisite
