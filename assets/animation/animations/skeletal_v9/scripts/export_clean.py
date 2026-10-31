"""Promote verified skeletal atlases to the no-VFX runtime contract.

Preserve authored events/state rules; never invoke the historical renderer.
"""
from pathlib import Path
import copy
import hashlib
import json
import render as r
import export as exporter


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = json.loads((r.ROOT/'manifest.json').read_text())
    assert source['render_complete']
    assert source['render_input_sha256'] == exporter.fingerprint(exporter.inputs())
    clean = r.REPO/'animations/clean'
    old = json.loads((clean/'manifest.json').read_text())
    records = {c['name']: c for c in old['clips']+old.get('variants', [])}
    clips = source['clips']+source.get('variants', [])
    assert set(records) == {c['name'] for c in clips}
    # Preserve previous metadata for reproducibility before committing changes.
    backup = r.REPO/'reports/animation_revision_v10/clean_before_sector'
    backup.mkdir(parents=True, exist_ok=True)
    if not (backup/'manifest.json').exists():
        r.atomic(backup/'manifest.json', (clean/'manifest.json').read_bytes())
    prepared = []
    for clip in clips:
        name = clip['name']; prior = records[name]
        for key in ('frame_count', 'fps', 'duration', 'loop', 'skin'):
            assert clip[key] == prior[key], (name, key)
        assert len(clip['events']) == len(prior['events'])
        for a,b in zip(clip['events'],prior['events']):
            assert all(b.get(k)==v for k,v in a.items())
        meta_path = clean/prior['atlas']['json']
        data = json.loads(meta_path.read_text())
        if not (backup/(name+'.json')).exists():
            r.atomic(backup/(name+'.json'), meta_path.read_bytes())
        data['frames'] = clip['frames']
        data['pose_source'] = 'skeletal_v9 world bones; authored death retains legacy pose metadata'
        if name not in r.DEATH_ATLASES:
            poses=[]
            for i in range(clip['frame_count']):
                a,o,p = r.pose(name,i/clip['frame_count']); w=r.world(a,o)
                markers={}
                for side in ('near','far'):
                    for label,bone in [('shoulder','shoulder'),('elbow','elbow'),('hand','wrist'),('foot','ankle'),('ankle','ankle'),('knee','knee'),('hip','hip')]:
                        markers[side+'_'+label]=(w[bone+'_'+side][0]*(.46*512/768)+r.np.array([70,111])*512/768).round(3).tolist()
                for label,bone in [('root','root'),('torso','spine'),('head','head')]:
                    markers[label]=(w[bone][0]*(.46*512/768)+r.np.array([70,111])*512/768).round(3).tolist()
                poses.append({'frame':i,'time':i/24,'markers_px':markers,'channels':p})
            data['poses']=poses
            data['marker_semantics']='joint centers; foot aliases ankle, hand aliases wrist'
        rec=copy.deepcopy(prior);rec['frames']=clip['frames']
        prepared.append((clip,rec,data))
    # Mark incomplete before replacing any atlas; completed manifest is last.
    pending=copy.deepcopy(old);pending['render_complete']=False
    r.js(clean/'manifest.json',pending)
    for clip,rec,data in prepared:
        dest=clean/rec['atlas']['image']
        r.atomic(dest,(r.ROOT/clip['atlas']['image']).read_bytes())
        r.js(clean/rec['atlas']['json'],data)
        rec['atlas_sha256']=sha(dest)
        rec['atlas_json_sha256']=sha(clean/rec['atlas']['json'])
    result=copy.deepcopy(old)
    result.update(render_complete=True,art_revision='skeletal_sector_repair',render_input_sha256=source['render_input_sha256'],source_integrity=source['source_integrity'],source_skeletal_manifest_sha256=sha(r.ROOT/'manifest.json'),exporter_sha256=sha(Path(__file__)))
    current={rec['name']:rec for _,rec,_ in prepared}
    for group in ('clips','variants'):
        result[group]=[current[c['name']] for c in old.get(group,[])]
    r.js(clean/'manifest.json',result)
    print('Promoted clean atlases:',len(prepared),'sequences; engine playback unverified')

if __name__=='__main__':
    main()
