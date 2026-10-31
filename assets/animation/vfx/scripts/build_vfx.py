#!/usr/bin/env python3
"""Build the independent transparent VFX library from native editable geometry."""
from pathlib import Path
import json, math, hashlib, sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from effects import SPECS,render

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def atomic_text(p,text):
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+f'.{os.getpid()}.tmp')
    with tmp.open('w') as f:f.write(text);f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
def save_json(p,d):atomic_text(p,json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def atomic_image(im,p,**kwargs):
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.stem+f'.{os.getpid()}.tmp'+p.suffix)
    im.save(tmp,**kwargs)
    with tmp.open('rb') as f:os.fsync(f.fileno())
    with Image.open(tmp) as check:check.load()
    os.replace(tmp,p)
def compose_bg(im,color=(29,42,51,255)):
    bg=Image.new('RGBA',im.size,color);bg.alpha_composite(im);return bg.convert('RGB')
def main():
    effects=[]
    for eid,label,family,count,loop,anchor,z in SPECS:
        folder=ROOT/'frames'/eid;folder.mkdir(parents=True,exist_ok=True)
        frames=[];records=[];bbox=None
        for i in range(count):
            t=i/count if loop else i/(count-1);im=render(eid,t,loop);atomic_image(im,folder/f'{i:03}.png',compress_level=9)
            b=im.getbbox()
            if b:bbox=list(b) if bbox is None else [min(bbox[0],b[0]),min(bbox[1],b[1]),max(bbox[2],b[2]),max(bbox[3],b[3])]
            frames.append(im);records.append({'index':i,'time_seconds':round(i/24,7),'rect':[(i%8)*256,(i//8)*256,256,256],'path':f'frames/{eid}/{i:03}.png','sha256':sha(folder/f'{i:03}.png')})
        rows=math.ceil(count/8);atlas=Image.new('RGBA',(2048,256*rows))
        for i,im in enumerate(frames):atlas.paste(im,((i%8)*256,(i//8)*256))
        af=ROOT/'atlases'/f'{eid}.png';af.parent.mkdir(exist_ok=True);atomic_image(atlas,af,compress_level=9)
        meta={'id':eid,'label_zh':label,'family':family,'fps':24,'frame_count':count,'duration_seconds':count/24,'loop':loop,'anchor':anchor,'layer_z':z,'blend_mode':'mix','alpha_mode':'straight','pivot_px':[128,128], 'content_bbox':bbox,'atlas':{'image':f'atlases/{eid}.png','json':f'atlases/{eid}.json','columns':8,'rows':rows,'tile_size':[256,256],'sha256':sha(af)},'frames':records,'audio_cue':f'sfx.{eid}','audio_policy':'once_on_semantic_event; looping_vfx_never_retriggers_audio','lifecycle':'state_owner' if loop else 'one_shot_autofree','source_geometry':'scripts/effects.py'}
        if eid=='heavy_impact':meta['pivot_px']=[128,181]
        if eid in ('domain_enter','domain_loop','domain_exit'):meta['pivot_px']=[128,180]
        if eid=='feral_aura':meta['pivot_px']=[128,197]
        if anchor in ('source_to_target','owner_to_target','damaged_target_to_owner'):
            meta['segment_anchors_px']={'source':[30,128],'target':[224,128]}
        if eid=='lifesteal':meta['segment_anchors_px']={'source':[216,142],'target':[40,142]}
        if anchor=='owner_to_selected_card':
            meta['source_anchor_px']=[38,181];meta['target_card_rect_px']=[86,48,92,159]
            meta['target_anchor_px']=[170,125]
            meta['presentation_note']='External spirit reaches selected card, then stains a local patch near the right side of its portrait; not a body transformation.'
        if family=='card' or eid in ('feral_claw','feral_body'):
            meta['actual_card_node_policy']='Retain the authoritative card image/node under this transparent overlay; animation never changes card state.'
        save_json(ROOT/'atlases'/f'{eid}.json',meta)
        pv=ROOT/'previews';pv.mkdir(exist_ok=True)
        durations=[round((i+1)*1000/24/10)*10-round(i*1000/24/10)*10 for i in range(count)]
        gifs=[compose_bg(im) for im in frames]
        kwargs={'save_all':True,'append_images':gifs[1:],'duration':durations,'optimize':False,'disposal':2}
        if loop:kwargs['loop']=0
        atomic_image(gifs[0],pv/f'{eid}.gif',**kwargs)
        atomic_image(frames[0],pv/f'{eid}.webp',save_all=True,append_images=frames[1:],duration=[round((i+1)*1000/24)-round(i*1000/24) for i in range(count)],loop=0 if loop else 1,lossless=True,method=4)
        peak=max(range(count),key=lambda k:np.count_nonzero(np.array(frames[k])[...,3]>100))
        atomic_image(frames[peak],pv/f'{eid}_poster.png')
        meta.update(preview=f'previews/{eid}.gif',transparent_preview=f'previews/{eid}.webp',poster=f'previews/{eid}_poster.png',poster_frame=peak,preview_sha256=sha(pv/f'{eid}.gif'),transparent_preview_sha256=sha(pv/f'{eid}.webp'),poster_sha256=sha(pv/f'{eid}_poster.png'))
        effects.append(meta);print(eid,count,bbox,flush=True)
    manifest={'schema_version':1,'asset_revision':'v5','fps':24,'canvas_size':[256,256],'alpha_mode':'straight','blend_mode':'mix','provenance':'Original deterministic vector-like geometry, extending the project code-native VFX language; no downloaded game textures.','effects':effects,'effect_count':len(effects),'total_frames':sum(e['frame_count'] for e in effects),'source_sha256':sha(ROOT/'scripts/effects.py')}
    save_json(ROOT/'manifest.json',manifest)
    atomic_text(ROOT/'gallery_data.js','window.VOLIBEAR_VFX_DATA='+json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+';\n')
    make_proofs(effects)

def make_proofs(effects):
    out=ROOT/'reports';out.mkdir(exist_ok=True)
    font=ImageFont.truetype(str(ROOT/'fonts/proof_sans.ttf'),16)
    font2=ImageFont.truetype(str(ROOT/'fonts/proof_sans.ttf'),12)
    pages=[]
    for pn in range(math.ceil(len(effects)/8)):
        subset=effects[pn*8:pn*8+8];canvas=Image.new('RGB',(1140,8*185+44),(23,33,41));d=ImageDraw.Draw(canvas)
        d.text((18,13),f'V5 ORIGINAL VFX / page {pn+1} / 5 actual exported samples per effect',font=font,fill=(225,235,235))
        used=[]
        for r,e in enumerate(subset):
            inds=[round(q*(e['frame_count']-1)) for q in (.12,.27,.43,.60,.78)]
            y=44+r*185;d.text((15,y+9),e['id'],font=font2,fill=(214,223,225));d.text((15,y+29),f"{e['frame_count']} frames / {'loop' if e['loop'] else 'one-shot'}",font=font2,fill=(140,164,177))
            for k,i in enumerate(inds):
                im=Image.open(ROOT/e['frames'][i]['path']).convert('RGBA').resize((171,171),Image.Resampling.LANCZOS)
                x=270+k*174;canvas.paste(compose_bg(im),(x,y+3));d.text((x+6,y+154),f'f{i:02}',font=font2,fill=(170,188,200))
            used.append({'id':e['id'],'frames':inds})
        path=out/f'contact_{pn+1:02}.jpg';atomic_image(canvas,path,quality=94)
        pages.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path),'samples':used,'actual_viewed':False})
    save_json(out/'contact_manifest.json',{'pages':pages,'note':'Generated samples are not automatic visual approval; operator records actual review separately.'})
if __name__=='__main__':main()
