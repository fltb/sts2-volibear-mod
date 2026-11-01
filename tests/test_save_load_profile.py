"""Synthetic fixture/isolation controls; no game launches or native evidence edits."""
import copy
import ctypes
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import save_load_profile as p
import save_load_pair as runner
import save_load_evidence as gate
from test_save_load_evidence import fixture


class ShortOwnedProfileTests(unittest.TestCase):
    def test_unique_absolute_fixed_owned_roots(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(p,'ROOT',Path(directory)):
            a=p.create_owned_profile();b=p.create_owned_profile()
            self.assertTrue(a.is_absolute() and a.is_dir() and b.is_dir());self.assertNotEqual(a,b)
            self.assertEqual(a.parent,Path(directory).resolve()/'.local/p');self.assertRegex(a.name,r'^[0-9a-f]{12}$')
    def test_no_arbitrary_profile_argument(self):
        with self.assertRaises(TypeError):p.create_owned_profile(Path('ordinary-profile'))
    def test_collision_does_not_reuse_or_modify_existing(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(p,'ROOT',Path(directory)),patch.object(p.uuid,'uuid4',return_value=SimpleNamespace(hex='a'*32)):
            existing=p.create_owned_profile();marker=existing/'keep.txt';marker.write_text('untouched',encoding='utf-8')
            with self.assertRaises(FileExistsError):p.create_owned_profile()
            self.assertEqual(marker.read_text(encoding='utf-8'),'untouched')
    def test_reparse_parent_rejected_without_repair(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(p,'ROOT',Path(directory)):
            original=Path.lstat
            def observe(path,*args,**kwargs):
                if path==Path(directory).resolve()/'.local':return SimpleNamespace(st_mode=stat.S_IFDIR,st_file_attributes=0x400)
                return original(path,*args,**kwargs)
            with patch.object(Path,'lstat',observe):
                with self.assertRaisesRegex(ValueError,'reparse'):p.create_owned_profile()
    def test_long_workspace_fails_before_profile_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/('x'*100);root.mkdir()
            with patch.object(p,'ROOT',root),patch.object(p.h,'IS_WINDOWS',True):
                with self.assertRaisesRegex(ValueError,'shader-directory budget'):p.create_owned_profile()
            self.assertFalse((root/'.local').exists())
    def test_utf16_prefix_terminator_and_boundary(self):
        root='C:/'+('x'*90)+'😀'*10
        budget=p.shader_directory_budget(root)
        self.assertTrue(budget['directory'].startswith('\\\\?\\'))
        self.assertEqual(budget['utf16_units_with_terminator'],len(budget['directory'])+10+2)
        with patch.object(p,'shader_directory_budget',return_value=dict(utf16_units_with_terminator=260)):
            with self.assertRaises(ValueError):p.require_shader_directory_budget('unused')
        with patch.object(p,'shader_directory_budget',return_value=dict(utf16_units_with_terminator=259)):
            self.assertEqual(p.require_shader_directory_budget('unused')['utf16_units_with_terminator'],259)
    def test_original_nested_profile_exceeds_budget(self):
        old=ROOT/'artifacts/save-load/20261031T235541Z-4c947dc3/profile/appdata/SlayTheSpire2'
        # Pure length calculation: never reads/writes the old profile.
        if sys.platform=='win32':
            with self.assertRaises(ValueError):p.require_shader_directory_budget(old)
    @unittest.skipUnless(sys.platform=='win32','native Windows chdir regression')
    def test_native_prefixed_chdir_succeeds_twice_with_cache_retained(self):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.SetCurrentDirectoryW.argtypes=[ctypes.c_wchar_p];kernel.SetCurrentDirectoryW.restype=ctypes.c_int
        original=os.getcwd()
        with tempfile.TemporaryDirectory() as directory,patch.object(p,'ROOT',Path(directory)):
            profile=p.create_owned_profile();user_root=p.h.user_data_root(profile)
            target=user_root/'shader_cache'/p.PINNED_LONGEST_SHADER/('a'*64);target.mkdir(parents=True)
            marker=target/'retained.txt';marker.write_text('cache retained',encoding='utf-8')
            extended='\\\\?\\'+str(target)
            try:
                for phase in ('prepare','resume'):
                    ctypes.set_last_error(0)
                    self.assertEqual(kernel.SetCurrentDirectoryW(extended),1,(phase,ctypes.get_last_error()))
                    self.assertEqual(kernel.SetCurrentDirectoryW(original),1)
            finally:kernel.SetCurrentDirectoryW(original)
            self.assertEqual(marker.read_text(encoding='utf-8'),'cache retained')
    def test_wrong_root_seed_pid_token_still_rejected(self):
        for field,value in [('userRoot','C:/ordinary'),('checkpointPath','C:/ordinary/current_run.save'),('seed','wrong'),('pid',999),('token','stale')]:
            with self.subTest(field=field):
                raw,expected=fixture(case='S1');raw[field]=value
                self.assertFalse(gate.validate_phase(raw,expected))
    def test_runner_two_phases_use_identical_owned_environment(self):
        # Native launches are replaced with synthetic reports/bytes inside this test's
        # TemporaryDirectory. This proves wiring only, never engine acceptance.
        calls=[]
        def fake_phase(game,pair_dir,env,case,mode,phase,seed,stock,stock_evidence,timeout,frames,display):
            calls.append(copy.deepcopy(env));user_root=Path(env['VOLIBEAR_TEST_DATA_ROOT'])
            path=user_root/'default/1/modded/profile1/saves/current_run.save'
            raw,expected=fixture(case=case,mode=mode,phase=phase,pid=11 if phase=='prepare' else 22,token=phase+'-token')
            for record in (raw,expected):record.update(pair=pair_dir.name,userRoot=str(user_root),checkpointPath=str(path),seed=seed)
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(raw['afterMenu' if phase=='prepare' else 'afterLoad']),encoding='utf-8')
            checks={k:True for k in ('exited_zero','steam_disabled','no_cloud_backend','no_runtime_errors','mod_initialized','runtime_isolation',
                'teardown_matches_stock','stock_control_success','save_lifecycle','disk_checkpoint_matches_raw')}
            return dict(raw=raw,expected=expected,checks=checks,passed=True)
        with tempfile.TemporaryDirectory() as directory,patch.object(p,'ROOT',Path(directory)),patch.object(runner,'ROOT',Path(directory)),\
            patch.object(runner.h,'validate_game'),patch.object(runner.h,'stock_teardown',return_value=('',dict(successful=True,exit_code=0,timed_out=False))),\
            patch.object(runner,'launch_phase',side_effect=fake_phase),patch.dict(os.environ,{'VOLIBEAR_TEST_TOKEN':'stale','VOLIBEAR_SAVE_PHASE':'stale'}):
            report=runner.run_pair(Path('not-a-game'),'S1','restart',display='headless')
            self.assertTrue(report['passed']);self.assertEqual(len(calls),2);self.assertEqual(calls[0],calls[1])
            self.assertNotIn('VOLIBEAR_TEST_TOKEN',calls[0]);self.assertNotIn('VOLIBEAR_SAVE_PHASE',calls[0])
            self.assertEqual(report['userRoot'],calls[0]['VOLIBEAR_TEST_DATA_ROOT'])
            descriptor=json.loads((Path(directory)/'artifacts/save-load'/report['pair']/'profile.json').read_text(encoding='utf-8'))
            self.assertEqual(descriptor['profile'],report['profile']);self.assertEqual(descriptor['userRoot'],report['userRoot'])
            for phase in report['phases']:
                self.assertEqual(phase['expected']['checkpointPath'],descriptor['checkpointPath'])
                self.assertEqual(phase['raw']['userRoot'],descriptor['userRoot'])
            self.assertTrue(Path(report['profile']).is_dir()) # runner did not automatically delete the evidence

if __name__=='__main__':unittest.main()
