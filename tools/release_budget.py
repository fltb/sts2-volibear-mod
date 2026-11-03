"""Fixed release wall-clock budget; worker starts only after process-tree ownership."""
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid

LIMIT_SECONDS = 600
WORKER_KEY = 'VOLIBEAR_RELEASE_WORKER'
PERMIT_KEY = 'VOLIBEAR_RELEASE_PERMIT'
PARENT_KEY = 'VOLIBEAR_RELEASE_PARENT'


def worker_permit():
    """Consume the private supervisor handshake; inherited partial markers fail closed."""
    values = [os.environ.pop(key, None) for key in (WORKER_KEY, PERMIT_KEY, PARENT_KEY)]
    if not any(value is not None for value in values):
        return None
    token, filename, parent = values
    if not token or not filename or not parent or int(parent) != os.getppid():
        raise ValueError('Invalid release worker parent/permit')
    until = time.monotonic() + 5
    while not Path(filename).is_file():
        if time.monotonic() >= until or os.getppid() != int(parent):
            raise RuntimeError('Release supervisor did not grant an owned-worker permit')
        time.sleep(.01)
    permit = json.loads(Path(filename).read_text(encoding='utf-8'))
    if (permit.get('token') != token or permit.get('parent') != int(parent)
            or not isinstance(permit.get('deadline'), (int, float))
            or not 0 < permit['deadline'] - time.monotonic() <= LIMIT_SECONDS):
        raise ValueError('Invalid or expired release worker permit')
    return permit


def _processes():
    rows = {}
    for item in Path('/proc').iterdir():
        if not item.name.isdigit():
            continue
        try:
            fields = (item / 'stat').read_text().rsplit(')', 1)[1].split()
            rows[int(item.name)] = (int(fields[1]), fields[19], fields[0])
        except (OSError, ValueError, IndexError):
            continue
    return rows


def _descendants(rows, parent):
    found = set()
    frontier = {parent}
    while frontier:
        children = {pid for pid, row in rows.items() if row[0] in frontier} - found
        found.update(children)
        frontier = children
    return found


def _subreaper():
    if not sys.platform.startswith('linux'):
        raise RuntimeError('Release tree supervision supports Windows or Linux only')
    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(previous), 0, 0, 0) != 0 or libc.prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'Cannot establish release child subreaper')
    return libc, previous.value


def _linux_cleanup(existing, until):
    # A subreaper adopts orphaned descendants even if native tools used setsid().
    # Do not touch any child tree that predated this supervision call.
    while True:
        rows = _processes()
        owned = _descendants(rows, os.getpid())
        for pid in existing:
            owned.discard(pid)
            owned.difference_update(_descendants(rows, pid))
        if not owned:
            return True
        for pid in owned:
            try:
                if rows[pid][2] != 'Z':
                    # Bind the signal to this process identity, not a reusable PID.
                    if hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'):
                        fd = os.pidfd_open(pid)
                        try:
                            signal.pidfd_send_signal(fd, signal.SIGKILL)
                        finally:
                            os.close(fd)
                    elif _processes().get(pid) == rows[pid]:
                        os.kill(pid, signal.SIGKILL)
                try:
                    os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    pass
            except ProcessLookupError:
                pass
        if time.monotonic() >= until:
            return False
        time.sleep(.01)


def _wait_windows_job(job, until):
    from ctypes import wintypes
    class Accounting(ctypes.Structure):
        _fields_ = [('times', ctypes.c_int64 * 4), ('faults', wintypes.DWORD),
                    ('total', wintypes.DWORD), ('active', wintypes.DWORD),
                    ('terminated', wintypes.DWORD)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    query = kernel.QueryInformationJobObject
    query.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    query.restype = wintypes.BOOL
    while True:
        accounting = Accounting()
        if not query(job, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
            raise OSError(ctypes.get_last_error(), 'Cannot verify release job cleanup')
        if accounting.active == 0:
            return True
        if time.monotonic() >= until:
            return False
        time.sleep(.01)


def supervise(command, root, *, started=None, seconds=LIMIT_SECONDS, cleanup_reserve=5):
    """Run a single delivery worker. Shorter budgets are for synthetic tests only."""
    if not 0 < seconds <= LIMIT_SECONDS or not 0 < cleanup_reserve < seconds:
        raise ValueError('Release deadline must be at most 600 seconds with cleanup reserve')
    started = time.monotonic() if started is None else started
    deadline = started + seconds
    work_deadline = deadline - cleanup_reserve
    directory = Path(root) / '.local/release-deadlines'
    directory.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='run-', dir=directory))
    permit_path = directory / 'permit.json'
    report = {'schema': 1, 'limit_seconds': seconds, 'status': 'failed',
              'package_accepted': False, 'cleanup_complete': False}
    env = dict(os.environ)
    token = uuid.uuid4().hex
    env.update({WORKER_KEY: token, PERMIT_KEY: str(permit_path), PARENT_KEY: str(os.getpid())})
    process = job = libc = None
    previous = 0
    existing = set()
    code = 1
    try:
        if time.monotonic() >= work_deadline:
            raise subprocess.TimeoutExpired(command, seconds)
        if os.name == 'nt':
            # headless also supports direct script execution and its sibling imports.
            tools_path = str(Path(__file__).resolve().parent)
            if tools_path not in sys.path:
                sys.path.insert(0, tools_path)
            try:
                from tools import headless
            except ModuleNotFoundError:
                import headless
            job = headless._create_job()
        else:
            existing = _descendants(_processes(), os.getpid())
            libc, previous = _subreaper()
        process = subprocess.Popen([str(value) for value in command], cwd=root, env=env)
        report['worker_pid'] = process.pid
        if os.name == 'nt' and not headless._assign_job(job, process):
            raise RuntimeError('Cannot assign release worker to its owned job')
        # Permit creation is the only transition into preflight/build/native work.
        pending = directory / 'permit.pending'
        with pending.open('x', encoding='utf-8') as stream:
            json.dump({'token': token, 'parent': os.getpid(), 'deadline': work_deadline}, stream)
        # Both paths belong to this newly created private directory; publish atomically
        # so the waiting worker never reads a partially written JSON permit.
        pending.rename(permit_path)
        code = process.wait(timeout=max(0, work_deadline - time.monotonic()))
        report['worker_exit_code'] = code
        report['status'] = 'completed' if code == 0 else 'failed'
    except subprocess.TimeoutExpired:
        code = 124
        report['status'] = 'deadline_exceeded'
        report['error'] = 'Release total wall-clock deadline exhausted; package is not accepted'
    except Exception as error:
        code = 1
        report['error'] = str(error)
    finally:
        report['cleanup_complete'] = process is None
        try:
            if os.name == 'nt':
                cleaned = True
                if job is not None:
                    try:
                        if not headless._terminate_job(job):
                            raise RuntimeError('Cannot terminate owned release job')
                        cleaned = _wait_windows_job(job, deadline - .25)
                    finally:
                        headless.close_owned(job)
                if process is not None:
                    if process.poll() is None:
                        process.kill()  # Also covers assignment failure before the permit.
                    process.wait(timeout=max(.01, deadline - time.monotonic() - .25))
                report['cleanup_complete'] = cleaned
            elif libc is not None:
                report['cleanup_complete'] = _linux_cleanup(existing, deadline - .25)
                if process is not None:
                    process.poll()
        except Exception as error:
            report['cleanup_error'] = str(error)
        finally:
            if libc is not None:
                libc.prctl(36, previous, 0, 0, 0)
        if not report['cleanup_complete']:
            code = 1 if code == 0 else code
            report['status'] = 'cleanup_failed' if code != 124 else report['status']
        report['elapsed_seconds'] = time.monotonic() - started
        if report['elapsed_seconds'] >= seconds:
            code = 124
            report['status'] = 'deadline_exceeded'
        report['package_accepted'] = code == 0 and report['status'] == 'completed'
        report['exit_code'] = code
        (directory / 'deadline.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print('Release deadline report: ' + str(directory / 'deadline.json'), flush=True)
    return code
