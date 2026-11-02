"""Focused native-reference hover test; never launches a game or release gate."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
config = json.loads((ROOT / '.local/config.json').read_text(encoding='utf-8'))
dotnet = Path(config['dotnet'])
data = Path(config['game_dir']) / ('data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64')
env = dict(os.environ, DOTNET_ROOT=str(dotnet.parent), DOTNET_NOLOGO='1', DOTNET_CLI_TELEMETRY_OPTOUT='1')
env['PATH'] = str(dotnet.parent) + os.pathsep + env.get('PATH', '')
result = subprocess.run([str(dotnet), 'run', '--project', str(Path(__file__).with_name('DomainDisabledPresentation.Tests.csproj')),
                         '-c', 'Release', '-p:Sts2DataDir=' + str(data)], cwd=ROOT, env=env, timeout=120)
sys.exit(result.returncode)
