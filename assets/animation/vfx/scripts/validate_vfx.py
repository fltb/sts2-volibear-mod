#!/usr/bin/env python3
"""Validate exported pixels and event references; does not award art approval."""
from pathlib import Path
import json,hashlib,math
import numpy as np
from PIL import Image,ImageSequence
from effects import SPECS
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    m=json.loads((ROOT/'manifest.json').read_text());bind=json.loads((ROOT/'card_vfx_bindings.json').read_text());icons=json.loads((ROOT/'icons/manifest.json').read_text())
    errors=[];rows=[]
    def check(cond,msg):
        if not cond:errors.append(msg)
    check(m['effect_count']==len(SPECS),'effect count')
    check(m['source_sha256']==sha(ROOT/'scripts/effects.py'),'source geometry fingerprint')
    ids={e['id'] for e in m['effects']};check(len(ids)==len(m['effects']),'duplicate effect ID')
    for e in m['effects']:
        aa=np.asarray(Image.open(ROOT/e['atlas']['image']).convert('RGBA'));frames=[];edge_count=0
        check(sha(ROOT/e['atlas']['image'])==e['atlas']['sha256'],e['id']+' atlas SHA')
        check(aa.shape==(256*e['atlas']['rows'],2048,4),e['id']+' atlas dimensions')
        check(len(e['frames'])==e['frame_count'],e['id']+' frame count')
        for r in e['frames']:
            path=ROOT/r['path'];im=Image.open(path);a=np.array(im)
            check(im.mode=='RGBA' and im.size==(256,256),str(path)+' format')
            check(sha(path)==r['sha256'],str(path)+' SHA')
            x,y,w,h=r['rect'];check(np.array_equal(aa[y:y+h,x:x+w],a),str(path)+' atlas pixel mismatch')
            edge_count+=int(np.count_nonzero(a[0,:,3])+np.count_nonzero(a[-1,:,3])+np.count_nonzero(a[:,0,3])+np.count_nonzero(a[:,-1,3]))
            frames.append(a)
        check(edge_count==0,e['id']+' clipped outer alpha')
        check(any(np.any(f[...,3]) for f in frames),e['id']+' blank all frames')
        # Premultiplied-space comparison measures visible change, not RGB hidden
        # behind alpha zero. Loop seam should be a normal temporal step.
        pf=[f[...,:3].astype(float)*(f[...,3:4]/255) for f in frames]
        diffs=[float(np.abs(pf[i+1]-pf[i]).mean()) for i in range(len(pf)-1)]
        seam=float(np.abs(pf[0]-pf[-1]).mean())
        if e['loop']:check(seam<=max(diffs)*1.7+.03,e['id']+' loop seam outside adjacent change bound')
        else:check(not np.any(frames[0][...,3]) and not np.any(frames[-1][...,3]),e['id']+' one-shot endpoints not transparent')
        for pathkey,hashkey in [('preview','preview_sha256'),('transparent_preview','transparent_preview_sha256'),('poster','poster_sha256')]:check(sha(ROOT/e[pathkey])==e[hashkey],e['id']+' '+pathkey+' SHA')
        gif=Image.open(ROOT/e['preview']);duration=sum(f.info.get('duration',0) for f in ImageSequence.Iterator(gif));check(abs(duration-e['duration_seconds']*1000)<=10,e['id']+' GIF total timing')
        check(gif.info.get('loop')==0 if e['loop'] else 'loop' not in gif.info,e['id']+' GIF loop policy')
        webp=Image.open(ROOT/e['transparent_preview']);decoded=[];elapsed=0
        for wf in ImageSequence.Iterator(webp):
            arr=np.array(wf.convert('RGBA'));ms=wf.info['duration'];decoded.append((elapsed,elapsed+ms,arr));elapsed+=ms
        check(abs(elapsed-e['duration_seconds']*1000)<=1,e['id']+' WebP timing')
        check(webp.info.get('loop')==(0 if e['loop'] else 1),e['id']+' WebP loop policy')
        for i,png in enumerate(frames):
            moment=round(i*1000/24);matches=[arr for start,end,arr in decoded if start<=moment<end]
            check(len(matches)==1,e['id']+' WebP timeline coverage')
            if matches:
                arr=matches[0];check(np.array_equal(arr[...,3],png[...,3]),e['id']+' WebP alpha at '+str(i));visible=png[...,3]>0;check(np.array_equal(arr[...,:3][visible],png[...,:3][visible]),e['id']+' lossless visible WebP pixels at '+str(i))
        poster=Image.open(ROOT/e['poster']).convert('RGBA');check(np.array_equal(np.array(poster),frames[e['poster_frame']]),e['id']+' poster source frame')
        rows.append({'id':e['id'],'frames_checked':len(frames),'atlas_pixels_equal':True,'outer_alpha_pixels':edge_count,'gif_frames':gif.n_frames,'gif_duration_ms':duration,'webp_frames':webp.n_frames,'webp_duration_ms':elapsed,'webp_visible_pixels_equal_to_PNG':True,'loop_seam_premultiplied_mae':round(seam,6),'largest_adjacent_mae':round(max(diffs),6)})
    source=ROOT/'source/cards_source.json';data=json.loads(source.read_text())
    check(bind['card_source_sha256']==sha(source),'card source fingerprint')
    check({x['id'] for x in bind['cards']}=={x['id'] for x in data['cards']},'89 card coverage')
    source_by_id={x['id']:x for x in data['cards']}
    checked=0
    for c in bind['cards']:
        sc=source_by_id[c['id']];check(c['base_effect_verbatim']==sc['base_effect'] and c['upgraded_effect_verbatim']==sc['upgraded_effect'],c['id']+' rules drift')
        check(len(c['cues'])>0,c['id']+' missing cues')
        for cue in c['cues']:
            for eid in [cue['effect_id'],cue.get('prelude_effect'),cue.get('target_contact_effect'),cue.get('optional_connector_effect'),*cue.get('effect_by_result_form',{}).values()]:
                if eid:check(eid in ids,c['id']+' unknown effect '+eid)
            check(cue['blocks_gameplay'] is False,c['id']+' visual blocks gameplay');checked+=1
    for cue in bind['global_rule_cues']:
        if cue['effect_id']:check(cue['effect_id'] in ids,'unknown global effect '+cue['effect_id'])
    icon_checks=0
    import xml.etree.ElementTree as ET
    for ic in icons['icons']:
        svg=ROOT/ic['editable_svg'];check(sha(svg)==ic['svg_sha256'],ic['id']+' SVG SHA');ET.parse(svg)
        for sz,f in ic['files'].items():
            path=ROOT/f['path'];im=Image.open(path);check(im.mode=='RGBA' and im.size==(int(sz),int(sz)),ic['id']+' icon dimensions');check(sha(path)==f['sha256'],ic['id']+' icon SHA');icon_checks+=1
    audio_path=ROOT.parent/'audio/manifest.json'
    audio_runtime_present=audio_path.exists()
    if audio_runtime_present:audio=json.loads(audio_path.read_text());audio_ids={c['id'] for c in audio['cues']}
    else:audio_path=ROOT/'source/audio_cues.json';audio_ids=set(json.loads(audio_path.read_text())['cue_ids'])
    for e in m['effects']:check(e['audio_cue'] in audio_ids,'missing audio cue '+e['audio_cue'])
    report={'status':'pass' if not errors else 'fail','scope':'technical_pixels_timing_source_binding_only; visual review is separate','effect_count':len(rows),'total_frames_checked':sum(x['frames_checked'] for x in rows),'card_count':len(bind['cards']),'card_cues_checked':checked,'global_cues':len(bind['global_rule_cues']),'icons_checked':len(icons['icons']),'icon_png_files_checked':icon_checks,'audio_cue_ids_resolved':len(m['effects']),'audio_validation_scope':'live_parent_audio_manifest' if audio_runtime_present else 'standalone_cue_interface_snapshot; audio_runtime_assets_in_animation_package','errors':errors,'effects':rows,'inputs':{'manifest_sha256':sha(ROOT/'manifest.json'),'bindings_sha256':sha(ROOT/'card_vfx_bindings.json'),'icons_manifest_sha256':sha(ROOT/'icons/manifest.json'),'audio_interface_sha256':sha(audio_path),'validator_sha256':sha(Path(__file__))}}
    (ROOT/'reports/technical_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('effects','inputs')},ensure_ascii=False));raise SystemExit(bool(errors))
if __name__=='__main__':main()
