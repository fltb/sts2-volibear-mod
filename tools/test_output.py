"""Retention for newly created, runner-owned native test output."""
from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
_scope = ContextVar('test_output_scope', default=None)
MARKER = '.test-output-complete'


def settings():
    path = ROOT / '.local/test-output.json'
    options = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    mode = os.environ.get('VOLIBEAR_TEST_OUTPUT', options.get('mode', 'minimal'))
    keep = options.get('keep_runs', 10)
    if mode not in ('minimal', 'detailed') or type(keep) is not int or not 1 <= keep <= 100:
        raise ValueError('Test output requires mode minimal/detailed and keep_runs in 1..100')
    return mode, keep


@contextmanager
def session():
    """Keep raw evidence until the outermost suite has finished its cross-run checks."""
    if _scope.get() is not None:
        yield
        return
    mode, keep = settings()
    with ExitStack() as stack:
        token = _scope.set((stack, mode, keep))
        try:
            yield
        finally:
            _scope.reset(token)


def remove(path):
    if path.is_symlink() or not path.is_dir():
        path.unlink(missing_ok=True)
    else:
        shutil.rmtree(path)


def scratch(path):
    scope = _scope.get()
    if scope is not None:
        scope[0].callback(remove, path)


def register(directory, report=None):
    scope = _scope.get()
    if scope is not None:
        scope[0].callback(_finish, directory, *scope[1:], report)


def rotate(parent, keep):
    # Only our completion markers qualify. Active runs and unrelated directories never do.
    completed = []
    for marker in parent.glob('*/' + MARKER):
        try:
            if not marker.parent.is_symlink() and marker.is_file():
                completed.append((marker.stat().st_mtime_ns, marker.parent))
        except FileNotFoundError:
            continue
    for _, directory in sorted(completed, reverse=True)[keep:]:
        try:
            shutil.rmtree(directory)
        except FileNotFoundError:
            pass  # A concurrent finisher already rotated it.


def _finish(directory, mode, keep, report):
    if not directory.is_dir() or directory.is_symlink():
        return
    if report:
        (directory / 'report.json').write_text(json.dumps(report), encoding='utf-8')
    if mode == 'minimal':
        summaries = {}
        for path in directory.glob('*report.json'):
            data = json.loads(path.read_text(encoding='utf-8'))
            summary = {k: data[k] for k in ('run_id', 'scenario', 'status', 'passed', 'successful',
                                              'exit_code', 'timed_out', 'checks') if k in data}
            details = data.get('diagnostics', {})
            reasons = [str(x)[:512] for x in (data.get('errors') or [])[:8]]
            for key in ('runtime_errors', 'shutdown_errors'):
                reasons.extend(str(x)[:512] for x in details.get(key, [])[:4])
            combat = data.get('combat_tests')
            if isinstance(combat, dict):
                reasons.extend(str(x)[:512] for x in combat.get('errors', [])[:4])
            if reasons:
                summary['errors'] = reasons
            summaries[path.name] = summary
        if not summaries:
            summaries['report.json'] = {'run_id': directory.name, 'status': 'incomplete'}
        error = sys.exc_info()[1]
        for summary in summaries.values():
            if error:
                summary['exception'] = str(error)[:1024]
            if summary.get('status') in ('incomplete', 'failed') and not summary.get('errors'):
                for name in ('game.log', 'stdout.log'):
                    log = directory / name
                    if log.is_file() and log.stat().st_size:
                        with log.open('rb') as stream:
                            stream.seek(max(0, log.stat().st_size - 2048))
                            summary['log_tail'] = stream.read().decode(errors='replace')
                        break
        for name, summary in summaries.items():
            (directory / name).write_text(json.dumps(summary, ensure_ascii=False) + '\n', encoding='utf-8')
        for child in directory.iterdir():
            if child.name not in summaries:
                remove(child)
    else:
        # Isolated OS profiles are disposable even when retaining requested evidence.
        for name in ('home', 'appdata', 'localappdata', 'temp', 'data', 'config', 'cache', 'tmp'):
            remove(directory / name)
    (directory / MARKER).touch()
    rotate(directory.parent, keep)
