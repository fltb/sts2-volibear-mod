#!/usr/bin/env python3
"""Produce native editable SVG and matching raster mechanism icons."""
from pathlib import Path
import json, hashlib
from PIL import Image
from effects import Painter,rgba
from build_vfx import atomic_image,atomic_text
ROOT=Path(__file__).resolve().parents[1]

class Icon(Painter):
    def __init__(self):super().__init__(4);self.svg=[]
    def col(self,c,a):
        r,g,b,al=rgba(c,a);return f'rgb({r},{g},{b})',al/255
    def line(self,pts,col='cyan',width=3,a=1):
        super().line(pts,col,width,a);c,al=self.col(col,a)
        self.svg.append(f'<polyline points="'+ ' '.join(f'{x:.3f},{y:.3f}' for x,y in pts)+f'" fill="none" stroke="{c}" stroke-opacity="{al:.5f}" stroke-width="{width}" stroke-linejoin="round"/>')
    def poly(self,pts,col='cyan',a=1,outline=None,width=2):
        super().poly(pts,col,a,outline,width);c,al=self.col(col,a);oc,oa=self.col(outline,a) if outline else ('none',0)
        self.svg.append('<polygon points="'+' '.join(f'{x:.3f},{y:.3f}' for x,y in pts)+f'" fill="{c}" fill-opacity="{al:.5f}" stroke="{oc}" stroke-opacity="{oa:.5f}" stroke-width="{width}" stroke-linejoin="round"/>')
    def ellipse(self,box,col='cyan',a=1,width=None):
        super().ellipse(box,col,a,width);x0,y0,x1,y1=box;c,al=self.col(col,a)
        style=f'fill="none" stroke="{c}" stroke-opacity="{al:.5f}" stroke-width="{width}"' if width else f'fill="{c}" fill-opacity="{al:.5f}"'
        self.svg.append(f'<ellipse cx="{(x0+x1)/2}" cy="{(y0+y1)/2}" rx="{(x1-x0)/2}" ry="{(y1-y0)/2}" {style}/>')

ICON_SPECS=[('thunder_growth','雷电成长','lightning_growth'),('domain','领域','domain_loop'),('feral','兽化','feral_claw'),('bite_mark','咬痕','mark_bite'),('counter_thunder','反雷','counter_release'),('charge','蓄势','charge'),('enhance','强化','strength'),('retain_armor','留甲','armor_retain'),('iron_armor','坚甲','armor_iron'),('purify','净化','card_purify'),('thunder_armor','雷甲','thunder_armor'),('replay','重演','card_replay'),('lifesteal','汲取','lifesteal'),('cost_reduce','减费','cost_reduce'),('energy','返能','energy_gain'),('domain_suppress','领域压制','domain_suppress')]

def draw_icon(e):
    p=Icon();p.poly([(128,17),(215,67),(215,184),(128,237),(41,184),(41,67)],'ink',.96,'slate',5)
    if e=='thunder_growth':
        p.poly([(145,52),(89,128),(120,128),(102,186),(167,103),(136,103)],'cyan',1,'deep',4)
        for k in range(3):p.poly([(77+k*35,202),(77+k*35,188-k*9),(91+k*35,188-k*9),(91+k*35,202)],'gold')
    elif e=='domain':
        p.arc(128,164,65,27,0,6.283,'cyan',8);p.arc(128,160,60,79,3.1416,6.283,'pale',7)
        p.line([(90,146),(106,113),(97,111),(116,81)],'gold',7)
        p.line([(166,146),(150,113),(159,111),(140,81)],'gold',7)
    elif e=='feral':
        for k in range(3):p.poly([(85+k*33,57),(70+k*33,153),(83+k*33,184),(100+k*33,103)],'pale',1,'deep',3)
        p.line([(80,194),(126,209),(176,192)],'gold',6)
    elif e=='bite_mark':
        for side in (-1,1):
            p.arc(128,128,63,51,3.35 if side<0 else .21,6.07 if side<0 else 2.93,'rust',12)
            for k in range(3):
                x=94+k*34;y=128+side*(41 if k==1 else 34);p.poly([(x-9,y+side*4),(x+9,y+side*4),(x,y-side*18)],'gold')
    elif e=='counter_thunder':
        p.poly([(88,67),(156,67),(156,92),(183,92),(148,135),(112,92),(137,92),(137,84),(88,84)],'gold')
        p.poly([(136,105),(87,161),(116,161),(105,205),(163,141),(136,141)],'cyan',1,'deep',3)
    elif e=='charge':
        for x,s in [(75,1),(181,-1)]:p.poly([(x-15*s,70),(x+36*s,128),(x-15*s,186),(x+5*s,128)],'gold')
        p.diamond(128,128,25,'cyan')
    elif e=='enhance':
        p.poly([(100,197),(100,114),(72,114),(128,55),(184,114),(156,114),(156,197)],'gold',1,'deep',4)
        p.poly([(117,185),(117,105),(139,105),(139,185)],'pale')
    elif e=='retain_armor':
        p.shield(128,129,80,1,7,col='gold')
        p.line([(101,130),(101,108),(128,93),(155,108),(155,130)],'pale',10)
        p.poly([(94,124),(162,124),(162,169),(128,184),(94,169)],'gold',1,'ink',5);p.diamond(128,145,12,'deep')
    elif e=='iron_armor':
        p.shield(128,129,82,1,7,col='slate')
        for y in (83,117,151):p.poly([(89,y),(128,y+13),(167,y),(160,y+24),(128,y+38),(96,y+24)],'pale',1,'ink',5)
        p.line([(128,58),(128,204)],'gold',7)
    elif e=='purify':
        p.poly([(76,66),(176,66),(176,194),(76,194)],'deep',.7,'pale',5)
        p.poly([(63,166),(178,88),(194,108),(79,186)],'mint',1,'ink',4)
        p.line([(79,166),(179,99)],'ice',5)
        p.shard(173,58,14,-1,'gold');p.shard(187,173,9,-.5,'gold')
    elif e=='thunder_armor':
        p.shield(128,129,81,1,7,col='cyan');p.poly([(141,70),(103,130),(131,130),(112,183),(157,116),(130,116)],'gold',1,'deep',4)
    elif e=='replay':
        p.arc(128,128,61,56,3.8,6.8,'cyan',12);p.arc(128,128,61,56,.66,3.5,'gold',12)
        p.poly([(172,148),(200,153),(188,122)],'cyan');p.poly([(84,108),(56,103),(68,134)],'gold')
        p.poly([(119,94),(119,162),(153,128)],'pale')
    elif e=='lifesteal':
        p.poly([(181,65),(181,102),(147,111),(117,146),(81,157),(75,190),(58,157),(73,126),(77,141),(109,131),(139,96),(161,88),(161,65)],'mint',1,'deep',3)
        p.diamond(181,69,18,'red');p.diamond(77,165,17,'mint')
    elif e=='cost_reduce':
        for y in (72,125):p.poly([(76,y),(128,y+28),(180,y),(128,y+53)],'cyan',1,'deep',4)
        p.line([(90,198),(166,198)],'gold',8)
    elif e=='energy':
        p.diamond(128,128,79,'gold');p.poly([(140,69),(102,130),(130,130),(111,184),(158,116),(132,116)],'ice',1,'deep',3)
    elif e=='domain_suppress':
        for y in (66,111,156):p.poly([(76,y),(128,y+22),(180,y),(128,y+41)],'slate',1,'deep',3)
        p.line([(92,66),(128,82),(164,66)],'cyan',5)
    return p

def main():
    rows=[]
    for eid,label,vfx in ICON_SPECS:
        p=draw_icon(eid);base=ROOT/'icons';(base/'svg').mkdir(parents=True,exist_ok=True)
        svg=base/'svg'/f'{eid}.svg';atomic_text(svg,'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="128" height="128">\n'+''.join(p.svg)+'\n</svg>\n')
        files={}
        for size in (256,128,64,32):
            out=base/str(size)/f'{eid}.png';out.parent.mkdir(exist_ok=True);atomic_image(p.finish().resize((size,size),Image.Resampling.LANCZOS),out)
            files[str(size)]={'path':str(out.relative_to(ROOT)),'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
        rows.append({'id':eid,'label_zh':label,'related_vfx':vfx,'files':files,'editable_svg':str(svg.relative_to(ROOT)),'svg_sha256':hashlib.sha256(svg.read_bytes()).hexdigest()})
    data={'schema_version':1,'icon_count':len(rows),'raster_sizes':[256,128,64,32],'icons':rows,'source':'scripts/build_icons.py','note':'Original code-authored editable vectors; no font glyphs, official game icons or text baked into PNG.'}
    atomic_text(ROOT/'icons/manifest.json',json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    atomic_text(ROOT/'icons_data.js','window.VOLIBEAR_ICON_DATA='+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n')
    from PIL import ImageDraw,ImageFont
    contact=Image.new('RGB',(1024,4*230),(27,38,47));d=ImageDraw.Draw(contact);font=ImageFont.truetype(str(ROOT/'fonts/proof_sans.ttf'),13)
    for i,row in enumerate(rows):
        x=(i%4)*256;y=(i//4)*230
        for size,dx,dy in [(128,7,12),(64,145,32),(32,211,48)]:
            im=Image.open(ROOT/row['files'][str(size)]['path']).convert('RGBA');contact.paste(im,(x+dx,y+dy),im)
        d.text((x+12,y+159),row['id'],font=font,fill=(225,230,225));d.text((x+12,y+185),'128 px / 64 px / 32 px',font=font,fill=(156,175,186))
    atomic_image(contact,ROOT/'reports/icons_contact.png');print(json.dumps({'icons':len(rows),'png_files':len(rows)*4,'svg_files':len(rows)}))
if __name__=='__main__':main()
