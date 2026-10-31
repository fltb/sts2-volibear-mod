#!/usr/bin/env python3
"""Prepare an exact-aspect candidate, export proofs, and comparison views. Never approve art."""
from pathlib import Path
import argparse,hashlib,json,math,importlib.util
from PIL import Image,ImageDraw,ImageOps

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('id');p.add_argument('attempt',type=int);a=p.parse_args()
id=a.id;raw=ROOT/f'cards/candidates_v7/{id}/attempt{a.attempt:02d}.png'
if not raw.exists():
    selected=json.loads((ROOT/'data/asset_manifest.json').read_text())['cards'][id].get('provenance',{})
    assert selected.get('attempt')==a.attempt,'This archived attempt is not a delivered source; supply a new candidate.'
    raw=ROOT/selected['raw_path']
im=Image.open(raw).convert('RGB');w,h=im.size
# Largest 25:19 integer rectangle, with no stretching or painted reconstruction.
unit=min(w//25,h//19);cw,ch=unit*25,unit*19
assert cw>=1000 and ch>=760,(id,'generation too small')
assert cw/w>.92 and ch/h>.92,(id,'aspect mismatch needs regeneration, not a large crop',im.size)
left=(w-cw)//2;top=(h-ch)//2;box=[left,top,left+cw,top+ch]
out=ROOT/f'cards/candidates_v7/{id}/stage{a.attempt:02d}';out.mkdir(parents=True,exist_ok=True)
master=im.crop(box);master.save(out/'master.png')
source=json.loads((ROOT/'data/cards_source.json').read_text());card=next(c for c in source['cards'] if c['id']==id)
plan=next(c for c in json.loads((ROOT/'data/v7/redesign_plan.json').read_text())['cards'] if c['id']==id)
spec=importlib.util.spec_from_file_location('card_repo',ROOT/'scripts/card_repo.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
profiles=json.loads((ROOT/'config/export_profiles.json').read_text())['profiles']
for profile in profiles:
    rendered=mod.render(ROOT,card,master,profile);rendered.save(out/(profile['name']+'.png'))
master.resize((250,190),Image.Resampling.LANCZOS).save(out/'250.png')
master.resize((125,95),Image.Resampling.LANCZOS).save(out/'125.png')
ImageOps.grayscale(master).resize((125,95),Image.Resampling.LANCZOS).save(out/'gray.png')
locked={x['id']:x['sha256'] for x in json.loads((ROOT/'data/v7/user_locked_cards.json').read_text())['cards']}
for rid in plan['anchors']:
    assert rid in locked and hashlib.sha256((ROOT/f'cards/masters/{rid}.png').read_bytes()).hexdigest()==locked[rid], 'Benchmark must match a user-locked original'
refs=[Image.open(ROOT/f'cards/masters/{r}.png').convert('RGB') for r in plan['anchors']]
board=Image.new('RGB',(1560,1110),'#172330');d=ImageDraw.Draw(board)
for i,(name,pic) in enumerate([(id+' NEW',master)]+list(zip(plan['anchors'],refs))):
    x=15+i*520;d.text((x,12),name,fill='white');board.paste(pic.resize((500,380),Image.Resampling.LANCZOS),(x,35))
    board.paste(pic.resize((250,190),Image.Resampling.LANCZOS),(x,445))
    board.paste(pic.resize((125,95),Image.Resampling.LANCZOS),(x+270,445))
    board.paste(ImageOps.grayscale(pic).resize((125,95),Image.Resampling.LANCZOS).convert('RGB'),(x+270,555))
    d.text((x,660),'250 x 190 / 125 x 95 / grayscale',fill='#c1ceda')
for i,fn in enumerate(['sts1_large.png','sts1_small.png']):
    pic=Image.open(out/fn).convert('RGBA');pic.thumbnail((420,320),Image.Resampling.LANCZOS)
    bg=Image.new('RGB',pic.size,'#697681');bd=ImageDraw.Draw(bg)
    for y in range(0,bg.height,20):
        for x in range(0,bg.width,20):
            if (x//20+y//20)%2:bd.rectangle((x,y,x+19,y+19),fill='#394954')
    bg.paste(pic,mask=pic.getchannel('A'));board.paste(bg,(15+i*460,735));d.text((15+i*460,708),fn+' export mask',fill='white')
board.save(out/'comparison.jpg',quality=94)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record={'id':id,'attempt':a.attempt,'raw_file':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw),'raw_size':[w,h],
        'crop_box':box,'master_file':str((out/'master.png').relative_to(ROOT)),'master_sha256':sha(out/'master.png'),
        'master_size':[cw,ch],'comparison_file':str((out/'comparison.jpg').relative_to(ROOT)),
        'comparison_sha256':sha(out/'comparison.jpg'),'anchors':plan['anchors'],'visual_approval':False}
(out/'stage.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
