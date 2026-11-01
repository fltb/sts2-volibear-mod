#!/usr/bin/env python3
"""Run one genuine B01 mouse-drag/payment case in an owned, isolated Windows game.
Requires the already built/deployed ManualPlayProbe and main's scenario registration.
Does not build/deploy, start Steam, change normal settings, or send keys.
Default leaves focus untouched; explicit opt-in permits one idle, owned-window activation request.
"""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from unittest.mock import patch

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / 'tools/headless.py').is_file())
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import headless
from manual_evidence import MOVE_FLAGS, STEPS, EvidenceError, check_log, require, rounded, validate_ready

ULONG_PTR = ctypes.c_size_t


class MouseInput(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]


class InputUnion(ctypes.Union):
    _fields_ = [('mi', MouseInput)]


class Input(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('data', InputUnion)]


class LastInputInfo(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.UINT), ('dwTime', wintypes.DWORD)]


class WinMouse:
    def __init__(self):
        if os.name != 'nt':
            raise RuntimeError('Native Windows SendInput is required; no fallback input route')
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'GetForegroundWindow': ([], wintypes.HWND),
            'SetForegroundWindow': ([wintypes.HWND], wintypes.BOOL),
            'GetLastInputInfo': ([ctypes.POINTER(LastInputInfo)], wintypes.BOOL),
            'GetWindowThreadProcessId': ([wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
            'IsWindow': ([wintypes.HWND], wintypes.BOOL),
            'IsWindowVisible': ([wintypes.HWND], wintypes.BOOL),
            'IsIconic': ([wintypes.HWND], wintypes.BOOL),
            'GetClientRect': ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            'GetWindowRect': ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            'ClientToScreen': ([wintypes.HWND, ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
            'WindowFromPoint': ([wintypes.POINT], wintypes.HWND),
            'GetAncestor': ([wintypes.HWND, wintypes.UINT], wintypes.HWND),
            'GetCursorPos': ([ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
            'GetAsyncKeyState': ([ctypes.c_int], ctypes.c_short),
            'GetSystemMetrics': ([ctypes.c_int], ctypes.c_int),
            'SendInput': ([wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int], wintypes.UINT),
            'SetProcessDpiAwarenessContext': ([wintypes.HANDLE], wintypes.BOOL),
            'GetThreadDpiAwarenessContext': ([], wintypes.HANDLE),
            'GetAwarenessFromDpiAwarenessContext': ([wintypes.HANDLE], ctypes.c_int),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.user, name)
            function.argtypes, function.restype = arguments, result
        self.kernel.GetTickCount64.argtypes = []
        self.kernel.GetTickCount64.restype = ctypes.c_ulonglong
        self.kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
        self.kernel.IsProcessInJob.restype = wintypes.BOOL
        self.user.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # This runner only; no user settings.
        awareness = self.user.GetAwarenessFromDpiAwarenessContext(self.user.GetThreadDpiAwarenessContext())
        require(awareness == 2, 'Per-monitor DPI awareness required for physical coordinates')
        require(ctypes.sizeof(Input) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28), 'Win32 INPUT layout')

    def tick(self):
        return int(self.kernel.GetTickCount64())

    def pid(self, hwnd):
        pid = wintypes.DWORD()
        require(bool(self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))), 'Window PID unavailable')
        return pid.value

    def last_input_tick(self):
        info = LastInputInfo(cbSize=ctypes.sizeof(LastInputInfo))
        require(bool(self.user.GetLastInputInfo(ctypes.byref(info))), 'Last-input history unavailable')
        now = self.tick()
        # LASTINPUTINFO wraps at 32 bits; compare on the same 64-bit boot clock as the probe.
        last = now - (((now & 0xffffffff) - info.dwTime) & 0xffffffff)
        require(0 <= last <= now, 'Last-input clock cannot be established')
        return last

    def activate_owned(self, ready, owned, record):
        """One standard request, only after explicit caller opt-in and full preflight."""
        require(record.get('requested') is True, 'Activation requires explicit opt-in')
        require(record.get('requestCount') == 0 and not getattr(self, '_activation_attempted', False),
                'Activation request already attempted')
        process, job = owned.process, owned.job
        require(process is not None and job is not None and process.poll() is None and
                process.pid == ready['processId'], 'Cannot activate an unowned/dead child')
        handle = job.value if hasattr(job, 'value') else int(job)
        member = wintypes.BOOL()
        require(handle > 0 and self.kernel.IsProcessInJob(process._handle, job, ctypes.byref(member)) and member.value,
                'Child is not a live member of the owned Windows job')
        hwnd = ready['window']['hwnd']
        require(self.user.IsWindow(hwnd) and self.user.IsWindowVisible(hwnd) and not self.user.IsIconic(hwnd)
                and self.pid(hwnd) == process.pid, 'Activation HWND is not the visible owned child')
        buttons = [key for key in (1, 2, 4, 5, 6) if self.user.GetAsyncKeyState(key) & 0x8000]
        previous = int(self.user.GetForegroundWindow() or 0)
        record.update(targetHwnd=hwnd, targetPid=process.pid, jobHandle=handle, jobMember=True,
                      pressedButtons=buttons, oldForegroundHwnd=previous,
                      oldForegroundPid=self.pid(previous) if previous else 0,
                      launchTickMs=owned.launch_tick, launchLastInputTickMs=owned.launch_last_input,
                      checkTickMs=self.tick(), lastInputTickMs=self.last_input_tick())
        require(not buttons, 'Mouse button already held; activation refused')
        require(type(owned.launch_tick) is int and type(owned.launch_last_input) is int and
                record['lastInputTickMs'] == owned.launch_last_input < owned.launch_tick <= record['checkTickMs'],
                'Input occurred since the pre-launch inactivity baseline; activation refused')
        record['requestTickMs'] = self.tick()
        record['requestCount'] = 1
        self._activation_attempted = True
        record['requestResult'] = bool(self.user.SetForegroundWindow(hwnd))
        current = int(self.user.GetForegroundWindow() or 0)
        record.update(postForegroundHwnd=current, postForegroundPid=self.pid(current) if current else 0,
                      postTickMs=self.tick(), postLastInputTickMs=self.last_input_tick())
        require(record['requestResult'] and current == hwnd and record['postForegroundPid'] == process.pid,
                'OS denied owned-window activation; no retry or fallback')
        require(record['postLastInputTickMs'] == owned.launch_last_input,
                'Input occurred during activation; no mouse packets permitted')

    def cursor(self):
        value = wintypes.POINT()
        require(bool(self.user.GetCursorPos(ctypes.byref(value))), 'Cursor unavailable')
        return [value.x, value.y]

    def verify(self, ready, process, point):
        require(process.poll() is None and process.pid == ready['processId'], 'Owned child exited or PID changed')
        hwnd = ready['window']['hwnd']
        require(self.user.IsWindow(hwnd) and self.user.IsWindowVisible(hwnd) and not self.user.IsIconic(hwnd), 'Owned window unavailable')
        require(self.pid(hwnd) == process.pid, 'Manifest HWND is not owned child')
        foreground = self.user.GetForegroundWindow()
        require(foreground == hwnd and self.pid(foreground) == process.pid, 'Foreground is not owned target; no focus stealing')
        client, outer, origin = wintypes.RECT(), wintypes.RECT(), wintypes.POINT(0, 0)
        require(self.user.GetClientRect(hwnd, ctypes.byref(client)) and
                self.user.GetWindowRect(hwnd, ctypes.byref(outer)) and
                self.user.ClientToScreen(hwnd, ctypes.byref(origin)), 'Window geometry unavailable')
        rectangle = [origin.x, origin.y, client.right - client.left, client.bottom - client.top]
        require(rectangle[2:] == ready['window']['size'], 'Window resized after native manifest')
        position = ready['window']['position']
        require(any(all(abs(a-b) <= 2 for a, b in zip(position, candidate))
                    for candidate in ([origin.x, origin.y], [outer.left, outer.top])), 'Window moved after native manifest')
        require(origin.x <= point[0] < origin.x + rectangle[2] and origin.y <= point[1] < origin.y + rectangle[3],
                'Input point outside owned game client')
        hit = self.user.WindowFromPoint(wintypes.POINT(*point))
        root = self.user.GetAncestor(hit, 2) if hit else 0
        require(root == hwnd and self.pid(hit) == process.pid, 'Input point covered by another window')
        return dict(foregroundHwnd=int(foreground), foregroundPid=process.pid, pointHwnd=int(root), clientRect=rectangle,
                    outerRect=[outer.left, outer.top, outer.right-outer.left, outer.bottom-outer.top])

    def left_down(self):
        return bool(self.user.GetAsyncKeyState(1) & 0x8000)

    def send(self, kind, point, tag):
        flags = {'move': MOVE_FLAGS, 'down': 2, 'up': 4}[kind]
        desktop = [self.user.GetSystemMetrics(index) for index in (76, 77, 78, 79)]
        left, top, width, height = desktop
        require(width > 1 and height > 1 and left <= point[0] < left+width and top <= point[1] < top+height,
                'Point outside virtual desktop')
        coordinates = [round((point[0]-left) * 65535 / (width-1)), round((point[1]-top) * 65535 / (height-1))]
        event = Input(type=0, data=InputUnion(mi=MouseInput(coordinates[0], coordinates[1], 0, flags, 0, tag)))
        tick = self.tick()  # Before insertion: native receipt may be delivered immediately on another thread.
        sent = self.user.SendInput(1, ctypes.byref(event), ctypes.sizeof(event))
        require(sent == 1, 'SendInput inserted no event (blocked desktop/UIPI or API failure)')
        deadline = time.monotonic() + 0.15
        cursor = self.cursor()
        while any(abs(a-b) > 2 for a, b in zip(cursor, point)) and time.monotonic() < deadline:
            time.sleep(0.005)
            cursor = self.cursor()
        return dict(kind=kind, point=point, flags=flags, sent=int(sent), tickMs=tick,
                    virtualScreen=desktop, normalised=coordinates, cursor=cursor)


class OwnedRun:
    def __init__(self):
        self.event = threading.Event()
        self.process = None
        self.job = None
        self.launch_tick = None
        self.launch_last_input = None

    def bind(self, process, job, launch_tick=None, launch_last_input=None):
        self.process, self.job = process, job
        self.launch_tick, self.launch_last_input = launch_tick, launch_last_input
        self.event.set()

    def abort(self):
        # This handle/PID came from our own spawn_owned, never from the manifest or EnumWindows.
        if self.process is not None and self.process.poll() is None:
            headless._terminate(self.process, self.job, force=True)


def inject_drag(api, ready, owned, receipt, stop):
    require(owned.job is not None and owned.process is not None, 'No owned Windows job')
    require(not api.left_down(), 'Existing mouse-down belongs to operator; refusing input')
    require(0 <= api.tick() - ready['readyTickMs'] <= 10000, 'Stale native ready manifest')
    start, end = (rounded(ready['anchors'][key]['screen']) for key in ('card', 'target'))
    tag = int(ready['nonce'][-16:], 16) & ((1 << (8 * ctypes.sizeof(ULONG_PTR))) - 1)
    initial_geometry = None
    last_point = None
    held = False

    def pause(seconds):
        require(not stop.wait(seconds), 'Owned run ended during input')

    def packet(kind, point):
        nonlocal initial_geometry, last_point, held
        require(not stop.is_set(), 'Input cancelled')
        if last_point is not None:
            require(all(abs(a-b) <= 3 for a, b in zip(api.cursor(), last_point)), 'Cursor changed externally; aborting')
        verification = api.verify(ready, owned.process, point)
        if initial_geometry is None:
            initial_geometry = verification['clientRect']
        require(verification['clientRect'] == initial_geometry, 'Owned client moved during drag')
        row = api.send(kind, point, tag)
        held = kind != 'up' if kind in ('down', 'up') else held
        receipt['packets'].append(dict(row, **verification))
        last_point = point
        require(all(abs(a-b) <= 2 for a, b in zip(row['cursor'], point)), 'Inserted move did not reach intended cursor position')

    try:
        packet('move', start)
        pause(0.12)
        packet('down', start)
        pause(0.06)
        for step in range(1, STEPS + 1):
            packet('move', [round(start[i] + (end[i]-start[i]) * step / STEPS) for i in range(2)])
            pause(0.015)
        packet('up', end)
    except Exception:
        if held:
            # Only release if ownership STILL holds. Never send even a cleanup event into a
            # foreign foreground; abort the owned child instead. Partial traces cannot pass.
            try:
                current = api.cursor()
                require(all(abs(a-b) <= 3 for a, b in zip(current, last_point)), 'Cursor moved outside owned drag')
                api.verify(ready, owned.process, current)
                receipt['cleanupRelease'] = api.send('up', current, tag)
            except Exception:
                receipt['cleanupReleaseSkipped'] = 'ownership lost; no further desktop input'
        raise


class InputWatcher(threading.Thread):
    def __init__(self, api, directory, token, nonce, owned, timeout, stop, activate_owned_window=False):
        super().__init__(name='Volibear-owned-mouse', daemon=False)
        self.api, self.directory, self.token, self.nonce = api, directory, token, nonce
        self.owned, self.timeout, self.stop = owned, timeout, stop
        require(type(activate_owned_window) is bool, 'Activation option must be an explicit boolean')
        self.activate_owned_window = activate_owned_window
        self.ready = None
        self.receipt = dict(schema=1, token=token, nonce=nonce, processId=None, hwnd=None,
                            api='Windows.SendInput.mouse_drag', spawn=None, packets=[], activation=None, error=None)

    def run(self):
        deadline = time.monotonic() + self.timeout
        try:
            while not self.owned.event.is_set():
                require(time.monotonic() < deadline and not self.stop.wait(0.025), 'No owned child before deadline')
            process, job = self.owned.process, self.owned.job
            require(process is not None and job is not None, 'Launch did not acquire Windows job ownership')
            handle = job.value if hasattr(job, 'value') else int(job)
            require(bool(handle), 'Empty Windows job handle')
            self.receipt.update(processId=process.pid, spawn=dict(pid=process.pid, jobHandle=handle,
                                launchTickMs=getattr(self.owned, 'launch_tick', None),
                                launchLastInputTickMs=getattr(self.owned, 'launch_last_input', None)))
            path = self.directory / 'manual-ready.json'
            while not path.is_file():
                require(process.poll() is None, 'Owned process exited before native input manifest')
                require(time.monotonic() < deadline and not self.stop.wait(0.025), 'No native ready manifest before deadline')
            require(path.stat().st_size <= 65536, 'Oversized native manifest')
            self.ready = json.loads(path.read_text(encoding='utf-8'))
            validate_ready(self.ready, self.token, self.nonce, process.pid)
            self.receipt['hwnd'] = self.ready['window']['hwnd']
            if self.activate_owned_window:
                self.receipt['activation'] = dict(requested=True, requestCount=0)
                self.api.activate_owned(self.ready, self.owned, self.receipt['activation'])
            inject_drag(self.api, self.ready, self.owned, self.receipt, self.stop)
        except Exception as error:
            self.receipt['error'] = type(error).__name__ + ': ' + str(error)
            self.owned.abort()


def run_case(game, timeout=90, ready_timeout=50, frames=10000, activate_owned_window=False):
    require(threading.current_thread() is threading.main_thread(), 'headless.launch must run on main thread')
    require(type(activate_owned_window) is bool, 'Activation option must be an explicit boolean')
    api = WinMouse()
    # A serial no-mods control retains the shared runner's strict teardown attribution.
    stock, stock_evidence = headless.stock_teardown(game, timeout, frames, 'window')
    if not stock_evidence['successful']:
        return dict(status='failed', error='Native stock window control failed', stock=stock_evidence)
    token, nonce = headless.new_run_id(), secrets.token_hex(24)
    directory, env, command = headless.prepare_run(game, token, frames, 'window')
    env.update(VOLIBEAR_TEST_SCENARIO='manual-play', VOLIBEAR_TEST_CHARACTER='volibear', VOLIBEAR_MANUAL_INPUT_NONCE=nonce)
    command.append('--bootstrap')
    require('--force-steam=off' in command and '--headless' not in command and 'Dummy' not in command, 'Offline native window command')
    owned, stop = OwnedRun(), threading.Event()
    watcher = InputWatcher(api, directory, token, nonce, owned, ready_timeout, stop, activate_owned_window)
    original_spawn = headless.spawn_owned

    def retain_owned_child(*arguments, **keywords):
        launch_tick = api.tick() if activate_owned_window else None
        launch_last_input = api.last_input_tick() if activate_owned_window else None
        process, job = original_spawn(*arguments, **keywords)
        owned.bind(process, job, launch_tick, launch_last_input)
        if job is None:
            headless.wait_owned_process(process, 0, job)
            raise RuntimeError('Cannot own Windows child job; no input permitted')
        return process, job

    watcher.start()
    launch_error = None
    try:
        # Local wrapper only; shared launcher source and its cleanup/isolation stay unchanged.
        with patch.object(headless, 'spawn_owned', retain_owned_child):
            code, timed_out = headless.launch(game, directory, env, command, timeout)
    except Exception as error:
        launch_error = type(error).__name__ + ': ' + str(error)
        owned.abort()
        code, timed_out = -1, False
    finally:
        stop.set()
        watcher.join(timeout=3)
    require(not watcher.is_alive(), 'Input watcher did not retire')
    (directory / 'manual-input.json').write_text(json.dumps(watcher.receipt, indent=2) + '\n', encoding='utf-8')
    log = headless.combined_log(directory)
    checks = headless.evaluate(code, timed_out, log, stock)
    checks['stock_control'] = stock_evidence['successful']
    checks['launch_succeeded'] = launch_error is None
    checks['shutdown_marker'] = '[Volibear] SHUTDOWN_BEGIN ' + token in log
    evidence = check_log(log, watcher.ready, watcher.receipt, token, nonce,
                         owned.process.pid if owned.process is not None else -1, directory,
                         activate_owned_window=activate_owned_window)
    checks['ordinary_input_payment'] = evidence['valid']
    report = dict(schema=1, run_id=token, scenario='manual-play', variant='b01', mode='real-game-window',
                  status='passed' if all(checks.values()) else 'failed', checks=checks,
                  exit_code=code, timed_out=timed_out, launch_error=launch_error,
                  activateOwnedWindow=activate_owned_window,
                  evidence=evidence, input=watcher.receipt, stock_teardown_control=stock_evidence,
                  game_version='v0.107.1', game_commit='59260271',
                  git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)))
    (directory / 'manual-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--ready-timeout', type=int, default=50)
    parser.add_argument('--frames', type=int, default=10000)
    parser.add_argument('--activate-owned-window', action='store_true',
                        help='Opt in to one standard owned-window focus request only if no input occurred since launch')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Windows is required; no emulated or direct-card fallback')
    if not 30 <= args.timeout <= 180 or not 5 <= args.ready_timeout <= args.timeout - 25 or not 3000 <= args.frames <= 10000:
        parser.error('timeout 30..180, ready-timeout 5..timeout-25, frames 3000..10000 required')
    game = Path(headless.config()['game_dir']).expanduser().resolve()
    headless.validate_game(game)
    report = run_case(game, args.timeout, args.ready_timeout, args.frames, args.activate_owned_window)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
