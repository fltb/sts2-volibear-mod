"""Decode all candidate files and verify frame/timing/source integrity, no art approval."""
from pathlib import Path
import json,hashlib
from PIL import Image
import numpy as np
import render as r
ROOT=r.ROOT

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 m=json.loads((ROOT/'manifest.json').read_text());rows=[];issues=[];edge_frames=[]
 for path,digest in m['source_integrity'].items():
  if sha(r.REPO/path)!=digest:issues.append('Changed source: '+path)
 for p in list((ROOT/'source').glob('*.png'))+list((ROOT/'parts').glob('*.png')):
  with Image.open(p) as im:im.load()
 for c in m['clips']+m['variants']:
  name=c['name'];count=c['frame_count'];expected=r.CLIPS[name]
  if c['events']!=expected['events']:issues.append(name+': event mismatch')
  with Image.open(ROOT/c['atlas']['image']) as im:im.load();atlas=im.convert('RGBA')
  for f in c['frames']:
   i=f['frame'];p=ROOT/'frames'/name/f'{i:03d}.png'
   with Image.open(p) as im:im.load();im=im.convert('RGBA')
   if sha(p)=='':raise AssertionError()
   if hashlib.sha256(im.tobytes()).hexdigest()!=f['raw_rgba_sha256']:issues.append(f'{name}/{i}: frame hash mismatch')
   x,y,w,h=f['rect']
   if atlas.crop((x,y,x+w,y+h)).tobytes()!=im.tobytes():issues.append(f'{name}/{i}: atlas mismatch')
   a=np.array(im.getchannel('A'));border=np.concatenate([a[0],a[-1],a[:,0],a[:,-1]])
   if (border>32).any():edge_frames.append({'clip':name,'frame':i,'edge_pixels':int((border>32).sum())})
  decoded={}
  for kind in ['gif','webp']:
   with Image.open(ROOT/c[kind]) as im:
    duration=0;n=im.n_frames
    for i in range(n):im.seek(i);im.load();duration+=im.info.get('duration',0)
   decoded[kind]={'frames':n,'duration_ms':duration,'sha256':sha(ROOT/c[kind])}
   if abs(duration-count/24*1000)>11:issues.append(name+': '+kind+' duration mismatch')
  rows.append({'clip':name,'frames':count,'decoded':decoded,'events':len(c['events'])})
 weights={}
 for name,(v,uv,ws,tris) in r.MESHES.items():
  sums=np.array([sum(x.values()) for x in ws]);err=float(np.max(abs(sums-1)));weights[name]={'vertices':len(v),'triangles':len(tris),'max_weight_sum_error':err}
  if err>1e-6:issues.append(name+': bad mesh weights')
 report={'technical_status':'pass' if not issues and not edge_frames and m['render_complete'] else 'needs_review','render_complete':m['render_complete'],'sequences':len(rows),'total_frames':sum(x['frames'] for x in rows),'input_sha256':m['render_input_sha256'],'issues':issues,'nontransparent_canvas_edge_frames':edge_frames,'clips':rows,'meshes':weights,'visual_approval':False,'browser_playback':'not_verified_in_this_environment','game_integration':'integration_source_uncompiled'}
 r.js(ROOT/'technical_validation.json',report);print(json.dumps({k:report[k] for k in ['technical_status','sequences','total_frames','issues','nontransparent_canvas_edge_frames']}))
if __name__=='__main__':main()
