#!/usr/bin/env python3
"""Stage, import, export and independently mount-test a namespaced Godot art PCK.
Requires the caller's Godot 4.5.1 executable. Does not compile/register/publish a game mod.
All engine import writes go to a fresh temporary project, never the authoring assets.
"""
from pathlib import Path
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--godot',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    godot=args.godot.resolve();output=args.output.resolve()
    if not godot.is_file():raise SystemExit('Godot executable does not exist')
    if output.suffix.lower()!='.pck':raise SystemExit('Output must end in .pck')
    if output.exists():raise SystemExit('Choose a new output path; existing resource pack is not overwritten')
    output.parent.mkdir(parents=True,exist_ok=True)
    here=Path(__file__).resolve().parent
    logs=[];commands=[]
    with tempfile.TemporaryDirectory(prefix='volibear_v5_pack_') as work_name:
        work=Path(work_name);build=work/'build';verify=work/'verify'
        build.mkdir();verify.mkdir()
        env=os.environ.copy()
        # These are task-local paths; the user's HOME/profile is not modified.
        for key,part in [('XDG_DATA_HOME','data'),('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache')]:
            folder=work/'engine_profile'/part;folder.mkdir(parents=True,exist_ok=True);env[key]=str(folder)
        def run(label,argv):
            print(label,flush=True)
            result=subprocess.run([str(x) for x in argv],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            clean=re.sub(r'\x1b\[[0-9;]*m','',result.stdout)
            commands.append({'phase':label,'argv':[str(x) for x in argv],'exit_code':result.returncode})
            logs.append('## '+label+'\n'+clean)
            if result.returncode:
                (output.with_suffix('.build.log')).write_text('\n'.join(logs))
                raise RuntimeError(f'{label} failed with exit {result.returncode}; see {output.with_suffix(".build.log")}')
        run('Stage immutable runtime assets',[sys.executable,here/'stage_assets.py','--output',build/'VolibearArt'])
        staged=json.loads((build/'VolibearArt/STAGED_ASSETS.json').read_text())
        project='config_version=5\n[application]\nconfig/name="Volibear V5 resource pack"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        (build/'project.godot').write_text(project)
        resource_paths=sorted('res://VolibearArt/'+x['file'] for x in staged['files'] if Path(x['file']).suffix.lower() in {'.png','.ogg','.svg'})
        preset=(here/'export_presets.cfg').read_text().replace('export_filter="all_resources"','export_filter="resources"\nexport_files=PackedStringArray('+', '.join(json.dumps(x) for x in resource_paths)+')')
        (build/'export_presets.cfg').write_text(preset)
        run('Import assets in isolated Godot project',[godot,'--headless','--editor','--path',build,'--import'])
        temporary_pack=work/'VolibearArt_v5.pck'
        run('Export resource PCK',[godot,'--headless','--path',build,'--export-pack','AssetPack',temporary_pack])
        if not temporary_pack.is_file() or temporary_pack.stat().st_size==0:raise RuntimeError('Engine did not create a resource pack')
        (verify/'project.godot').write_text(project.replace('resource pack','isolated pack verification'))
        shutil.copy2(here/'verify_asset_pack.gd',verify/'verify_asset_pack.gd')
        verification_report=work/'verification.json'
        run('Mount and decode PCK in separate empty project',[godot,'--headless','--path',verify,'--script','verify_asset_pack.gd','--',temporary_pack,verification_report])
        verification=json.loads(verification_report.read_text())
        if not verification.get('passed'):raise RuntimeError('Pack verifier failed')
        # Do not certify a pack if any frozen input manifest changed during the build.
        for path,expected in staged['input_manifest_sha256'].items():
            if sha(path)!=expected:raise RuntimeError(f'Source changed during pack build: {path}')
        temp_output=output.with_name(output.name+'.building')
        shutil.copy2(temporary_pack,temp_output);os.replace(temp_output,output)
        report={'scope':'Resources only; not a registered, compiled or game-tested STS2 mod','pack_file':output.name,'pack_bytes':output.stat().st_size,'pack_sha256':sha(output),'input_manifest_sha256':staged['input_manifest_sha256'],'build_source_sha256':{name:sha(here/name) for name in ['build_asset_pack.py','stage_assets.py','verify_asset_pack.gd','export_presets.cfg']},'staged_files':staged['file_count'],'staged_bytes':staged['total_bytes'],'engine_verification':verification,'commands':commands,'build_log':output.with_suffix('.build.log').name}
        output.with_suffix('.report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        output.with_suffix('.build.log').write_text('\n'.join(logs))
        print(json.dumps({'output':str(output),'sha256':report['pack_sha256'],'bytes':report['pack_bytes'],'passed':True}),flush=True)

if __name__=='__main__':main()
