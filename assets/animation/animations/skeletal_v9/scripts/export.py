"""Export the same rig/poses to clean frames, atlases, previews and review pages."""
from pathlib import Path
import argparse,json,hashlib,math,io,time
from concurrent.futures import ProcessPoolExecutor
POOL=None
def render_frame(task):
    name,i,count=task
    return r.render(name,i/count)
from PIL import Image,ImageDraw
import render as r
ROOT=r.ROOT;REPO=r.REPO
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inputs():
    files=[ROOT/'rig.json',ROOT/'scripts/render.py',ROOT/'scripts/leg_deformation.py',ROOT/'scripts/build_parts.py',Path(__file__),REPO/'animations/rig/motions.json']
    files+=list((ROOT/'parts').glob('*.png'))+list((ROOT/'source').glob('*.png'))
    return {str(p.relative_to(REPO)):digest(p) for p in sorted(files)}
def fingerprint(data):return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
def gif_frames(frames):
    rgb=[]
    for im in frames:
        bg=Image.new('RGB',im.size,(26,38,52));bg.paste(im,(0,0),im);rgb.append(bg)
    palette_sheet=Image.new('RGB',(128*8,128*math.ceil(len(rgb)/8)))
    for i,im in enumerate(rgb):palette_sheet.paste(im.resize((128,128)),(i%8*128,i//8*128))
    palette=palette_sheet.quantize(colors=256)
    return [im.quantize(palette=palette,dither=Image.Dither.NONE) for im in rgb]
def export_clip(name,fp):
    c=r.CLIPS[name];count=round(c['duration']*24);frames=[];samples=[];start=time.monotonic()
    rendered=POOL.map(render_frame,[(name,i,count) for i in range(count)]) if POOL else (r.render(name,i/count) for i in range(count))
    for i,im in enumerate(rendered):
        r.save(ROOT/'frames'/name/f'{i:03d}.png',im);frames.append(im)
        angles,offsets,channels=r.pose(name,i/count)
        samples.append({'time':i/24,'rotations':angles,'offsets':{n:v.tolist() for n,v in offsets.items()},'mouth_cel':0 if channels.get('roar',0)<.12 else 1 if channels.get('roar',0)<.85 else 2})
    atlas=Image.new('RGBA',(4096,512*math.ceil(count/8)))
    records=[]
    for i,im in enumerate(frames):
        x=i%8*512;y=i//8*512;atlas.alpha_composite(im,(x,y));records.append({'frame':i,'rect':[x,y,512,512],'time_seconds':i/24,'duration_ms':1000/24,'raw_rgba_sha256':hashlib.sha256(im.tobytes()).hexdigest(),'pivot_px':[250,442]})
    r.save(ROOT/'atlases'/f'{name}.png',atlas)
    meta={'name':name,'duration':count/24,'loop':c['loop'],'skin':c['skin'],'fps':24,'frame_count':count,'frames':records,'events':c['events'],'atlas':{'image':f'atlases/{name}.png','json':f'atlases/{name}.json','columns':8,'rows':math.ceil(count/8),'tile_size':[512,512]},'input_fingerprint':fp,'technique':'authored_death_cels' if name in ['die','domain_die'] else 'overlapping_parts_weighted_skeleton','gif':f'previews/{name}.gif','webp':f'previews/{name}.webp'}
    r.js(ROOT/'atlases'/f'{name}.json',meta)
    durations=[(round((i+1)*100/24)-round(i*100/24))*10 for i in range(count)]
    gifs=gif_frames(frames);b=io.BytesIO();gifs[0].save(b,format='GIF',save_all=True,append_images=gifs[1:],duration=durations,loop=0,disposal=2,optimize=False);r.atomic(ROOT/meta['gif'],b.getvalue())
    b=io.BytesIO();frames[0].save(b,format='WEBP',save_all=True,append_images=frames[1:],duration=[round((i+1)*1000/24)-round(i*1000/24) for i in range(count)],loop=0,lossless=True,method=4);r.atomic(ROOT/meta['webp'],b.getvalue())
    pages=[]
    for first in range(0,count,16):
        page=Image.new('RGB',(1024,1088),(26,38,52));draw=ImageDraw.Draw(page)
        for j,im in enumerate(frames[first:first+16]):
            x=j%4*256;y=j//4*272;thumb=im.resize((256,256),Image.Resampling.LANCZOS);page.paste(thumb,(x,y+16),thumb);draw.text((x+5,y+2),f'{name}  {first+j:03d}',fill=(220,235,241))
        path=ROOT/'review'/f'{name}_page_{first//16:02d}.png';r.save(path,page);pages.append({'file':str(path.relative_to(ROOT)),'frames':[first,min(first+15,count-1)],'sha256':digest(path),'visual_review':'pending'})
    meta['atlas_sha256']=digest(ROOT/meta['atlas']['image']);meta['gif_sha256']=digest(ROOT/meta['gif']);meta['webp_sha256']=digest(ROOT/meta['webp']);meta['review_pages']=pages
    endpoint=r.pose(name,1.)
    samples.append({'time':count/24,'rotations':endpoint[0],'offsets':{n:v.tolist() for n,v in endpoint[1].items()},'mouth_cel':0 if endpoint[2].get('roar',0)<.12 else 1 if endpoint[2].get('roar',0)<.85 else 2})
    r.js(ROOT/'frames'/name/'skeleton_samples.json',{'clip':name,'duration':count/24,'loop':c['loop'],'input_fingerprint':fp,'samples':samples,'technique':meta['technique']})
    print(json.dumps({'clip':name,'frames':count,'seconds':round(time.monotonic()-start,1)}),flush=True)
    return meta
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--clips',nargs='+');args=ap.parse_args();names=args.clips or list(r.CLIPS)
    POOL=ProcessPoolExecutor(max_workers=4)
    before=inputs();fp=fingerprint(before);current={}
    manifest_path=ROOT/'manifest.json'
    if manifest_path.exists():
        old=json.loads(manifest_path.read_text())
        if old.get('render_input_sha256')==fp:current={c['name']:c for c in old.get('clips',[])+old.get('variants',[])}
    for name in names:
        if name not in r.CLIPS:raise ValueError(name)
        current[name]=export_clip(name,fp)
        assert inputs()==before,'Inputs changed during export; discard candidate results.'
        clips=[current[c['name']] for c in r.MOTIONS if c['name'] in current and not c.get('base_clip')]
        variants=[current[c['name']] for c in r.MOTIONS if c['name'] in current and c.get('base_clip')]
        data={'schema_version':9,'art_revision':'V9_anatomical_hip_and_shoulder_revision','render_complete':len(current)==len(r.CLIPS),'render_input_sha256':fp,'source_integrity':before,'canvas_size':[512,512],'fps':24,'pivot_px':[250,442],'feet_ground_y':442,'facing':'right','contains_baked_effects':False,'contains_domain_tint':False,'total_sequences':len(current),'total_frames':sum(c['frame_count'] for c in current.values()),'action_count':len(clips),'format':'RGBA8 PNG atlases; exact timing in JSON; GIF/WebP for inspection','art_approved':False,'clips':clips,'variants':variants}
        r.js(manifest_path,data)

    POOL.shutdown()
