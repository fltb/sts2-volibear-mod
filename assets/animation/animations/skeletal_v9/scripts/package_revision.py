"""Package the V9 revision and all its rebuild inputs; verify actual extraction."""
from pathlib import Path
import hashlib, json, os, tempfile, zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    files = [p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.tmp']
    files += list((REPO / 'reports/animation_revision_v9').glob('*.json'))
    files += [REPO / p for p in ['references/identity/volibear_approved.png', 'animations/rig/motions.json', 'animations/source/revision_v3/mouth_half_edit.png', 'animations/source/revision_v2/mouth_open_edit.png']]
    files = sorted(set(files))
    entries = {str(p.relative_to(REPO)): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in files}
    dest = REPO / 'exports/Volibear_V9_editable_animation.zip'
    temp = dest.with_name('.' + dest.name + '.tmp')
    with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            z.write(p, str(p.relative_to(REPO)))
        z.writestr('PACKAGE_CONTENTS.json', json.dumps(entries, ensure_ascii=False, indent=2))
        z.writestr('START_HERE.html', '<!doctype html><meta charset="utf-8"><title>Volibear V9</title><h1>V9 关节返修动画包</h1><p>本包为独立动画返修与重建输入，不含历史 V5 声音、卡片和特效库。</p><p><a href="animations/skeletal_v9/index.html">打开动画与部件预览</a></p><p><a href="animations/skeletal_v9/previews/joint_demo.gif">打开三动作 GIF</a></p>')
    with tempfile.TemporaryDirectory(prefix='volibear-v9-verify-') as folder:
        with zipfile.ZipFile(temp) as z:
            assert z.testzip() is None
            z.extractall(folder)
        for name, meta in entries.items():
            p = Path(folder) / name
            assert p.stat().st_size == meta['bytes'] and sha(p) == meta['sha256'], name
    os.replace(temp, dest)
    report = {'file': str(dest.relative_to(REPO)), 'bytes': dest.stat().st_size, 'sha256': sha(dest), 'files_checked': len(entries), 'zip_crc': 'pass', 'actual_extraction_and_sha256': 'pass', 'scope': 'V9 animation revision plus all rebuild inputs; not a repack of the three historical full repositories'}
    p = dest.with_suffix('.validation.json'); t = p.with_suffix('.tmp')
    t.write_text(json.dumps(report, ensure_ascii=False, indent=2)); os.replace(t, p)
    print(json.dumps(report), flush=True)

if __name__ == '__main__':
    main()
