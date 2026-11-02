#!/usr/bin/env python3
"""Copy only runtime atlases/audio into a Godot project's VolibearArt resource folder.
No game is launched, no DLL is produced, no Workshop upload occurs.
"""
from pathlib import Path
import argparse, hashlib, json, shutil

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def icon_runtime_paths(row):
    paths = [version['path'] for version in row['files'].values()]
    if row.get('editable_svg'):
        paths.append(row['editable_svg'])
    elif not row.get('raster_source'):
        raise ValueError('Icon requires editable_svg or raster_source: ' + row['id'])
    # Painted icons ship their raster exports, not old SVGs or authoring masters.
    return paths

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True,help='Destination Godot project resource directory ending in VolibearArt')
    args=ap.parse_args()
    repo=Path(__file__).resolve().parent.parent
    dest=args.output.resolve()
    if dest.name!='VolibearArt': raise SystemExit('Output directory must be named VolibearArt')
    if dest.exists() and any(dest.iterdir()): raise SystemExit('Choose an empty output directory to avoid retaining obsolete assets')
    dest.mkdir(parents=True,exist_ok=True)
    copied=[]; input_manifests={}
    sources={'animations':repo/'animations'/'clean','vfx':repo/'vfx','audio':repo/'audio','ui':repo/'ui'}
    if not (sources['animations']/'manifest.json').is_file():
        raise SystemExit('Missing clean animation atlas set; refusing to stack new VFX over baked-VFX animation')
    def copy(folder,rel):
        path=Path(rel)
        if path.is_absolute() or '..' in path.parts: raise ValueError(f'Unsafe asset path: {rel}')
        src=sources[folder]/path; out=dest/folder/path
        before=sha(src)
        out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out)
        actual=sha(out)
        if actual!=before or sha(src)!=before:raise RuntimeError(f'Source changed while staging: {src}')
        copied.append({'file':out.relative_to(dest).as_posix(),'bytes':out.stat().st_size,'sha256':actual})
    for folder in ('animations','vfx','audio','ui'):
        manifest=sources[folder]/'manifest.json'
        if not manifest.is_file():raise SystemExit(f'Missing final {manifest}')
        input_manifests[str(manifest)]=sha(manifest)
        m=json.loads(manifest.read_text())
        if folder=='animations':
            if not m.get('render_complete'):raise SystemExit('Animation render is not complete')
            for row in m.get('clips',[])+m.get('variants',[]):
                copy(folder,row['atlas']['image']);copy(folder,row['atlas']['json'])
                row.pop('frames',None);row.pop('preview',None)
            m.pop('source_integrity',None)
        elif folder=='vfx':
            for row in m['effects']:
                copy(folder,row['atlas']['image']);copy(folder,row['atlas']['json'])
                for f in row.get('frames',[]):f.pop('path',None)
        elif folder=='audio':
            seen=set()
            for row in m['cues']:
                if row['file'] not in seen:copy(folder,row['file']);seen.add(row['file'])
                row.pop('wav',None)
        else:
            for row in m['assets']:copy(folder,row['file'])
        m['staging']={'storage':'runtime_atlases_ogg_and_ui','source_manifest_sha256':sha(manifest),'notes':'Raw drawing frames, proofs, WAV masters and source files remain in the authoring repository.'}
        out=dest/folder/'manifest.json';out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
        copied.append({'file':out.relative_to(dest).as_posix(),'bytes':out.stat().st_size,'sha256':sha(out)})
    for folder,name in [('audio','action_cues.json'),('vfx','card_vfx_bindings.json')]:
        if (repo/folder/name).is_file():
            input_manifests[str(repo/folder/name)]=sha(repo/folder/name)
            copy(folder,name)
    icon_manifest=repo/'vfx/icons/manifest.json'
    if icon_manifest.is_file():
        input_manifests[str(icon_manifest)]=sha(icon_manifest)
        icons=json.loads(icon_manifest.read_text())
        copy('vfx','icons/manifest.json')
        for row in icons['icons']:
            for path in icon_runtime_paths(row):copy('vfx',path)
    for path,expected in input_manifests.items():
        if sha(Path(path))!=expected:raise RuntimeError(f'Input manifest changed during staging: {path}')
    report={'scope':'Runtime resource staging only; not a compiled or game-tested mod','input_manifest_sha256':input_manifests,'files':copied,'file_count':len(copied),'total_bytes':sum(r['bytes'] for r in copied)}
    (dest/'STAGED_ASSETS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(dest),'files':len(copied),'bytes':report['total_bytes']}))

if __name__=='__main__':main()
