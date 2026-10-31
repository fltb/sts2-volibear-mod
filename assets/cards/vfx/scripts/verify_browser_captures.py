#!/usr/bin/env python3
"""Compare actual Chromium canvas screenshots against independent PNG frames.

file:// canvas security prevents getImageData; ordinary screenshots preserve the
real viewer behavior without relaxing the browser's file-origin policy.
"""
import json,sys
from PIL import Image
import numpy as np
rows=[]
for r in json.load(sys.stdin):
    shot=Image.open(r['capture']).convert('RGB');ref=Image.open(r['reference']).convert('RGBA')
    expected=Image.new('RGBA',ref.size,(32,49,59,255));expected.alpha_composite(ref)
    expected=expected.convert('RGB').resize(shot.size,Image.Resampling.BILINEAR)
    aa=np.array(shot).astype(float);bb=np.array(expected).astype(float)
    mae=float(np.abs(aa-bb).mean());fg=int(np.any(np.abs(aa-np.array([32,49,59]))>8,axis=-1).sum())
    rows.append({'id':r['id'],'screenshot_size':list(shot.size),'mean_absolute_rgb_difference':round(mae,5),'visible_pixels':fg,'pass':mae<2.5 and fg>0})
out={'status':'pass' if all(x['pass'] for x in rows) else 'fail','checked':len(rows),'method':'actual canvas screenshot vs independent exported frame composited on known stage background; allows browser subpixel resampling','tolerance_mean_absolute_rgb':2.5,'rows':rows}
print(json.dumps(out));sys.exit(0 if out['status']=='pass' else 1)
