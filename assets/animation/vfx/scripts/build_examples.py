#!/usr/bin/env python3
"""Context proof: a real external card receives the spirit; bear stays fixed."""
from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw,ImageFont
from build_vfx import atomic_image,atomic_text
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=ROOT/'examples';out.mkdir(exist_ok=True)
    source=ROOT/'source/volibear_approved.png'
    cards=ROOT/'source'
    # These are inspection thumbnails, never replacements for a production master.
    sources=[('preview_character.png',source,285),('preview_B01.png',cards/'B01.png',400),('preview_T01.png',cards/'T01.png',400)]
    provenance=[]
    for name,path,width in sources:
        im=Image.open(path).convert('RGBA');im=im.resize((width,round(im.height*width/im.width)),Image.Resampling.LANCZOS);atomic_image(im,out/name)
        provenance.append({'preview':name,'source_path_at_build':str(path.relative_to(ROOT)),'source_sha256':sha(path),'preview_sha256':sha(out/name),'purpose':'context inspection only; original proportions retained'})
    char=Image.open(out/'preview_character.png').convert('RGBA');b01=Image.open(out/'preview_B01.png').convert('RGBA');t01=Image.open(out/'preview_T01.png').convert('RGBA')
    font=ImageFont.truetype(str(ROOT/'fonts/proof_sans.ttf'),20);small=ImageFont.truetype(str(ROOT/'fonts/proof_sans.ttf'),14)
    frames=[]
    for i in range(52):
        im=Image.new('RGBA',(820,480),(24,37,47,255));d=ImageDraw.Draw(im)
        d.text((27,22),'FERAL TRANSFER  /  EXTERNAL CARD TARGET',font=font,fill=(229,234,224))
        d.text((28,58),'The original bear silhouette never changes.',font=small,fill=(166,189,195))
        im.alpha_composite(char,(0,170))
        # Card plate represents an engine-owned card node under the VFX.
        d.rounded_rectangle((362,86,546,404),radius=9,fill=(43,59,70),outline=(159,143,111),width=3)
        d.text((378,102),'SELECTED CARD',font=small,fill=(216,223,215))
        portrait=(t01 if i>=36 else b01).resize((166,126),Image.Resampling.LANCZOS);im.alpha_composite(portrait,(371,135))
        d.text((383,285),'CLAW FORM' if i>=36 else 'ATTACK CARD',font=small,fill=(221,190,129))
        d.line([(384,318),(524,318)],fill=(78,98,108),width=2);d.line([(384,335),(510,335)],fill=(78,98,108),width=2)
        if i<40:
            fx=Image.open(ROOT/f'frames/feral_transfer/{i:03}.png').convert('RGBA').resize((512,512),Image.Resampling.LANCZOS);im.alpha_composite(fx,(190,-10))
        label='01  CONFIRMED TARGET' if i<10 else '02  SPIRIT IN TRANSIT' if i<22 else '03  LOCAL SURFACE STAIN' if i<36 else '04  COMMITTED CLAW FORM'
        d=ImageDraw.Draw(im);d.text((570,168),label[:4],font=font,fill=(216,190,130));d.text((570,204),label[4:],font=small,fill=(190,211,215))
        d.text((570,252),'No body morph.',font=small,fill=(155,181,189));d.text((570,276),'No detached limb.',font=small,fill=(155,181,189));d.text((570,300),'No self-infection.',font=small,fill=(155,181,189))
        d.text((28,444),'Illustrative presentation timeline only. Game state is authoritative.',font=small,fill=(144,165,175));frames.append(im.convert('RGB'))
    durations=[round((i+1)*1000/24/10)*10-round(i*1000/24/10)*10 for i in range(len(frames))]
    atomic_image(frames[0],out/'feral_transfer_demo.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=False)
    atomic_image(frames[0],out/'feral_transfer_demo.webp',save_all=True,append_images=frames[1:],duration=[round((i+1)*1000/24)-round(i*1000/24) for i in range(len(frames))],loop=0,lossless=True)
    picks=[0,10,20,28,35,44];board=Image.new('RGB',(1230,720),(20,31,40))
    for j,i in enumerate(picks):board.paste(frames[i].resize((410,240),Image.Resampling.LANCZOS),((j%3)*410,(j//3)*240))
    # Six panels occupy two rows; the bottom explanation uses actual source art.
    d=ImageDraw.Draw(board);d.text((24,512),'SOURCE BODY: identical in every panel',font=font,fill=(221,232,227));d.text((24,554),'TARGET: one existing card node, local lower-right staining, then an actual confirmed form change',font=small,fill=(168,191,198));d.text((24,594),'This storyboard does not add selection rules, damage, costs or character anatomy changes.',font=small,fill=(168,191,198));d.text((24,634),'No screen-wide flash. The short energy path leads the eye to the recipient.',font=small,fill=(168,191,198))
    atomic_image(board,out/'feral_transfer_storyboard.png')
    atomic_text(out/'provenance.json',json.dumps({'previews':provenance,'picked_demo_frames':picks,'demo_frame_count':52,'fps':24,'storyboard_sha256':sha(out/'feral_transfer_storyboard.png'),'source_bear_unchanged_by_effect':True,'rules_implemented':False},ensure_ascii=False,indent=2)+'\n')
    print('external card context demo built')
if __name__=='__main__':main()
