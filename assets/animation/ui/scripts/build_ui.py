#!/usr/bin/env python3
"""Adapt the approved illustration to native UI sizes without repainting anatomy."""
from pathlib import Path
import json,hashlib,math
from PIL import Image,ImageDraw,ImageOps,ImageFilter,ImageChops
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent
SRC=REPO/'references/identity/volibear_approved.png'
REC=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(im,name,role,basis):
    p=ROOT/'images'/name;p.parent.mkdir(parents=True,exist_ok=True);im.save(p)
    REC.append({'id':Path(name).stem,'file':str(p.relative_to(ROOT)),'size':list(im.size),'mode':im.mode,'role':role,'basis':basis,'sha256':sha(p)})
def plate(size):
    w,h=size;im=Image.new('RGBA',size,(21,34,48,255));d=ImageDraw.Draw(im)
    d.polygon([(0,h*.64),(w*.43,h*.20),(w,h*.46),(w,h),(0,h)],fill=(37,55,70,255))
    d.polygon([(0,h*.83),(w*.55,h*.51),(w,h*.71),(w,h),(0,h)],fill=(16,29,43,255))
    return im
def portrait(src,size):
    im=plate(size);crop=src.crop((450,70,1240,1160));fit=ImageOps.fit(crop,(round(size[0]*1.3),round(size[1]*1.06)),method=Image.Resampling.LANCZOS,centering=(.70,.30));im.alpha_composite(fit,(-round(size[0]*.16),0));return im
def head_icon(src,size):
    # A deliberate circular UI window prevents raw rectangular chest crop edges.
    work=size*4;im=Image.new('RGBA',(work,work),(20,36,51,255));p=src.crop((720,110,1230,650));p=ImageOps.fit(p,(work,work),Image.Resampling.LANCZOS,centering=(.62,.32));im.alpha_composite(p)
    mask=Image.new('L',(work,work));ImageDraw.Draw(mask).ellipse((12,12,work-12,work-12),fill=255);im.putalpha(mask)
    return im.resize((size,size),Image.Resampling.LANCZOS)
def energy(size,dim=False):
    s=4;z=size*s;im=Image.new('RGBA',(z,z));d=ImageDraw.Draw(im);cx=cy=z/2;r=z*.45
    pts=[(cx+math.cos(i*math.pi/3-math.pi/6)*r,cy+math.sin(i*math.pi/3-math.pi/6)*r) for i in range(6)]
    d.polygon(pts,fill=(16,33,49,255),outline=(151,126,87,255),width=max(2,round(z*.035)))
    r2=r*.80;pts2=[(cx+math.cos(i*math.pi/3-math.pi/6)*r2,cy+math.sin(i*math.pi/3-math.pi/6)*r2) for i in range(6)]
    d.line(pts2+[pts2[0]],fill=(67,106,127,255),width=max(2,round(z*.017)),joint='curve')
    bolt=[(.54,.19),(.28,.52),(.46,.52),(.38,.81),(.72,.43),(.54,.43),(.64,.19)]
    d.polygon([(a*z,b*z) for a,b in bolt],fill=(97,204,228,255) if not dim else (76,103,118,255))
    return im.resize((size,size),Image.Resampling.LANCZOS)
def main():
    src=Image.open(SRC).convert('RGBA')
    assert sha(SRC)=='870b2ad6670b3adf7b319710b883f8e3b6319a7715ac68fb5628cbe6c64e3e5d'
    for size in [(132,195),(528,780)]:
        im=portrait(src,size);suffix='' if size[0]==132 else '_master'
        save(im,'char_select_volibear'+suffix+'.png','character select portrait','author template 132x195; 4x editable derivation')
        locked=ImageOps.grayscale(im).convert('RGBA');locked.putalpha(255);arr=Image.new('RGBA',size,(12,21,32,135));locked=Image.alpha_composite(locked,arr)
        save(locked,'char_select_volibear_locked'+suffix+'.png','locked character select portrait','same original crop; grayscale and dark UI state')
    head=head_icon(src,128);save(head,'character_icon_volibear.png','run / top-panel portrait','author template 128x128')
    alpha=head.getchannel('A');outer=alpha.filter(ImageFilter.MaxFilter(9));outline=Image.new('RGBA',head.size,(215,239,242,0));outline.putalpha(outer)
    save(outline,'character_icon_volibear_outline.png','multiplayer portrait outline','128x128 silhouette, no new anatomy')
    marker=Image.new('RGBA',(128,128));d=ImageDraw.Draw(marker);d.polygon([(64,124),(40,101),(88,101)],fill=(187,161,118,255));d.ellipse((8,4,120,116),fill=(19,34,49,255),outline=(187,161,118,255),width=5)
    crop=head.resize((103,103),Image.Resampling.LANCZOS);marker.alpha_composite(crop,(12,8));save(marker,'map_marker_volibear.png','map position marker','author template 128x128; character face on a map pin')
    for size,name in [(74,'big_energy.png'),(24,'text_energy.png'),(256,'energy_master.png')]:save(energy(size),name,'energy emblem','template 74/24; scalable custom bolt/bronze hexagon')
    save(energy(74,True),'big_energy_empty.png','energy disabled UI state','same emblem, unlit')
    canvas=Image.new('RGBA',(512,512));fit=ImageOps.contain(src,(460,460),Image.Resampling.LANCZOS);canvas.alpha_composite(fit,((512-fit.width)//2,480-fit.height));save(canvas,'character_fallback.png','fallback static creature visual','approved original, uniform scale, no anatomy repaint')
    full=plate((1920,1080));d=ImageDraw.Draw(full);d.polygon([(0,0),(760,0),(900,1080),(0,1080)],fill=(14,24,36,255));person=ImageOps.contain(src,(1120,1020),Image.Resampling.LANCZOS);full.alpha_composite(person,(780,1070-person.height));save(full,'character_select_background.png','character select backdrop','1920x1080 project layout; exact character painting at uniform scale, clear left UI area')
    transition=Image.new('RGBA',(1920,1080));transition.alpha_composite(person,(780,1070-person.height));save(transition,'character_select_transition.png','transition character cutout','same registered position as select background; engine scene controls transition')
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><path d="M128 13 228 70 228 186 128 243 28 186 28 70Z" fill="#102131" stroke="#977e57" stroke-width="9"/><path d="M128 36 208 82 208 174 128 220 48 174 48 82Z" fill="none" stroke="#436a7f" stroke-width="4"/><path d="M138 49 72 133 118 133 97 207 184 110 138 110 164 49Z" fill="#61cce4"/></svg>'
    (ROOT/'source').mkdir(exist_ok=True);(ROOT/'source/energy_emblem.svg').write_text(svg)
    # New gestures are authored separately. Preserve them and their provenance
    # when rebuilding crops of the approved character; never regenerate them.
    hands=json.loads((ROOT/'source/multiplayer_hands/provenance.json').read_text())
    for row in hands['source_assets']+hands['runtime_assets']:
        if sha(ROOT/row['file'])!=row['sha256']: raise ValueError('Authored hand differs: '+row['file'])
    REC.extend(hands['runtime_assets'])
    m={'schema_version':1,'source_file':str(SRC.relative_to(REPO)),'source_sha256':sha(SRC),'source_processing':'UI crops, proportional resize, UI panel composition and grayscale locked state. No repaint or new character generation.','template_commit':'2c900a04dd2073872f677f4fb78ee2ad1e871009','size_policy':'Template conventions, not claimed engine-enforced limits.','assets':REC,'reuse_decisions':{'merchant':'animations/clean relaxed_loop','rest_site':'animations/clean relaxed_loop; no new sitting/campfire animation claimed','revive':'return from held death to idle via explicit game revive trigger; no new painted revive clip claimed','card_frames':'basegame UI frames, with existing 89 project portraits','background_music':'basegame music retained; no new score commissioned','multiplayer_point_and_rps':'vanilla fallback; four bespoke gesture drawings not included','yummy_cookie_relic':'vanilla fallback unless mod gameplay defines a custom version'}}
    m['source_processing']='Existing UI derives from the unchanged approved illustration. Four additional multiplayer gestures are new authored images; see source/multiplayer_hands/provenance.json.'
    m['reuse_decisions']['multiplayer_point_and_rps']='four bespoke Volibear gesture sprites; native fixed pivots; no vanilla fallback'
    (ROOT/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'manifest.js').write_text('window.VOLIBEAR_UI='+json.dumps(m,ensure_ascii=False,separators=(',',':'))+';\n')
    proof=Image.new('RGB',(1200,850),(31,43,57));d=ImageDraw.Draw(proof)
    samples=['char_select_volibear.png','char_select_volibear_locked.png','character_icon_volibear.png','character_icon_volibear_outline.png','map_marker_volibear.png','big_energy.png','text_energy.png','big_energy_empty.png','character_fallback.png']
    for i,n in enumerate(samples):
        x=(i%5)*240;y=(i//5)*300;im=Image.open(ROOT/'images'/n).convert('RGBA');im.thumbnail((216,245));proof.paste(im,(x+(240-im.width)//2,y+35),im);d.text((x+8,y+8),n.replace('volibear','vb'),fill=(220,230,233))
    bg=Image.open(ROOT/'images/character_select_background.png');bg.thumbnail((660,250));proof.paste(bg,(530,590));d.text((540,575),'1920 x 1080 selection composition',fill=(220,230,233))
    (ROOT/'previews').mkdir(exist_ok=True);proof.save(ROOT/'previews/ui_contact.png')
    print('UI',len(REC),'PNG assets and 1 native SVG')
if __name__=='__main__':main()
