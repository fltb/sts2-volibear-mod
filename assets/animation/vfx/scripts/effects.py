"""Original code-authored VFX for the Volibear asset kit.

Shapes, timing and palettes are editable source; no stock game textures are used.
All coordinates are in a 256 square. Runtime images use straight alpha.
"""
import math
from PIL import Image, ImageDraw, ImageFilter

SPECS = [
    ('claw_slash','爪击划痕','physical',18,False,'target_contact',30),
    ('heavy_impact','重击碎震','physical',24,False,'target_ground',10),
    ('bite_hit','咬合接触','physical',18,False,'target_contact',30),
    ('guard_gain','架起格挡','guard',24,False,'owner_front',20),
    ('guard_hit','格挡受击','guard',16,False,'owner_contact',30),
    ('guard_break','破除格挡','guard',22,False,'target_contact',30),
    ('counter_release','反击释出','guard',22,False,'owner_to_target',20),
    ('absorb','格挡吸收','guard',24,False,'owner_contact',20),
    ('lightning_strike','单体落雷','lightning',22,False,'target_contact',20),
    ('lightning_chain','横向雷路','lightning',20,False,'source_to_target',15),
    ('lightning_all','群体雷幕','lightning',28,False,'resolved_enemy_group',10),
    ('lightning_growth','雷电成长','lightning',24,False,'owner_status',30),
    ('domain_enter','领域展开','domain',36,False,'owner_ground',-20),
    ('domain_loop','领域持续','domain',48,True,'owner_ground',-20),
    ('domain_exit','领域退散','domain',30,False,'owner_ground',-20),
    ('domain_suppress','领域压制','domain',24,False,'target_status',20),
    ('card_purify','卡牌净化','card',28,False,'selected_card',20),
    ('feral_transfer','熊灵传递与侵染','feral',40,False,'owner_to_selected_card',20),
    ('feral_claw','兽化·爪形','feral',30,False,'converted_attack_card',20),
    ('feral_body','兽化·躯形','feral',30,False,'converted_other_card',20),
    ('feral_aura','兽性显现','feral',36,False,'owner_ground',-10),
    ('mark_bite','咬痕标记','status',36,True,'target_status',30),
    ('wound','易伤裂纹','status',22,False,'target_status',30),
    ('weakness','虚弱落势','status',24,False,'target_status',30),
    ('charge','蓄势收拢','status',28,False,'selected_card',20),
    ('strength','力量升腾','status',24,False,'owner_status',20),
    ('armor_retain','留甲锁定','guard',30,False,'owner_status',20),
    ('armor_iron','坚甲固形','guard',30,False,'owner_status',20),
    ('card_draw','抽牌流光','card',22,False,'draw_pile_to_hand',20),
    ('card_retrieve','检索回收','card',28,False,'source_pile_to_hand',20),
    ('card_discard','弃牌落迹','card',22,False,'card_to_discard_pile',20),
    ('card_exhaust','消耗散片','card',26,False,'exhausted_card',20),
    ('energy_gain','能量返还','card',24,False,'owner_energy',20),
    ('cost_reduce','减费压印','card',22,False,'card_cost_anchor',20),
    ('card_replay','重演回响','card',28,False,'played_card',20),
    ('lifesteal','汲取回流','status',30,False,'damaged_target_to_owner',20),
    ('heal','生命回复','status',28,False,'owner_status',20),
    ('roar_wave','咆哮波','physical',26,False,'owner_mouth_to_targets',15),
    ('thunder_armor','雷甲增益','guard',26,False,'owner_front',20),
    ('cast_charge','施法聚雷','lightning',30,False,'owner_hand',15),
]
PAL = {'ink':(21,39,57),'cyan':(91,210,233),'ice':(224,249,242),
       'blue':(47,112,148),'deep':(34,67,87),'gold':(222,173,91),
       'rust':(151,85,60),'pale':(211,215,200),'red':(168,80,70),
       'mint':(112,201,174),'slate':(101,124,137)}
TAU=math.tau

def clamp(v,a=0,b=1):return min(b,max(a,v))
def ease(v):v=clamp(v);return v*v*(3-2*v)
def lerp(a,b,t):return a+(b-a)*t
def env(t):return ease(t/.13)*(1-ease((t-.61)/.39))
def rgba(color,alpha=1):
    col=PAL.get(color,color)
    return tuple(col[:3])+(round(255*clamp(alpha)),)

class Painter:
    def __init__(self,ss=3):
        self.ss=ss;self.im=Image.new('RGBA',(256*ss,256*ss));self.d=ImageDraw.Draw(self.im)
    def xy(self,p):return tuple(round(x*self.ss) for x in p)
    def line(self,points,col='cyan',width=3,a=1):
        self.d.line([self.xy(p) for p in points],fill=rgba(col,a),width=max(1,round(width*self.ss)),joint='curve')
    def poly(self,points,col='cyan',a=1,outline=None,width=2):
        pp=[self.xy(p) for p in points];self.d.polygon(pp,fill=rgba(col,a))
        if outline:self.d.line(pp+[pp[0]],fill=rgba(outline,a),width=max(1,round(width*self.ss)),joint='curve')
    def ellipse(self,box,col='cyan',a=1,width=None):
        b=tuple(round(x*self.ss) for x in box)
        if width:self.d.ellipse(b,outline=rgba(col,a),width=max(1,round(width*self.ss)))
        else:self.d.ellipse(b,fill=rgba(col,a))
    def bolt(self,pts,a=1,width=5,core=True):
        self.line(pts,'ink',width+5,a*.8);self.line(pts,'blue',width+2,a)
        self.line(pts,'cyan',width,a)
        if core:self.line(pts,'ice',max(1,width*.29),a)
    def shard(self,x,y,r,angle,col='gold',a=1,aspect=.35):
        c,s=math.cos(angle),math.sin(angle)
        pts=[]
        for dx,dy in [(r,0),(-r*.2,r*aspect),(-r,0),(-r*.2,-r*aspect)]:
            pts.append((x+dx*c-dy*s,y+dx*s+dy*c))
        self.poly(pts,col,a)
    def shield(self,cx,cy,r,a=1,thick=4,fill=True,col='cyan'):
        pts=[(cx,cy-r),(cx+r*.65,cy-r*.58),(cx+r*.48,cy+r*.3),(cx,cy+r),(cx-r*.48,cy+r*.3),(cx-r*.65,cy-r*.58)]
        if fill:self.poly(pts,'deep',a*.24)
        self.line(pts+[pts[0]],'ink',thick+4,a*.85)
        self.line(pts+[pts[0]],col,thick,a)
        self.line([pts[5],pts[0],pts[1]],'ice',max(1,thick*.35),a*.8)
    def diamond(self,x,y,r,col='cyan',a=1):
        self.poly([(x,y-r),(x+r*.6,y),(x,y+r),(x-r*.6,y)],col,a,'ink',1.8)
        self.poly([(x,y-r),(x,y+r),(x-r*.6,y)],'ice',a*.6)
    def arc(self,cx,cy,rx,ry,start,end,col='cyan',width=3,a=1):
        self.line([(cx+rx*math.cos(start+(end-start)*i/46),cy+ry*math.sin(start+(end-start)*i/46)) for i in range(47)],col,width,a)
    def corners(self,x0=86,y0=48,x1=178,y1=207,a=1,col='cyan',width=3):
        l=15
        for pts in [[(x0,y0+l),(x0,y0),(x0+l,y0)],[(x1-l,y0),(x1,y0),(x1,y0+l)],[(x0,y1-l),(x0,y1),(x0+l,y1)],[(x1-l,y1),(x1,y1),(x1,y1-l)]]:self.line(pts,col,width,a)
    def finish(self):
        return self.im.resize((256,256),Image.Resampling.LANCZOS)

def tapered_slash(p,center,angle,length,width,progress,alpha=1,col='cyan'):
    """Single authored curved wedge, with a sharp leading tip and broad middle."""
    cx,cy=center;c,s=math.cos(angle),math.sin(angle);end=lerp(.15,1,ease(progress/.6))
    l=[];r=[]
    for i in range(30):
        q=end*i/29;u=(q-.5)*length;v=-math.sin(q*math.pi)*length*.17
        w=math.sin(q*math.pi)**.65*width*(1-.6*q)
        l.append((cx+u*c-(v+w)*s,cy+u*s+(v+w)*c))
        r.append((cx+u*c-(v-w)*s,cy+u*s+(v-w)*c))
    p.poly(l+list(reversed(r)),'ink',alpha)
    p.poly([(lerp(cx,x,.97),lerp(cy,y,.97)) for x,y in l+list(reversed(r))],col,alpha)
    p.line([(cx+(q-.5)*length*c+math.sin(q*math.pi)*length*.17*s,
             cy+(q-.5)*length*s-math.sin(q*math.pi)*length*.17*c) for q in [end*i/28 for i in range(29)]],'ice',1.5,alpha*.8)

def ring(p,t,a,rx=88,ry=27,cy=180):
    for k in range(3):
        ang=t*TAU+k*TAU/3
        p.arc(128,cy,rx,ry,ang,ang+1.5,'blue',6,a*.8)
        p.arc(128,cy,rx,ry,ang,ang+1.24,'cyan',2.5,a)
    for k in range(6):
        ang=k*TAU/6
        x,y=128+rx*.8*math.cos(ang),cy+ry*.8*math.sin(ang)
        p.shard(x,y,4,ang,'gold',a*.75)

def radial_shards(p,t,a,cx=128,cy=134,col='gold',count=7,r0=22,r1=84):
    for k in range(count):
        ang=(k+.15)*TAU/count
        rr=lerp(r0,r1,ease(t));r=lerp(12,2,t)*(1+(k%3)*.15)
        p.shard(cx+rr*math.cos(ang),cy+rr*.75*math.sin(ang),r,ang,col,a)

def card_stream(p,t,a,mode):
    # Abstract motion accents: actual cards remain the engine-owned nodes.
    for k in range(3):
        q=clamp(t*1.5-k*.14);x=lerp(42,208,q);y=155-52*math.sin(q*math.pi)+k*10
        if mode=='discard':x=lerp(55,208,q);y=lerp(67,201,q)+14*math.sin(q*math.pi)
        if mode=='retrieve':x=lerp(42,206,q);y=182-98*math.sin(q*math.pi*.7)+k*5
        aa=a*math.sin(q*math.pi)
        p.line([(x-26,y+9),(x-12,y+4),(x,y)],'cyan',3,aa)
        p.line([(x-22,y+16),(x-4,y+8)],'blue',2,aa*.8)
        p.shard(x+3,y,8,-.3,'pale',aa)

def render(effect,t,loop=False):
    p=Painter();a=(.72+.18*math.sin(t*TAU)) if loop else env(t)
    if not loop and (t<=0 or t>=1):return p.finish()
    if effect=='claw_slash':
        for k in range(3):tapered_slash(p,(122+k*14,101+k*21),-.72,177-11*k,9-k,t,a*(1-.1*k))
        for k in range(4):p.shard(181+k*8,84+k*12,7*(1-t),-.8,'gold',a*.65)
    elif effect=='heavy_impact':
        q=ease(t/.45)
        p.poly([(78,40),(116,116),(103,120),(138,166),(149,128),(129,130),(121,44)],'gold',a*.75,'ink',3)
        p.arc(128,181,25+77*q,8+18*q,0,TAU,'gold',4,a*.8)
        for k in range(7):
            ang=math.pi+(k+.4)*math.pi/7;rr=35+55*q
            p.shard(128+math.cos(ang)*rr,181+math.sin(ang)*rr*.7,11*(1-.7*t),ang,'slate' if k%2 else 'gold',a, .6)
        p.line([(101,172),(115,166),(125,179),(137,169),(157,174)],'ice',3,a)
    elif effect=='bite_hit':
        gap=lerp(52,9,ease(t/.45))
        for side in (-1,1):
            for k in range(3):
                x=97+k*31;y=128+side*gap
                p.poly([(x-9,y+side*14),(x+8,y+side*11),(x+3,y-side*18)],'pale',a,'ink',2.5)
            p.arc(128,128+side*13,68,gap+18,math.pi if side<0 else 0,TAU if side<0 else math.pi,'gold',3,a*.7)
        radial_shards(p,t,a*.6,count=5,r0=12,r1=80)
    elif effect in ('guard_gain','guard_hit','thunder_armor'):
        r=56+7*ease(t/.35);p.shield(128,129,r,a,4)
        p.line([(109,102),(128,92),(147,103)],'gold',3,a*.8)
        if effect=='guard_hit':
            radial_shards(p,t,a,cx=177,cy=104,count=5,r0=4,r1=42)
            p.poly([(158,104),(172,90),(181,106),(169,119)],'ice',a*.8)
        elif effect=='thunder_armor':
            p.bolt([(140,85),(121,119),(137,120),(116,163)],a,5)
            p.bolt([(76,115),(67,139),(79,144)],a*.7,2.5)
            p.bolt([(181,114),(189,136),(181,149)],a*.7,2.5)
        else:p.line([(112,135),(124,148),(147,115)],'cyan',3,a*.75)
    elif effect=='guard_break':
        q=ease(t);r=57
        shapes=[[(128,72),(163,96),(158,123),(139,113),(130,93)],[(158,137),(151,166),(128,188),(136,150)],[(119,92),(99,108),(105,144),(118,136)],[(97,150),(107,172),(127,188),(122,158)]]
        shifts=[(34,-25),(31,30),(-30,-11),(-25,29)]
        for pts,(dx,dy) in zip(shapes,shifts):p.poly([(x+q*dx,y+q*dy) for x,y in pts],'slate',a,'cyan',2)
        p.bolt([(142,84),(118,117),(136,134),(115,172)],a,4)
    elif effect=='counter_release':
        q=ease(t/.7);x=86+98*q
        p.poly([(x-75,69),(x+21,127),(x-74,190),(x-25,128)],'deep',a*.6)
        p.poly([(x-32,78),(x+21,127),(x-32,179),(x-9,128)],'cyan',a,'ink',3)
        p.line([(x-14,98),(x+15,127),(x-14,157)],'ice',2,a)
        p.line([(37,115),(x-37,121)],'gold',3,a*.7)
        p.line([(31,145),(x-42,137)],'blue',3,a*.75)
    elif effect=='absorb':
        q=ease(t)
        p.shield(126,134,32+6*q,a,2.4,False)
        for k in range(6):
            ang=(k+.3)*TAU/6;rr=94*(1-q)+12
            p.shard(126+math.cos(ang)*rr,134+math.sin(ang)*rr*.8,11*(1-.55*q),ang,'gold',a)
        p.diamond(126,134,8,a=a)
    elif effect=='lightning_strike':
        pts=[(139,27),(118,69),(140,85),(115,129),(136,143),(122,192)]
        aa=a*(.8+.2*math.sin(t*TAU*3)**2)
        p.bolt(pts,aa,8-4*t)
        p.bolt([(135,87),(168,101),(158,122),(183,145)],aa*.65,3)
        p.bolt([(119,126),(89,146),(101,160),(84,178)],aa*.65,2.5)
        p.arc(124,202,13+36*t,5+11*t,0,TAU,'blue',3,a*.7)
        radial_shards(p,t,a*.6,124,199,count=5,r0=4,r1=35)
    elif effect=='lightning_chain':
        end=38+183*ease(t/.35)
        pts=[(30,128),(64,114),(85,138),(111,108),(143,132),(173,112),(203,130),(end,128)]
        pts=[(min(x,end),y) for x,y in pts]
        p.bolt(pts,a,5)
        p.bolt([(92,134),(113,164),(137,151)],a*.55,2.2)
        p.bolt([(171,113),(181,90),(201,97)],a*.55,2.2)
        for x in (30,end):p.diamond(x,128,8,a=a*.8)
    elif effect=='lightning_all':
        for k in range(3):
            x=65+k*63;sub=clamp((t-k*.035)/.85);aa=env(sub)
            p.bolt([(x+7,39+k%2*10),(x-9,81),(x+10,95),(x-5,142),(x+3,179)],aa,5)
            p.arc(x,188,18+14*sub,6+6*sub,0,TAU,'cyan',2.2,aa*.7)
        p.line([(37,199),(73,211),(124,204),(170,213),(218,199)],'blue',3,a*.4)
    elif effect=='lightning_growth':
        p.bolt([(142,70),(116,113),(136,113),(112,171)],a,6)
        for k in range(3):
            x=78+k*50;h=19+13*k
            p.poly([(x-9,201),(x-9,201-h),(x,192-h),(x+9,201-h),(x+9,201)],'gold',a*.6)
        p.arc(127,133,55,59,-2.9,-1.5,'blue',3,a*.7)
    elif effect.startswith('domain_'):
        if effect=='domain_suppress':
            for k in range(3):
                y=53+k*51+11*ease(t)
                p.poly([(75,y),(128,y+23),(181,y),(128,y+42)],'slate',a*(.8-.14*k),'ink',2)
                p.line([(88,y+5),(128,y+23),(168,y+5)],'cyan',2,a*.65)
        else:
            if effect=='domain_enter':
                rr=25+66*ease(t/.6);aa=a;phase=t*.7
            elif effect=='domain_exit':
                rr=89+12*t;aa=a*(1-t);phase=-t*.3
            else:rr=88;aa=.5+.12*math.sin(t*TAU);phase=t
            ring(p,phase,aa,rr,rr*.30)
            for k in range(3):
                x=65+63*k;u=(t+k/3)%1 if loop else t
                h=24+73*math.sin(clamp(u)*math.pi)
                p.bolt([(x,168),(x-8,142),(x+4,168-h)],aa*.33,2,False)
            if effect=='domain_enter':p.arc(128,180,rr*.78,rr*.2,0,TAU,'ice',1.6,a*.7)
            if effect=='domain_exit':
                for k in range(9):p.shard(48+20*k,180-30*t-(k%3)*7,4*(1-t),-.5,'cyan',a*.5)
    elif effect=='card_purify':
        p.corners(a=a*.6,col='pale')
        q=ease(t);y=195-142*q
        p.poly([(81,y+17),(178,y-32),(178,y-18),(81,y+32)],'ice',a*.6)
        p.line([(81,y+17),(178,y-32)],'mint',4,a)
        for k in range(7):
            x=88+(k*19)%85;yy=y+20-((k*23)%50)
            p.shard(x+17*t,max(19,yy-28*t),4*(1-t)+1,-1,'mint',a*.65)
    elif effect=='feral_transfer':
        # A visibly external source transfers to a selected card, then stains
        # only its lower-right region. It never changes the owner's anatomy.
        q=ease(clamp(t/.63));cx=lerp(38,170,q);cy=lerp(181,125,q)-32*math.sin(q*math.pi)
        pts=[]
        for k in range(28):
            u=clamp(q-k*.009);pts.append((lerp(38,170,u),lerp(181,125,u)-32*math.sin(u*math.pi)))
        p.line(pts,'deep',14,a*.7);p.line(pts,'cyan',3,a)
        p.arc(cx,cy,10,17,t*TAU*1.8,t*TAU*1.8+4.8,'gold',3,a)
        p.diamond(cx,cy,7,a=a)
        stain=ease((t-.48)/.29)
        if stain>0:
            center=(161,121);border=[(151,92),(174,102),(169,118),(178,133),(162,145),(151,151),(139,136),(143,124),(133,113),(149,108)]
            p.poly([(lerp(center[0],x,stain),lerp(center[1],y,stain)) for x,y in border],'deep',a*.88,'gold',1.5)
            for k in range(3):tapered_slash(p,(150+k*5,116+k*7),-.9,28,3,stain,a*.7)
        p.corners(a=a*.4,col='slate')
    elif effect in ('feral_claw','feral_body'):
        p.corners(a=a*.75,col='gold',width=3)
        if effect=='feral_claw':
            for k in range(3):tapered_slash(p,(112+k*15,113+k*15),-1.0,102,8,t,a,col='pale')
            p.line([(95,176),(116,189),(143,180),(164,189)],'cyan',2,a*.7)
        else:
            p.shield(130,126,50,a,4,col='pale')
            p.bolt([(139,96),(119,123),(136,128),(118,158)],a*.8,3)
        for k in range(4):p.shard(76+k*34,216-12*t,4,-.6,'gold',a*.7)
    elif effect=='feral_aura':
        for k in range(5):
            x=64+k*32;h=25+18*math.sin(k*.9)
            p.poly([(x-10,188),(x+2,166-h*ease(t/.6)),(x+7,174),(x+13,148-h*ease(t/.6)),(x+19,190)],'deep',a*.5)
            p.line([(x+2,179),(x+10,164)],'gold',2,a*.65)
        p.arc(128,197,90,19,.1,3.0,'gold',3,a*.7)
    elif effect=='mark_bite':
        pulse=1+.025*math.sin(t*TAU);cx=128;cy=132
        for side in (-1,1):
            p.arc(cx,cy,40*pulse,30*pulse,math.pi+.2 if side<0 else .2,TAU-.2 if side<0 else math.pi-.2,'rust',7,.85)
            for k in range(3):
                x=107+k*21;y=132+side*(22 if k==1 else 18)
                p.poly([(x-5,y+side*5),(x+5,y+side*5),(x,y-side*7)],'gold',.85)
        p.diamond(128,132,6,col='gold',a=.6+.12*math.sin(t*TAU))
    elif effect=='wound':
        for k in range(3):tapered_slash(p,(105+k*23,118+k*12),-.94,106,7,t,a,'red')
        p.line([(87,173),(104,181),(117,173)],'rust',2,a*.65)
    elif effect=='weakness':
        for k in range(3):
            x=84+k*44;y=77+12*ease(t)
            p.line([(x,y),(x-9,y+37),(x+6,y+48),(x-5,y+74)],'slate',6,a)
            p.poly([(x-17,y+67),(x-5,y+88),(x+7,y+63)],'gold',a*.8)
    elif effect=='charge':
        q=ease(t/.7)
        p.corners(a=a*.45,col='gold')
        for k in range(3):
            y=88+k*39;dx=36*(1-q)
            p.poly([(54+dx,y-14),(86+dx,y),(54+dx,y+14),(64+dx,y)],'gold',a*.8)
            p.poly([(202-dx,y-14),(170-dx,y),(202-dx,y+14),(192-dx,y)],'gold',a*.8)
        p.diamond(128,128,13,a=a)
    elif effect=='strength':
        for k in range(3):
            x=84+k*44;y=171-(26 if k==1 else 0)-25*ease(t)
            p.poly([(x-12,y+29),(x-12,y-9),(x-23,y-9),(x,y-41),(x+23,y-9),(x+12,y-9),(x+12,y+29)],'gold',a,'ink',2.5)
            p.line([(x-6,y+16),(x-6,y-13),(x,y-23)],'pale',2,a*.7)
    elif effect in ('armor_retain','armor_iron'):
        p.shield(128,131,64,a,6,col='slate' if effect=='armor_iron' else 'gold')
        if effect=='armor_retain':
            p.line([(106,135),(106,114),(128,102),(150,114),(150,135)],'pale',5,a)
            p.poly([(102,127),(154,127),(154,160),(128,172),(102,160)],'gold',a*.8,'ink',2)
            p.diamond(128,145,8,'deep',a)
        else:
            for k in range(3):
                y=99+k*27;p.poly([(101,y),(128,y+8),(155,y),(150,y+19),(128,y+28),(106,y+19)],'pale',a*.8,'ink',2)
            p.line([(128,80),(128,190)],'gold',3,a*.7)
    elif effect in ('card_draw','card_retrieve','card_discard'):
        card_stream(p,t,a,effect.removeprefix('card_'))
        if effect=='card_retrieve':p.arc(82,160,32,40,1.2,5.0,'gold',2,a*.6)
    elif effect=='card_exhaust':
        q=ease(t);p.corners(a=a*(1-q),col='slate')
        for k in range(16):
            x=92+(k*23)%77;y=60+(k*37)%141
            dx=((k%5)-2)*15*q;dy=-45*q-(k%3)*9*q
            p.shard(x+dx,y+dy,6*(1-q)+1,-1+.2*k,'slate' if k%3 else 'gold',a*.8,aspect=.7)
    elif effect=='energy_gain':
        p.diamond(128,128,26+5*math.sin(t*math.pi),'gold',a)
        p.line([(130,102),(117,127),(132,127),(121,149)],'ice',3,a)
        for k in range(5):
            ang=k*TAU/5;rr=79*(1-ease(t))+27
            p.shard(128+math.cos(ang)*rr,128+math.sin(ang)*rr,8,ang,'gold',a*.7)
    elif effect=='cost_reduce':
        for k in range(2):
            y=83+k*48+12*ease(t)
            p.poly([(83,y),(128,y+24),(173,y),(128,y+45)],'cyan',a*(1-.25*k),'ink',3)
        p.line([(97,201),(159,201)],'gold',3,a*.6)
    elif effect=='card_replay':
        for k in range(3):
            shift=(2-k)*11;p.corners(78+shift,49+shift,163+shift,190+shift,a*(.33+.24*k),'cyan',2.4)
        p.arc(128,130,52,43,3.7,6.4,'gold',4,a)
        p.poly([(177,119),(187,143),(165,138)],'gold',a)
        p.arc(128,130,52,43,.6,3.3,'gold',4,a*.7)
        p.poly([(79,143),(69,119),(91,124)],'gold',a*.7)
    elif effect=='lifesteal':
        q=ease(t);pts=[]
        for k in range(35):
            u=clamp(q-k*.013);pts.append((216-176*u,142-39*math.sin(u*math.pi)))
        p.line(pts,'deep',11,a*.8);p.line(pts,'mint',3,a)
        x,y=pts[0];p.diamond(x,y,9,'mint',a)
        for k in range(3):p.shard(203-k*8-116*q,156-k*8-12*math.sin(q*math.pi),4,-2.7,'red',a*.6)
    elif effect=='heal':
        for k in range(5):
            q=(t+k*.13)%1;x=76+k*26;y=190-105*q
            p.poly([(x,y-10),(x+6,y),(x,y+9),(x-6,y)],'mint',a*(.6+.3*math.sin(q*math.pi)))
        p.poly([(119,92),(137,92),(137,115),(159,115),(159,133),(137,133),(137,156),(119,156),(119,133),(97,133),(97,115),(119,115)],'pale',a*.65,'ink',2)
    elif effect=='roar_wave':
        for k in range(3):
            q=clamp((t-k*.09)*1.35);x=55+112*q;r=26+36*q
            aa=math.sin(q*math.pi)*a
            p.line([(x,r*-1+128),(x+20,128-r*.4),(x+27,128),(x+20,128+r*.4),(x,128+r)],'ink',8,aa)
            p.line([(x,r*-1+128),(x+20,128-r*.4),(x+27,128),(x+20,128+r*.4),(x,128+r)],'pale',4,aa)
            p.line([(x+25,122),(x+29,128),(x+25,134)],'gold',2,aa)
    elif effect=='cast_charge':
        q=ease(t/.65);rr=70-42*q
        for k in range(3):
            ang=k*TAU/3+t*1.6
            pts=[]
            for j in range(3):
                r=rr+12*j;an=ang+.25*j;pts.append((128+math.cos(an)*r,128+math.sin(an)*r))
            p.bolt(pts,a*.8,3)
        p.diamond(128,128,12+9*q,a=a)
        p.arc(128,128,25,32,t*TAU,t*TAU+4,'gold',2,a*.6)
    else:raise KeyError(effect)
    return p.finish()
