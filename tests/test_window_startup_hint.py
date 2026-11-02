"""Tool-only preload ABI checks using a fake X11 library; no window/game starts."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import headless as h

FAKE_X11 = r'''
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
static int writes;
Atom XInternAtom(Display *d, const char *name, Bool only) {
    if (!strcmp(name,"_NET_WM_WINDOW_TYPE_NORMAL")) return 101;
    if (!strcmp(name,"_NET_WM_WINDOW_TYPE")) return 102;
    if (!strcmp(name,"_NET_WM_PID")) return 103;
    if (!strcmp(name,"_NET_WM_USER_TIME")) return 104;
    abort();
}
int XGetWindowProperty(Display *d, Window w, Atom prop, long off, long len, Bool del,
    Atom requested, Atom *type, int *format, unsigned long *n, unsigned long *remaining, unsigned char **data) {
    *type=prop==102?XA_ATOM:XA_CARDINAL; *format=32; *n=1; *remaining=0;
    unsigned long *value=malloc(sizeof(*value)); *value=prop==102?101:(unsigned long)getpid();
    *data=(unsigned char *)value; return Success;
}
int XChangeProperty(Display *d, Window w, Atom prop, Atom type, int format, int mode, const unsigned char *data, int n) {
    if(prop!=104 || type!=XA_CARDINAL || format!=32 || n!=1 || *(unsigned long *)data!=0) abort();
    ++writes; return 1;
}
int XFree(void *p) { free(p); return 1; }
int XMapWindow(Display *d, Window w) {
    if(writes!=atoi(getenv("EXPECT_HINT"))) abort();
    printf("FAKE_MAP writes=%d\n",writes); return 73;
}
'''
CLIENT = r'''
#include <dlfcn.h>
#include <stdlib.h>
int main(int argc,char **argv) {
    void *handle=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL); if(!handle) return 11;
    int (*map)(void *,unsigned long)=dlsym(handle,"XMapWindow"); if(!map) return 12;
    if(map(0,42)!=73 || map(0,42)!=73) return 13;
    return 0;
}
'''


class StartupHintRouting(unittest.TestCase):
    def test_missing_compiler_fails_instead_of_activating_fallback(self):
        if not sys.platform.startswith('linux') or os.uname().machine != 'x86_64':
            self.skipTest('Linux x86_64 tool')
        with patch.object(h.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'cc is required'):
                h.build_window_startup_hint()

    def test_child_only_environment_preserves_parent_and_other_modes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game = root / '.local/game'
            game.mkdir(parents=True)
            exe = game / 'game'
            env = {'LD_PRELOAD': '/existing.so'}
            command = [str(exe), '--windowed', '--display-driver', 'x11']
            with patch.object(h, 'ROOT', root), patch.object(h, 'game_executable', return_value=exe), patch.object(h, 'build_window_startup_hint', return_value=root/'hint.so'):
                child = h.window_startup_environment(command, game, env)
                self.assertEqual(child['LD_PRELOAD'], str(root/'hint.so') + ':/existing.so')
                self.assertEqual(child['VOLIBEAR_X11_STARTUP_HINT_EXE'], str(exe))
                self.assertEqual(env, {'LD_PRELOAD': '/existing.so'})
                self.assertIs(h.window_startup_environment(['game','--headless'], game, env), env)
                with self.assertRaisesRegex(RuntimeError, 'owned isolated'):
                    h.window_startup_environment(command, root, env)

    @unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('cc'), 'Linux C compiler ABI fixture')
    def test_real_dlopen_dlsym_pre_map_once_and_unrelated_executable_untouched(self):
        hint = h.build_window_startup_hint()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake = root/'fake.c'; fake.write_text(FAKE_X11)
            client = root/'client.c'; client.write_text(CLIENT)
            library = root/'fake.so'; exe = root/'client'
            subprocess.run(['cc','-shared','-fPIC',str(fake),'-o',str(library)],check=True,capture_output=True)
            subprocess.run(['cc',str(client),'-o',str(exe),'-ldl'],check=True,capture_output=True)
            for enabled in (True, False):
                env = dict(os.environ, LD_PRELOAD=str(hint), EXPECT_HINT='1' if enabled else '0',
                           VOLIBEAR_X11_STARTUP_HINT_EXE=str(exe) if enabled else '/different/process')
                result = subprocess.run([str(exe),str(library)],env=env,capture_output=True,text=True,timeout=5)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(result.stdout.count('FAKE_MAP writes='+env['EXPECT_HINT']),2)
                self.assertEqual(result.stderr.count('WINDOW_STARTUP_HINT before_map'),int(enabled))


if __name__ == '__main__':
    unittest.main()
