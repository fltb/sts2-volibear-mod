from pathlib import Path
import os
root=Path(__file__).resolve().parents[1]
for name,var,source in [('viewer_data.js','V9_DATA','manifest.json'),('parts_data.js','V9_RIG','rig.json')]:
 p=root/name;t=p.with_name('.'+name+'.tmp');t.write_text('window.'+var+'='+ (root/source).read_text()+';\n');os.replace(t,p)
