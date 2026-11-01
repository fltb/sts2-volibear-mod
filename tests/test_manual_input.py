"""No game launch and no native input: independent evidence mutations + mocked Win32 ownership."""
import copy
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
import struct
import zlib
import tempfile
import threading
from types import SimpleNamespace
import unittest

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / 'tools/headless.py').is_file())
sys.path.insert(0, str(ROOT / 'tools'))
if Path(__file__).with_name('manual_input.py').is_file():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import manual_evidence as gate
import manual_input as runner

TOKEN = '20261101T000000Z-test1234'
NONCE = 'a' * 48
PID = 123
HWND = 456


PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def png_chunk(name, payload):
    return struct.pack('>I',len(payload)) + name + payload + struct.pack('>I',zlib.crc32(name+payload) & 0xffffffff)


def png_bytes(rgb=(255,0,0), width=1280, height=720, color=2, depth=8, raw=None, compressed=None):
    channels = 3 if color == 2 else 4
    if raw is None:
        pixel = bytes(rgb) if channels == 3 else bytes((*rgb,255))
        raw = (b'\0' + pixel*width)*height
    ihdr = png_chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,depth,color,0,0,0))
    return PNG_SIGNATURE + ihdr + png_chunk(b'IDAT',zlib.compress(raw) if compressed is None else compressed) + png_chunk(b'IEND',b'')


def fixture():
    before = dict(energy=3, maxEnergy=3, phase='Play', round=1, turn=1, playerHp=80,
                  playerBlock=0, playerId=100, playerNetId=0, cardId=0, cardModel='Volibear_B01',
                  pile='Hand', upgraded=False, masterIndex=0, masterModel='Volibear_B01',
                  deck=['Volibear_B01']*4 + ['Volibear_B02']*4 + ['Volibear_B03', 'Volibear_B04'],
                  piles=dict(Hand=[0], Draw=[1,2,3,4,5], Discard=[6,7,8,9], Exhaust=[], Play=[]),
                  enemies=[dict(id=n, model='NativeSlime', hp=50, maxHp=50, block=0) for n in (101,102,103)],
                  actionsDisabled=False, executingCard=False)
    after = copy.deepcopy(before)
    after.update(energy=2, pile='Discard')
    after['piles']['Hand'] = []
    after['piles']['Discard'].append(0)
    after['enemies'][-1]['hp'] = 44
    capture = dict(file='manual-before.png', width=1280, height=720, source='NGame.GetViewport.GetTexture.GetImage')
    ready = dict(schema=1, token=TOKEN, nonce=NONCE, scenario='manual-play', variant='b01',
                 gameVersion='v0.107.1', gameCommit='59260271', os='Windows', display='Windows',
                 processId=PID, godotProcessId=PID, pidSource='System.Environment.ProcessId',
                 readyTickMs=10000, testMode=False, steamInitialized=False,
                 window=dict(id=0, hwnd=HWND, position=[100,100], size=[1280,720], viewportSize=[1280,720],
                             screenTransform=[[1,0],[0,1],[100,100]]),
                 anchors=dict(card=dict(nodeId=501, local=[100,150], viewport=[600,600], screen=[700,700]),
                              target=dict(nodeId=502, local=[50,60], viewport=[1000,240], screen=[1100,340])),
                 cardId=0, targetId=103, originalCardIds=list(range(10)),
                 fixtureApi='CardPileCmd.Add;CreatureCmd.SetMaxAndCurrentHp', encounter='SlimesWeak',
                 before=before, beforeCapture=capture)
    play = dict(cardId=0, cardModel='Volibear_B01', targetId=103, isAutoPlay=False,
                energySpent=1, energyValue=1, starsSpent=0, playIndex=0, playCount=1, resultPile='Discard')
    hit = dict(targetId=103, unblocked=6, blocked=0, overkill=0, killed=False)
    rows = [('EnergySpentEntry', dict(amount=1, playerId=100), 10570),
            ('CardPlayStartedEntry', play, 10580),
            ('DamageReceivedEntry', dict(receiverId=103, cardId=0, hit=hit), 10600),
            ('CreatureAttackedEntry', dict(attackerId=100, hits=[hit]), 10620),
            ('CardPlayFinishedEntry', copy.deepcopy(play), 10640)]
    result = dict(schema=1, token=TOKEN, nonce=NONCE, scenario='manual-play', variant='b01',
                  gameVersion='v0.107.1', gameCommit='59260271', processId=PID,
                  api='Windows.SendInput.mouse_drag', acceptance='ordinary-input-and-native-payment',
                  before=copy.deepcopy(before), after=after,
                  history=[dict(index=i+1, kind=k, tickMs=t, data=d) for i,(k,d,t) in enumerate(rows)],
                  beforeCapture=copy.deepcopy(capture), afterCapture=dict(capture, file='manual-after.png'))
    start, end = [700,700], [1100,340]
    points = [start,start] + [[round(start[i]+(end[i]-start[i])*s/gate.STEPS) for i in range(2)]
                            for s in range(1,gate.STEPS+1)] + [end]
    kinds = ['move','down'] + ['move']*gate.STEPS + ['up']
    ticks = [10010,10130] + [10190+i*15 for i in range(gate.STEPS)] + [10550]
    packets = [dict(kind=k, point=p, flags={'move':gate.MOVE_FLAGS,'down':2,'up':4}[k], sent=1,
                    tickMs=t, cursor=p[:], foregroundHwnd=HWND, foregroundPid=PID, pointHwnd=HWND,
                    clientRect=[100,100,1280,720], outerRect=[100,100,1280,720], virtualScreen=[0,0,1920,1080],
                    normalised=[round(p[0]*65535/1919),round(p[1]*65535/1079)])
               for k,p,t in zip(kinds,points,ticks)]
    injected = dict(schema=1, token=TOKEN, nonce=NONCE, processId=PID, hwnd=HWND,
                    api='Windows.SendInput.mouse_drag', spawn=dict(pid=PID,jobHandle=789), packets=packets, error=None)
    return ready, result, injected


def log_for(ready, result):
    return gate.READY_PREFIX + json.dumps(ready) + '\n' + gate.RESULT_PREFIX + json.dumps(result) + '\n'


def accepted(ready, result, injected):
    return gate.check_log(log_for(ready,result), ready, injected, TOKEN, NONCE, PID)


def set_path(root, path, value):
    for key in path[:-1]:
        root = root[key]
    root[path[-1]] = value


class EvidenceTests(unittest.TestCase):
    def test_raw_valid_fixture_not_game_acceptance(self):
        self.assertTrue(accepted(*fixture())['valid'])

    def test_probe_passed_boolean_is_irrelevant(self):
        ready,result,injected = fixture()
        result['passed'] = False
        self.assertTrue(accepted(ready,result,injected)['valid'])
        result['passed'] = True
        result['after']['energy'] = 3
        self.assertFalse(accepted(ready,result,injected)['valid'])

    def test_identity_geometry_mutations(self):
        mutations = [(['token'],'stale'), (['nonce'],'b'*48), (['processId'],999), (['godotProcessId'],999),
                     (['pidSource'],'inferred'), (['gameVersion'],'v0.107.2'), (['gameCommit'],'wrong'),
                     (['testMode'],True), (['steamInitialized'],True), (['os'],'Linux'), (['display'],'headless'),
                     (['scenario'],'content'), (['variant'],'u07'), (['window','hwnd'],0),
                     (['window','size'],[1280,721]), (['window','position'],[999,999]), (['anchors','card','screen'],[900,900]),
                     (['anchors','target','nodeId'],0), (['readyTickMs'],20000),
                     (['fixtureApi'],'CardCmd.AutoPlay'), (['encounter'],'Synthetic'),
                     (['originalCardIds'],list(range(1,11))), (['cardId'],9), (['targetId'],104)]
        for path,value in mutations:
            with self.subTest(path=path):
                ready,result,injected = fixture()
                set_path(ready,path,value)
                self.assertFalse(accepted(ready,result,injected)['valid'])

    def test_native_payment_and_identity_mutations(self):
        mutations = [(['api'],'CardCmd.AutoPlay'), (['acceptance'],'effect-only-not-payment'),
                     (['after','energy'],3), (['after','pile'],'Hand'), (['after','cardId'],7),
                     (['after','masterIndex'],1), (['after','cardModel'],'Generated_B01'),
                     (['after','enemies',2,'hp'],43), (['after','enemies',0,'hp'],49),
                     (['after','enemies',2,'id'],102), (['after','piles','Hand'],[0]),
                     (['after','piles','Discard'],[6,7,8,9,9]), (['after','round'],2),
                     (['after','actionsDisabled'],True), (['after','upgraded'],True),
                     (['after','playerHp'],79), (['after','deck'],['Volibear_B01']),
                     (['history',0,'data','amount'],0), (['history',0,'data','amount'],True),
                     (['history',1,'data','isAutoPlay'],True), (['history',1,'data','energySpent'],0),
                     (['history',1,'data','energySpent'],True), (['history',1,'data','energyValue'],0),
                     (['history',1,'data','targetId'],101), (['history',1,'data','playCount'],2),
                     (['history',1,'data','starsSpent'],1), (['history',4,'data','isAutoPlay'],True),
                     (['history',0,'tickMs'],10000), (['history',1,'index'],0),
                     (['history',2,'data','cardId'],1), (['history',2,'data','hit','unblocked'],0),
                     (['history',3,'data','attackerId'],103)]
        for path,value in mutations:
            with self.subTest(path=path):
                ready,result,injected = fixture()
                set_path(result,path,value)
                self.assertFalse(accepted(ready,result,injected)['valid'])

    def test_actual_input_receipt_mutations(self):
        mutations = [(['token'],'wrong'), (['nonce'],'b'*48), (['processId'],9), (['hwnd'],999),
                     (['spawn','pid'],999), (['spawn','jobHandle'],0), (['error'],'focus lost'),
                     (['api'],'direct-GuiInput'), (['packets',0,'kind'],'keyboard'),
                     (['packets',1,'sent'],0), (['packets',1,'foregroundPid'],999),
                     (['packets',4,'foregroundHwnd'],999), (['packets',5,'pointHwnd'],999),
                     (['packets',6,'point'],[1100,340]), (['packets',7,'cursor'],[0,0]),
                     (['packets',8,'clientRect'],[101,100,1280,720]), (['packets',9,'flags'],1),
                     (['packets',10,'normalised'],[0,0]), (['packets',11,'tickMs'],1),
                     (['packets',-1,'tickMs'],20000)]
        for path,value in mutations:
            with self.subTest(path=path):
                ready,result,injected = fixture()
                set_path(injected,path,value)
                self.assertFalse(accepted(ready,result,injected)['valid'])

    def test_missing_duplicate_and_error_markers(self):
        ready,result,injected = fixture()
        text = log_for(ready,result)
        for malformed in ('', text + gate.RESULT_PREFIX + json.dumps(result), text+'MANUAL_PLAY_ERROR failure',
                          text.replace('MANUAL_PLAY_RESULT','OTHER_RESULT'), text+gate.RESULT_PREFIX+'{bad'):
            self.assertFalse(gate.check_log(malformed,ready,injected,TOKEN,NONCE,PID)['valid'])
        result['history'].append(copy.deepcopy(result['history'][1]))
        self.assertFalse(accepted(ready,result,injected)['valid'])

    def test_missing_or_reused_viewport_artifacts_fail(self):
        ready,result,injected = fixture()
        with tempfile.TemporaryDirectory(dir=ROOT/'.local') as path:
            directory = Path(path)
            self.assertFalse(gate.check_log(log_for(ready,result),ready,injected,TOKEN,NONCE,PID,directory)['valid'])
            for name in ('manual-before.png','manual-after.png'):
                (directory/name).write_bytes(png_bytes())
            self.assertFalse(gate.check_log(log_for(ready,result),ready,injected,TOKEN,NONCE,PID,directory)['valid'])
            (directory/'manual-after.png').write_bytes(png_bytes(rgb=(0,0,255)))
            self.assertTrue(gate.check_log(log_for(ready,result),ready,injected,TOKEN,NONCE,PID,directory)['valid'])


class PngTests(unittest.TestCase):
    def test_complete_rgb_and_rgba_decode_without_external_libraries(self):
        rgb = gate.validate_png(png_bytes(),1280,720)
        rgba = gate.validate_png(png_bytes(color=6),1280,720)
        self.assertEqual(len(rgb),64)
        self.assertNotEqual(rgb,rgba)
        self.assertNotEqual(rgb,gate.validate_png(png_bytes(rgb=(0,0,255)),1280,720))

    def test_bad_chunks_streams_filters_and_lengths_are_rejected(self):
        valid=png_bytes()
        raw=(b'\0'+b'\xff\0\0'*1280)*720
        ihdr=valid[8:33]
        compressed=zlib.compress(raw)
        bad=[valid[:7], valid[:-1], valid+b'garbage', valid[:-1]+bytes([valid[-1]^1]),
             PNG_SIGNATURE+ihdr+ihdr+valid[33:],
             PNG_SIGNATURE+png_chunk(b'IDAT',compressed)+png_chunk(b'IEND',b''),
             PNG_SIGNATURE+ihdr+png_chunk(b'ABCD',b'')+valid[33:],
             PNG_SIGNATURE+ihdr+png_chunk(b'IDAT',compressed[:5])+png_chunk(b'tEXt',b'x\0y')+
                png_chunk(b'IDAT',compressed[5:])+png_chunk(b'IEND',b''),
             png_bytes(depth=16), png_bytes(color=3),
             png_bytes(raw=b'\x05'+raw[1:]), png_bytes(raw=raw[:-1]), png_bytes(raw=raw+b'\0'),
             png_bytes(compressed=b'not zlib'), png_bytes(compressed=compressed[:-1]),
             png_bytes(compressed=compressed+b'junk')]
        for index,content in enumerate(bad):
            with self.subTest(mutation=index):
                with self.assertRaises(gate.EvidenceError): gate.validate_png(content,1280,720)
        with self.assertRaises(gate.EvidenceError): gate.validate_png(valid,1281,720)


class FakeApi:
    def __init__(self, foreign_at=None):
        self.position = [0,0]
        self.sent = []
        self.clock = 10010
        self.verifications = 0
        self.foreign_at = foreign_at
        self.button_held = False
    def tick(self): return self.clock
    def cursor(self): return self.position[:]
    def left_down(self): return self.button_held
    def verify(self, ready, process, point):
        self.verifications += 1
        if self.foreign_at is not None and self.verifications >= self.foreign_at:
            raise gate.EvidenceError('foreign foreground')
        return dict(foregroundHwnd=HWND,foregroundPid=PID,pointHwnd=HWND,clientRect=[100,100,1280,720],outerRect=[100,100,1280,720])
    def send(self,kind,point,tag):
        self.sent.append((kind,point,tag))
        self.position = point[:]
        self.clock += 15
        return dict(kind=kind,point=point,flags={'move':gate.MOVE_FLAGS,'down':2,'up':4}[kind],sent=1,
                    tickMs=self.clock,virtualScreen=[0,0,1920,1080],
                    normalised=[round(point[0]*65535/1919),round(point[1]*65535/1079)],cursor=point[:])


class NoWait:
    def is_set(self): return False
    def wait(self, seconds): return False


class InjectorTests(unittest.TestCase):
    def owned(self):
        return SimpleNamespace(job=789, process=SimpleNamespace(pid=PID,poll=lambda:None))
    def test_exact_single_drag_no_real_win32(self):
        ready,_,_ = fixture()
        api,receipt = FakeApi(), {'packets':[]}
        runner.inject_drag(api,ready,self.owned(),receipt,NoWait())
        self.assertEqual([k for k,_,_ in api.sent], ['move','down']+['move']*24+['up'])
        self.assertEqual(api.sent[0][1],[700,700])
        self.assertEqual(api.sent[-1][1],[1100,340])
        self.assertEqual(len(receipt['packets']),27)
    def test_foreign_foreground_at_every_packet_stops_input(self):
        ready,_,_ = fixture()
        for failing_packet in range(1,28):
            with self.subTest(packet=failing_packet):
                api,receipt = FakeApi(failing_packet), {'packets':[]}
                with self.assertRaises(gate.EvidenceError):
                    runner.inject_drag(api,ready,self.owned(),receipt,NoWait())
                self.assertEqual(len(api.sent),failing_packet-1)
                self.assertNotIn('cleanupRelease',receipt)
    def test_existing_button_and_missing_job_refuse_all_input(self):
        ready,_,_ = fixture()
        api = FakeApi()
        api.button_held = True
        with self.assertRaises(gate.EvidenceError): runner.inject_drag(api,ready,self.owned(),{'packets':[]},NoWait())
        self.assertEqual(api.sent,[])
        api.button_held = False
        owned = self.owned(); owned.job = None
        with self.assertRaises(gate.EvidenceError): runner.inject_drag(api,ready,owned,{'packets':[]},NoWait())
        self.assertEqual(api.sent,[])
    def test_stale_manifest_refuses_all_input(self):
        ready,_,_ = fixture()
        api = FakeApi(); api.clock = ready['readyTickMs']+10001
        with self.assertRaises(gate.EvidenceError): runner.inject_drag(api,ready,self.owned(),{'packets':[]},NoWait())
        self.assertEqual(api.sent,[])
    def test_background_launch_refused_before_any_native_api(self):
        errors=[]
        def attempt():
            try: runner.run_case(Path('does-not-exist'))
            except gate.EvidenceError as error: errors.append(str(error))
        thread=threading.Thread(target=attempt); thread.start(); thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors,['headless.launch must run on main thread'])
    def test_watcher_forged_token_aborts_without_input(self):
        ready,_,_=fixture(); ready['token']='foreign'
        event=threading.Event(); event.set()
        aborted=[]
        owned=SimpleNamespace(event=event,process=SimpleNamespace(pid=PID,poll=lambda:None),job=789,abort=lambda:aborted.append(True))
        with tempfile.TemporaryDirectory(dir=ROOT/'.local') as directory:
            Path(directory,'manual-ready.json').write_text(json.dumps(ready),encoding='utf-8')
            api=FakeApi()
            watcher=runner.InputWatcher(api,Path(directory),TOKEN,NONCE,owned,1,threading.Event())
            watcher.run()
            self.assertEqual(api.sent,[])
            self.assertTrue(aborted)
            self.assertIn('ready.token',watcher.receipt['error'])


class FakeUser32:
    def __init__(self):
        self.foreground=HWND; self.window_pid=PID; self.hit=HWND; self.width=1280; self.origin=[100,100]
    def IsWindow(self,h): return True
    def IsWindowVisible(self,h): return True
    def IsIconic(self,h): return False
    def GetForegroundWindow(self): return self.foreground
    def GetWindowThreadProcessId(self,h,out):
        ctypes.cast(out,ctypes.POINTER(wintypes.DWORD)).contents.value=self.window_pid if h==HWND else 999
        return 1
    def GetClientRect(self,h,out):
        r=ctypes.cast(out,ctypes.POINTER(wintypes.RECT)).contents
        r.left=r.top=0; r.right=self.width; r.bottom=720
        return True
    def GetWindowRect(self,h,out):
        r=ctypes.cast(out,ctypes.POINTER(wintypes.RECT)).contents
        r.left=92; r.top=69; r.right=1388; r.bottom=828
        return True
    def ClientToScreen(self,h,out):
        p=ctypes.cast(out,ctypes.POINTER(wintypes.POINT)).contents
        p.x,p.y=self.origin
        return True
    def WindowFromPoint(self,p): return self.hit
    def GetAncestor(self,h,flag): return h


class WindowGuardTests(unittest.TestCase):
    def test_real_guard_logic_with_pure_mock_win32(self):
        ready,_,_=fixture()
        native=runner.WinMouse.__new__(runner.WinMouse); native.user=FakeUser32()
        process=SimpleNamespace(pid=PID,poll=lambda:None)
        self.assertEqual(native.verify(ready,process,[700,700])['foregroundPid'],PID)
        for field,value in [('foreground',999),('window_pid',999),('hit',999),('width',1281),('origin',[150,100])]:
            with self.subTest(field=field):
                native.user=FakeUser32(); setattr(native.user,field,value)
                with self.assertRaises(gate.EvidenceError): native.verify(ready,process,[700,700])
        native.user=FakeUser32()
        with self.assertRaises(gate.EvidenceError): native.verify(ready,process,[99,99])
        with self.assertRaises(gate.EvidenceError): native.verify(ready,SimpleNamespace(pid=PID,poll=lambda:0),[700,700])

    def test_probe_has_no_replacement_input_or_payment_route(self):
        staged=Path(__file__).with_name('ManualPlayProbe.cs')
        source=(staged if staged.exists() else ROOT/'src/Volibear/ManualPlayProbe.cs').read_text(encoding='utf-8')
        for forbidden in ('CardCmd.AutoPlay(', 'new PlayCardAction', 'PlayCardAction.Create(',
                          '.OnGuiInput(', 'Input.ParseInputEvent(', 'PlayerCmd.SetEnergy(',
                          '.SpendResources(', '.PayEnergy('):
            self.assertNotIn(forbidden,source)
        self.assertIn('play.Resources.EnergySpent',source)
        self.assertIn('play.IsAutoPlay',source)
        self.assertIn('System.Environment.TickCount64',source)
        self.assertIn('Anchor(inputHolder!.Hitbox',source)
        self.assertIn('targetNode.Hitbox',source)
        script=Path(runner.__file__).read_text(encoding='utf-8')
        import ast
        focus_call_owners = [function.name for function in ast.walk(ast.parse(script))
                             if isinstance(function, ast.FunctionDef)
                             for call in ast.walk(function) if isinstance(call, ast.Call)
                             and isinstance(call.func, ast.Attribute) and call.func.attr == 'SetForegroundWindow']
        self.assertEqual(focus_call_owners, ['activate_owned'])
        for forbidden in ('SetCursorPos', 'AttachThreadInput', 'SetWindowPos', 'BringWindowToTop', 'AllowSetForegroundWindow'):
            self.assertNotIn(forbidden,script)
        self.assertIn('headless.prepare_run(',script)
        self.assertIn('headless.launch(',script)


class NativeAnchorContractTests(unittest.TestCase):
    """Source boundaries only; real layout/targeting remains a native-window acceptance gate."""
    def source(self):
        return (ROOT/'src/Volibear/ManualPlayProbe.cs').read_text(encoding='utf-8')

    def test_uses_bound_native_input_hitbox_without_bypassing_visibility(self):
        source=self.source()
        for required in ('room.Ui.Hand.GetCardHolder(card)', 'ReferenceEquals(inputHolder.CardNode, cardNode)',
                         'ReferenceEquals(inputHolder.CardModel, card)', 'Anchor(inputHolder!.Hitbox',
                         'NHandCardHolder.Hitbox.MousePressed', 'NCreature.Hitbox.MouseEntered',
                         '!node.IsVisibleInTree()', 'NClickableControl { IsEnabled: false }',
                         'Control.MouseFilterEnum.Ignore'):
            self.assertIn(required,source)
        for forbidden in ('Anchor(cardNode.Body)', '.SetEnabled(', '.SetClickable(', '.Show()', '.Visible ='):
            self.assertNotIn(forbidden,source)

    def test_clips_to_actual_visible_input_region_and_waits_for_layout(self):
        source=self.source()
        for required in ('Intersection(node.GetViewport().GetVisibleRect().Grow(-8))',
                         'Control { ClipContents: true }', 'AffineInverse() * viewportPoint',
                         'new Rect2(Vector2.Zero, node.Size).HasPoint(local)',
                         'clips.All(', 'stableSamples >= 3', '}, 8, "Native hand/enemy input regions'):
            self.assertIn(required,source)
        self.assertNotIn('await Pause(0.8)',source)

    def test_role_diagnostics_and_failure_image_do_not_hide_failure(self):
        source=self.source()
        for required in ('MANUAL_ANCHOR_DIAGNOSTIC ', 'card-visual-body', 'card-holder',
                         'card-input-hitbox', 'enemy-input-hitbox', 'visibleInTree =',
                         'globalRect =', 'viewportRect =', 'mouseFilter =', 'ancestors',
                         'diagnose("before-layout")', 'diagnose("layout-stable")',
                         'diagnose?.Invoke("failure")', '"manual-failure.png"',
                         'MANUAL_PLAY_ERROR ', 'MANUAL_FAILURE_CAPTURE_ERROR ',
                         '((SceneTree)Engine.GetMainLoop()).Quit(2)'):
            self.assertIn(required,source)


class BootstrapRoutingTests(unittest.TestCase):
    def test_manual_case_routes_bootstrap_to_owned_window_launcher(self):
        from contextlib import ExitStack
        from unittest.mock import MagicMock, patch
        directory = MagicMock(name='ignored_artifact_directory')
        base_command = ['owned-game.exe', '--force-steam=off', '--quit-after', '10000']
        prepared_env = {'VOLIBEAR_TEST_TOKEN': TOKEN, 'VOLIBEAR_TEST_DATA_ROOT': 'isolated-profile'}
        watcher = MagicMock(name='mocked_input_watcher')
        watcher.is_alive.return_value = False
        watcher.ready = {}
        watcher.receipt = {'packets': [], 'error': None}
        captured = {}

        def launch(game, path, env, command, timeout):
            captured.update(game=game, path=path, env=dict(env), command=list(command), timeout=timeout,
                            thread=threading.current_thread())
            return 0, False

        with ExitStack() as stack:
            win = stack.enter_context(patch.object(runner, 'WinMouse', return_value=object()))
            stack.enter_context(patch.object(runner, 'InputWatcher', return_value=watcher))
            stock = stack.enter_context(patch.object(runner.headless, 'stock_teardown',
                                                    return_value=(set(), {'successful': True})))
            prepare = stack.enter_context(patch.object(runner.headless, 'prepare_run',
                                                      return_value=(directory, prepared_env, base_command)))
            stack.enter_context(patch.object(runner.headless, 'new_run_id', return_value=TOKEN))
            stack.enter_context(patch.object(runner.secrets, 'token_hex', return_value=NONCE))
            launcher = stack.enter_context(patch.object(runner.headless, 'launch', side_effect=launch))
            spawn = stack.enter_context(patch.object(runner.headless, 'spawn_owned',
                                                    side_effect=AssertionError('No real process permitted in routing test')))
            stack.enter_context(patch.object(runner.headless, 'combined_log',
                                            return_value='[Volibear] SHUTDOWN_BEGIN ' + TOKEN))
            stack.enter_context(patch.object(runner.headless, 'evaluate', return_value={'mock_runtime': True}))
            stack.enter_context(patch.object(runner, 'check_log', return_value={'valid': True}))
            stack.enter_context(patch.object(runner.subprocess, 'check_output', side_effect=['mock-commit', b'']))
            runner.run_case(Path('owned-game-directory'), 90, 50, 10000)
            win.assert_called_once()
            stock.assert_called_once_with(Path('owned-game-directory'), 90, 10000, 'window')
            prepare.assert_called_once_with(Path('owned-game-directory'), TOKEN, 10000, 'window')
            launcher.assert_called_once()
            spawn.assert_not_called()

        self.assertEqual(captured['command'].count('--bootstrap'), 1)
        self.assertIn('--force-steam=off', captured['command'])
        self.assertNotIn('--headless', captured['command'])
        self.assertNotIn('Dummy', captured['command'])
        self.assertEqual(captured['env']['VOLIBEAR_TEST_SCENARIO'], 'manual-play')
        self.assertEqual(captured['env']['VOLIBEAR_TEST_CHARACTER'], 'volibear')
        self.assertEqual(captured['env']['VOLIBEAR_TEST_TOKEN'], TOKEN)
        self.assertEqual(captured['env']['VOLIBEAR_MANUAL_INPUT_NONCE'], NONCE)
        self.assertEqual(captured['env']['VOLIBEAR_TEST_DATA_ROOT'], 'isolated-profile')
        self.assertIs(captured['thread'], threading.main_thread())
        watcher.start.assert_called_once()
        watcher.join.assert_called_once_with(timeout=3)


if __name__ == '__main__':
    unittest.main()
