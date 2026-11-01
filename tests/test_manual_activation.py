"""Owned-window focus opt-in: pure mocks, no Win32 calls, processes, or input."""
import copy
import ctypes
from ctypes import wintypes
from contextlib import ExitStack
import inspect
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from test_manual_input import fixture, log_for, FakeUser32, TOKEN, NONCE, PID, HWND, runner, gate


class User(FakeUser32):
    def __init__(self):
        super().__init__()
        self.foreground=9999
        self.last=9000
        self.info_ok=True
        self.buttons=set()
        self.calls=[]
        self.allow=True
        self.take_focus=True
        self.input_during=False
    def GetLastInputInfo(self, pointer):
        info=ctypes.cast(pointer,ctypes.POINTER(runner.LastInputInfo)).contents
        assert info.cbSize==ctypes.sizeof(runner.LastInputInfo)
        info.dwTime=self.last
        return self.info_ok
    def GetAsyncKeyState(self,key): return 0x8000 if key in self.buttons else 0
    def SetForegroundWindow(self,hwnd):
        self.calls.append(hwnd)
        if self.allow and self.take_focus: self.foreground=hwnd
        if self.input_during: self.last=10005
        return self.allow
    def SendInput(self,*args): raise AssertionError('No native input permitted in activation tests')


class Kernel:
    def __init__(self): self.tick=10005; self.member=True; self.ok=True
    def GetTickCount64(self): return self.tick
    def IsProcessInJob(self,process,job,pointer):
        assert process==101 and job==789
        ctypes.cast(pointer,ctypes.POINTER(wintypes.BOOL)).contents.value=self.member
        return self.ok


def setup_activation():
    api=runner.WinMouse.__new__(runner.WinMouse)
    api.user=User(); api.kernel=Kernel()
    event=threading.Event(); event.set()
    owned=SimpleNamespace(process=SimpleNamespace(pid=PID,_handle=101,poll=lambda:None),job=789,
                          event=event,abort=MagicMock(),launch_tick=9900,launch_last_input=9000)
    ready,_,_=fixture()
    return api,owned,ready


def activation_fixture():
    ready,result,injected=fixture()
    injected['spawn'].update(launchTickMs=9900,launchLastInputTickMs=9000)
    api,owned,_=setup_activation()
    activation=dict(requested=True,requestCount=0)
    api.activate_owned(ready,owned,activation)
    injected['activation']=activation
    return ready,result,injected


class ActivationTests(unittest.TestCase):
    def test_exactly_one_request_only_to_live_owned_hwnd(self):
        api,owned,ready=setup_activation(); record=dict(requested=True,requestCount=0)
        api.activate_owned(ready,owned,record)
        self.assertEqual(api.user.calls,[HWND])
        self.assertEqual(record['oldForegroundHwnd'],9999)
        self.assertEqual(record['oldForegroundPid'],999)
        self.assertEqual(record['postForegroundHwnd'],HWND)
        self.assertEqual(record['postForegroundPid'],PID)
        self.assertEqual(record['launchLastInputTickMs'],record['postLastInputTickMs'])
        self.assertTrue(record['requestResult'])
        with self.assertRaises(gate.EvidenceError): api.activate_owned(ready,owned,record)
        with self.assertRaises(gate.EvidenceError):
            api.activate_owned(ready,owned,dict(requested=True,requestCount=0))
        self.assertEqual(api.user.calls,[HWND])

    def test_preflight_failures_never_request_focus(self):
        mutations=[lambda a,o,r: setattr(o,'job',None),
                   lambda a,o,r: setattr(o.process,'poll',lambda:0),
                   lambda a,o,r: setattr(o.process,'pid',999),
                   lambda a,o,r: setattr(a.user,'window_pid',999),
                   lambda a,o,r: setattr(a.user,'IsWindow',lambda h:False),
                   lambda a,o,r: setattr(a.user,'IsWindowVisible',lambda h:False),
                   lambda a,o,r: setattr(a.user,'IsIconic',lambda h:True),
                   lambda a,o,r: setattr(a.kernel,'member',False),
                   lambda a,o,r: setattr(a.kernel,'ok',False),
                   lambda a,o,r: setattr(a.user,'last',9990),
                   lambda a,o,r: setattr(a.user,'last',8900),
                   lambda a,o,r: setattr(a.user,'info_ok',False),
                   lambda a,o,r: setattr(o,'launch_tick',None),
                   lambda a,o,r: setattr(o,'launch_last_input',9900),
                   lambda a,o,r: r.update(requested=False),
                   lambda a,o,r: r.update(requestCount=1)]
        mutations += [lambda a,o,r,key=key: a.user.buttons.add(key) for key in (1,2,4,5,6)]
        for index,mutate in enumerate(mutations):
            with self.subTest(index=index):
                api,owned,ready=setup_activation(); record=dict(requested=True,requestCount=0)
                mutate(api,owned,record)
                with self.assertRaises(gate.EvidenceError): api.activate_owned(ready,owned,record)
                self.assertEqual(api.user.calls,[])

    def test_os_refusal_wrong_post_focus_or_input_during_request_never_retry(self):
        for field in ('allow','take_focus','input_during'):
            with self.subTest(field=field):
                api,owned,ready=setup_activation(); record=dict(requested=True,requestCount=0)
                setattr(api.user,field,field=='input_during')
                with self.assertRaises(gate.EvidenceError): api.activate_owned(ready,owned,record)
                self.assertEqual(api.user.calls,[HWND])
                self.assertEqual(record['requestCount'],1)

    def test_last_input_wrap_and_unavailable_clock(self):
        api,_,_=setup_activation()
        api.kernel.tick=(1<<32)+10; api.user.last=0xfffffff0
        self.assertEqual(api.last_input_tick(),(1<<32)-16)
        api.kernel.tick=50; api.user.last=100
        with self.assertRaises(gate.EvidenceError): api.last_input_tick()
        self.assertEqual(ctypes.sizeof(runner.LastInputInfo),8)

    def watcher(self,opt_in,allow=True):
        api,owned,ready=setup_activation(); api.user.allow=allow
        directory=MagicMock(name='manifest_no_filesystem')
        manifest=directory.__truediv__.return_value
        manifest.is_file.return_value=True
        manifest.stat.return_value=SimpleNamespace(st_size=1000)
        manifest.read_text.return_value=json.dumps(ready)
        watcher=runner.InputWatcher(api,directory,TOKEN,NONCE,owned,1,threading.Event(),opt_in)
        # Exercise the unchanged per-packet admission guard without sending any packet.
        with patch.object(runner,'inject_drag',side_effect=lambda *args:api.verify(ready,owned.process,[700,700])) as drag:
            watcher.run()
            called=drag.call_count
        return api,owned,watcher,called

    def test_default_watcher_never_requests_focus_and_still_refuses_foreign_foreground(self):
        self.assertIs(inspect.signature(runner.run_case).parameters['activate_owned_window'].default,False)
        self.assertIs(inspect.signature(runner.InputWatcher).parameters['activate_owned_window'].default,False)
        api,owned,watcher,called=self.watcher(False)
        self.assertEqual(api.user.calls,[])
        self.assertIsNone(watcher.receipt['activation'])
        self.assertIn('Foreground is not owned target',watcher.receipt['error'])
        self.assertEqual(watcher.receipt['packets'],[])
        owned.abort.assert_called_once()

    def test_opt_in_precedes_drag_and_os_refusal_prevents_all_drag(self):
        api,owned,watcher,called=self.watcher(True)
        self.assertEqual(api.user.calls,[HWND]); self.assertEqual(called,1)
        self.assertIsNone(watcher.receipt['error']); owned.abort.assert_not_called()
        api,owned,watcher,called=self.watcher(True,allow=False)
        self.assertEqual(api.user.calls,[HWND]); self.assertEqual(called,0)
        self.assertIn('OS denied',watcher.receipt['error']); owned.abort.assert_called_once()


class ActivationEvidenceTests(unittest.TestCase):
    def test_gate_requires_trusted_opt_in_not_trace_claim(self):
        ready,result,injected=activation_fixture(); log=log_for(ready,result)
        self.assertFalse(gate.check_log(log,ready,injected,TOKEN,NONCE,PID)['valid'])
        self.assertTrue(gate.check_log(log,ready,injected,TOKEN,NONCE,PID,activate_owned_window=True)['valid'])
        injected.pop('activation')
        self.assertFalse(gate.check_log(log,ready,injected,TOKEN,NONCE,PID,activate_owned_window=True)['valid'])
        self.assertTrue(gate.check_log(log,ready,injected,TOKEN,NONCE,PID)['valid'])

    def test_activation_raw_identity_inactivity_order_and_result_mutations(self):
        changes=[('requested',False),('requestResult',False),('jobMember',False),('pressedButtons',[2]),
                 ('requestCount',0),('requestCount',2),('requestCount',True),
                 ('targetHwnd',999),('targetPid',999),('postForegroundHwnd',999),('postForegroundPid',999),
                 ('jobHandle',999),('oldForegroundHwnd',0),('oldForegroundPid',0),
                 ('launchTickMs',9991),('launchLastInputTickMs',8999),('lastInputTickMs',9999),
                 ('postLastInputTickMs',9999),('checkTickMs',9999),('requestTickMs',9999),
                 ('postTickMs',10011),('postTickMs',True)]
        for key,value in changes:
            with self.subTest(key=key,value=value):
                ready,result,injected=activation_fixture(); injected['activation'][key]=value
                self.assertFalse(gate.check_log(log_for(ready,result),ready,injected,TOKEN,NONCE,PID,
                                               activate_owned_window=True)['valid'])
        ready,result,injected=activation_fixture()
        injected['spawn']['launchTickMs']=10001; injected['activation']['launchTickMs']=10001
        self.assertFalse(gate.check_log(log_for(ready,result),ready,injected,TOKEN,NONCE,PID,
                                       activate_owned_window=True)['valid'])


class ActivationRoutingTests(unittest.TestCase):
    def test_spawn_clock_is_captured_before_actual_owned_spawn(self):
        order=[]; captured={}; directory=MagicMock()
        api=MagicMock()
        api.tick.side_effect=lambda:order.append('launch-tick') or 9900
        api.last_input_tick.side_effect=lambda:order.append('last-input') or 9000
        process=SimpleNamespace(pid=PID,poll=lambda:0)
        def spawn(*a,**k): order.append('spawn'); return process,789
        watcher=MagicMock(); watcher.is_alive.return_value=False; watcher.ready={}; watcher.receipt={}
        def create_watcher(*args): captured['owned']=args[4]; captured['opt_in']=args[-1]; return watcher
        def launch(*args): runner.headless.spawn_owned(); return 0,False
        with ExitStack() as stack:
            stack.enter_context(patch.object(runner,'WinMouse',return_value=api))
            stack.enter_context(patch.object(runner,'InputWatcher',side_effect=create_watcher))
            stack.enter_context(patch.object(runner.headless,'stock_teardown',return_value=(set(),{'successful':True})))
            stack.enter_context(patch.object(runner.headless,'prepare_run',return_value=(directory,{},['game','--force-steam=off'])))
            stack.enter_context(patch.object(runner.headless,'new_run_id',return_value=TOKEN))
            stack.enter_context(patch.object(runner.headless,'spawn_owned',side_effect=spawn))
            stack.enter_context(patch.object(runner.headless,'launch',side_effect=launch))
            stack.enter_context(patch.object(runner.headless,'combined_log',return_value='[Volibear] SHUTDOWN_BEGIN '+TOKEN))
            stack.enter_context(patch.object(runner.headless,'evaluate',return_value={}))
            gate_mock=stack.enter_context(patch.object(runner,'check_log',return_value={'valid':True}))
            stack.enter_context(patch.object(runner.subprocess,'check_output',side_effect=['mock',b'']))
            runner.run_case(Path('mock-owned-game'),activate_owned_window=True)
        self.assertEqual(order,['launch-tick','last-input','spawn'])
        self.assertTrue(captured['opt_in'])
        self.assertEqual(captured['owned'].launch_tick,9900)
        self.assertEqual(captured['owned'].launch_last_input,9000)
        self.assertIs(gate_mock.call_args.kwargs['activate_owned_window'],True)
        api.activate_owned.assert_not_called()  # Watcher is mocked, never starts a native thread.

    def test_cli_explicit_flag_and_default_route(self):
        for flag in (False,True):
            with self.subTest(flag=flag), ExitStack() as stack:
                argv=['manual_input.py']+(['--activate-owned-window'] if flag else [])
                stack.enter_context(patch.object(runner.sys,'argv',argv))
                stack.enter_context(patch.object(runner.headless,'config',return_value={'game_dir':'.'}))
                stack.enter_context(patch.object(runner.headless,'validate_game'))
                case=stack.enter_context(patch.object(runner,'run_case',return_value={'status':'passed'}))
                stack.enter_context(patch('builtins.print'))
                self.assertEqual(runner.main(),0)
                self.assertIs(case.call_args.args[-1],flag)


if __name__=='__main__': unittest.main()
