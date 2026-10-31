#!/usr/bin/env python3
"""Compose proof sheets from unchanged final art. This does not draw or edit card content."""
from pathlib import Path
import argparse,json,math
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--font',type=Path,required=True);args=p.parse_args()
font=ImageFont.truetype(str(args.font),18);small=ImageFont.truetype(str(args.font),13);title=ImageFont.truetype(str(args.font),28)
src=json.loads((R/'data/cards_source.json').read_text())['cards'];m=json.loads((R/'data/asset_manifest.json').read_text())['cards'];locked={c['id'] for c in json.loads((R/'data/v7/user_locked_cards.json').read_text())['cards']};scores={c['id']:c['score'] for c in json.loads((R/'reports/revision_v7/quality_ranking.json').read_text())['cards']}
out=R/'previews/v7';out.mkdir(parents=True,exist_ok=True)
for page in range(4):
    batch=src[page*23:(page+1)*23];board=Image.new('RGB',(1370,100+math.ceil(len(batch)/5)*244+16),'#14212d');d=ImageDraw.Draw(board)
    d.text((20,15),f'沃利贝尔 V7 · 全部成品 {page+1}/4',font=title,fill='white');d.text((20,57),'金标 = 用户固定原图    青标 = 本轮重绘    总计 28 固定 + 61 重绘 = 89',font=font,fill='#b9ced5')
    for n,c in enumerate(batch):
        x=20+(n%5)*270;y=100+(n//5)*244;cid=c['id'];im=Image.open(R/m[cid]['master']).convert('RGB').resize((250,190),Image.Resampling.LANCZOS);board.paste(im,(x,y));col='#d8b77b' if cid in locked else '#71d9d4';d.rectangle((x,y,x+249,y+189),outline=col,width=2);d.text((x,y+193),cid+' '+c['name'],font=font,fill='white');label='固定保留' if cid in locked else f'重绘 · 独立审稿 {scores[cid]}/100';d.text((x,y+219),label,font=small,fill=col)
    board.save(out/f'all_cards_{page+1:02d}.jpg',quality=94)
board=Image.new('RGB',(1260,590),'#14212d');d=ImageDraw.Draw(board)
for x,cid,label in [(20,'U28','U28 雷霆反扑 · V7重绘'),(640,'U35','U35 霹天雳地 · 固定原图')]:
    d.text((x,15),label,font=title,fill='white');im=Image.open(R/m[cid]['master']).convert('RGB').resize((600,456),Image.Resampling.LANCZOS);board.paste(im,(x,65))
d.text((20,538),'后侧俯视 / 两名敌人 / 分向回雷',font=font,fill='#71d9d4');d.text((640,538),'侧面举臂 / 红色背景 / 前景地面波',font=font,fill='#d8b77b');board.save(out/'U28_U35_comparison.jpg',quality=94)
print(json.dumps({'overviews':4,'cards':len(src),'U28_U35':str(out/'U28_U35_comparison.jpg')}))
