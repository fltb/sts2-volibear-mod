from pathlib import Path
import io,json,os,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFilter

ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1]
W,H=1312,1199
def atomic(p,data):
    p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name('.'+p.name+'.tmp');t.write_bytes(data);os.replace(t,p)
def save(p,im):
    b=io.BytesIO();im.save(b,format='PNG');atomic(p,b.getvalue())
def js(p,obj):atomic(p,(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode())
def polygon(points):
    im=Image.new('L',(W*2,H*2));ImageDraw.Draw(im).polygon([(x*2,y*2) for x,y in points],fill=255)
    return np.array(im.resize((W,H),Image.Resampling.LANCZOS))/255.
def source(path):
    im=Image.open(path).convert('RGBA');im.load();return im
ref=source(REPO/'references/identity/volibear_approved.png')
core=source(ROOT/'source/core_without_spikes.png')
assert core.size==(W,H)
near=Image.new('RGBA',(W,H));near.alpha_composite(source(ROOT/'source/near_arm_complete_candidate.png').resize((650,710),Image.Resampling.LANCZOS),(60,240))
far=source(ROOT/'source/far_arm_complete.png')
xx,yy=np.meshgrid(np.arange(W),np.arange(H))
def cap(joint,direction,radius,keep_before=True,width=None):
    dx=xx-joint[0];dy=yy-joint[1];v=np.array(direction,dtype=float);v/=np.linalg.norm(v)
    along=dx*v[0]+dy*v[1];across=-dx*v[1]+dy*v[0]
    full=along<=0 if keep_before else along>=0
    width=radius if width is None else width
    disc=np.clip((1-np.sqrt((along/radius)**2+(across/width)**2))*min(radius,width)/1.5+.5,0,1)
    return np.where(full,1.,disc)
parts={}
def part(name,im,mask,bone,z,mesh=None):
    a=np.array(im);a[:,:,3]=np.round(a[:,:,3]*mask).astype(np.uint8);a[a[:,:,3]==0,:3]=0
    out=Image.fromarray(a);bb=out.getbbox();assert bb,name
    out=out.crop(bb)
    file='parts/'+name+'.png';save(ROOT/file,out)
    parts[name]={'file':file,'origin':list(bb[:2]),'size':list(out.size),'bone':bone,'z':z,'source_bounds':list(bb),'overlap':'painted source surface retained beyond joint; rounded overlapping caps','mesh':mesh}

# Logical anatomical silhouettes overlap. They are not exclusive ownership masks.
leg_sources={}
for side,origin,size in [('near',(100,650),(600,549)),('far',(660,690),(470,509))]:
    canvas=Image.new('RGBA',(W,H));canvas.alpha_composite(source(ROOT/f'source/{side}_leg_complete_candidate.png').resize(size,Image.Resampling.LANCZOS),origin);leg_sources[side]=canvas
for side,hip,knee,ankle,d1,d2,z in [
 ('far',(795,800),(915,940),(930,1080),(120,140),(15,140),0),
 ('near',(540,800),(365,975),(260,1100),(-175,175),(-105,125),3)]:
    part('thigh_'+side,leg_sources[side],cap(knee,d1,95),'hip_'+side,z)
    part('shin_'+side,leg_sources[side],cap(knee,d1,95,False)*cap((ankle[0],ankle[1]-30),(0,1),40,True,115),'knee_'+side,z+1)
    part('foot_'+side,leg_sources[side],cap((ankle[0],ankle[1]-30),(0,1),40,False,115),'ankle_'+side,z+2)

for side,im,elbow,wrist,d1,d2,z in [
 ('far',far,(1095,680),(1145,750),(95,155),(50,70),6),
 ('near',near,(340,550),(195,760),(-190,190),(0,1),15)]:
    elbow_radius=85 if side=='near' else 125
    upper_mask=cap(elbow,d1,elbow_radius)
    if side=='near':
        axis=np.array([-230,245],dtype=float);axis/=np.linalg.norm(axis)
        along=(xx-530)*axis[0]+(yy-360)*axis[1]
        socket=np.clip((55-along)/95,0,1)
        # Concealed shoulder-root paint must not project beyond the mane on rotation.
        root_trim=np.clip((along+35)/45,0,1)
        im=im.copy();alpha=np.array(im.getchannel('A'),dtype=float)
        im.putalpha(Image.fromarray(np.uint8(np.round(alpha*root_trim))))
        # The concealed root follows the arm behind the chest, not above the mane.
        part('upper_arm_socket_near',im,upper_mask*socket,'shoulder_near',9.5)
        upper_mask=upper_mask*(1-socket)
    part('upper_arm_'+side,im,upper_mask,'shoulder_'+side,z)
    part('forearm_'+side,im,cap(elbow,d1,elbow_radius,False)*cap(wrist,d2,25 if side=='far' else 30,True,110),'elbow_'+side,z+1)
    part('hand_'+side,im,cap(wrist,d2,25 if side=='far' else 30,False,110),'wrist_'+side,z+2)

spikes=polygon([(270,360),(280,215),(420,205),(325,85),(480,140),(430,0),(640,45),(680,130),(685,75),(820,130),(860,210),(740,245),(620,330),(480,285),(365,360)])
colors=np.array(ref).astype(float);blue=np.clip((colors[:,:,2]-colors[:,:,0]*1.05)/10,0,1)
part('back_spikes',ref,spikes*blue,'back',9)
torso=polygon([(335,430),(350,330),(460,240),(550,155),(640,120),(745,140),(850,210),(925,330),(1030,460),(1060,600),(970,735),(870,800),(800,835),(755,900),(695,975),(625,945),(580,865),(490,790),(390,735),(410,650),(370,550)])
# Blend only where a complete thigh already exists underneath. Never erase silhouette.
leg_coverage=np.zeros((H,W),dtype=float)
for side in ['near','far']:
    info=parts['thigh_'+side];layer=Image.new('RGBA',(W,H));layer.alpha_composite(source(ROOT/info['file']),tuple(info['origin']))
    leg_coverage=np.maximum(leg_coverage,np.array(layer.getchannel('A'))/255.)
inner=Image.fromarray(np.uint8(torso*255)).filter(ImageFilter.MinFilter(65)).filter(ImageFilter.GaussianBlur(12))
transition=np.array(inner)/255.
coverage_inner=Image.fromarray(np.uint8(leg_coverage*255)).filter(ImageFilter.MinFilter(21)).filter(ImageFilter.GaussianBlur(5))
coverage=np.array(coverage_inner)/255.
zone=np.clip((yy-660)/90,0,1)
blend=coverage*zone
torso=torso*(1-blend+blend*transition)
# The underpaint includes original thigh-root fur as well as the separate leg.
# Remove only the duplicate interior overlay where an opaque thigh exists below.
# Retain the crotch silhouette and all uncovered waist/hip pixels.
root_overlap=coverage*np.clip((yy-770)/100,0,1)
torso=torso*(1-root_overlap)
part('torso',core,torso,'chest',10,'torso')
# Common canvas, distinct lower jaw silhouettes: never crop open jaw to closed bounds.
head_round=np.clip((1-np.sqrt(((xx-850)/150)**2+((yy-310)/165)**2))*100+.5,0,1)
head_front=polygon([(850,170),(960,165),(1040,215),(1140,295),(1140,395),(1064,440),(1054,487),(1025,504),(997,488),(970,470),(948,446),(925,440),(850,410)])
head=np.maximum(head_round,head_front)
contours={'closed':[(925,438),(958,433),(985,431),(1014,445),(1050,451),(1080,427)],'half':[(925,438),(950,430),(979,447),(1006,451),(1034,464),(1060,455),(1080,430)],'open':[(925,438),(948,446),(970,470),(997,488),(1025,504),(1054,487),(1080,430)]}
parts['head']={'file':'parts/head.png','origin':[700,145],'size':[440,370],'bone':'head','z':11,'source_bounds':[700,145,1140,515],'mesh':'head','overlap':'rounded rear head with per-cel clean jaw silhouette','cels':[]}
for cel,file in [('closed',None),('half','animations/source/revision_v3/mouth_half_edit.png'),('open','animations/source/revision_v2/mouth_open_edit.png')]:
    a=np.array(core,dtype=float)
    if file:
        paint=np.array(source(REPO/file),dtype=float)
        blend=np.clip((xx-940)/40,0,1)*np.clip((yy-300)/35,0,1)
        a=a*(1-blend[:,:,None])+paint*blend[:,:,None]
    cut=polygon([(690,130),(1150,130),(1150,410)]+list(reversed(contours[cel]))+[(900,468),(850,480),(690,480)])
    a[:,:,3]*=head*cut;a=np.uint8(np.round(a));a[a[:,:,3]==0,:3]=0
    file='parts/head.png' if cel=='closed' else 'parts/head_'+cel+'.png'
    save(ROOT/file,Image.fromarray(a).crop(parts['head']['source_bounds']));parts['head']['cels'].append(file)


braids=source(ROOT/'source/braids_complete.png')
# Match reference gray fur; preserve dark metal and saturated cyan rune pixels.
ba=np.array(braids,dtype=float);rgb=ba[:,:,:3]
fur=np.clip((rgb.min(axis=2)-105)/55,0,1)*np.clip((45-(rgb.max(axis=2)-rgb.min(axis=2)))/20,0,1)
gray=rgb.mean(axis=2,keepdims=True)
target=rgb*.45+gray*.55-14
ba[:,:,:3]=np.clip(rgb*(1-fur[:,:,None])+target*fur[:,:,None],0,255)
braids=Image.fromarray(np.uint8(np.round(ba)))
for side,i,box in [('near',0,(700,343,820,844)),('far',1,(940,430,1030,861))]:
    b=braids.crop((i*braids.width//2,0,(i+1)*braids.width//2,braids.height));bbox=Image.fromarray((np.array(b.getchannel('A'))>32).astype(np.uint8)*255).getbbox();b=b.crop(bbox).resize((box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS)
    # Reference fur-interior landmarks: preserve entire metal/rune bands.
    a=np.array(b);rgb=a[:,:,:3].astype(float)
    mask=np.clip((rgb.min(2)-130)/40,0,1)*np.clip((35-np.ptp(rgb,axis=2))/15,0,1)
    bands={'near':[(0,90),(154,217),(366,501)],'far':[(0,72),(132,184),(320,431)]}[side]
    y=np.arange(a.shape[0]);spatial=np.zeros(a.shape[0])
    for lo,hi in bands:
        spatial=np.maximum(spatial,np.clip(np.minimum((y-lo)/6,(hi-1-y)/6),0,1))
    mask*=spatial[:,None]
    a[:,:,:3]=np.uint8(np.round(np.clip(rgb-mask[:,:,None]*np.array([5,10,15]),0,255)))
    b=Image.fromarray(a)
    canvas=Image.new('RGBA',(W,H));canvas.alpha_composite(b,box[:2]);part('braid_'+side,canvas,np.ones((H,W)),'braid_'+side+'_0',10 if side=='far' else 13,'braid_'+side)

bones={}
def bone(name,parent,point):bones[name]={'parent':parent,'rest_world':list(point)}
bone('root',None,(675,850));bone('pelvis','root',(675,850));bone('spine','pelvis',(690,650));bone('chest','spine',(690,430));bone('neck','chest',(820,350));bone('head','neck',(870,310));bone('back','chest',(610,230))
for side,points in [('near',[(530,360),(340,550),(195,760),(205,865)]),('far',[(1000,525),(1095,680),(1145,750),(1245,865)])]:
    parent='chest'
    for joint,p in zip(['shoulder','elbow','wrist','hand_tip'],points):name=joint+'_'+side;bone(name,parent,p);parent=name
for side,points in [('near',[(540,800),(365,975),(260,1100),(250,1160)]),('far',[(795,800),(915,940),(930,1080),(955,1145)])]:
    parent='pelvis'
    for joint,p in zip(['hip','knee','ankle','toe'],points):name=joint+'_'+side;bone(name,parent,p);parent=name
for side,x,ys in [('near',755,[365,485,610,740]),('far',983,[450,550,650,770])]:
    parent='neck'
    for i,y in enumerate(ys):name='braid_'+side+'_'+str(i);bone(name,parent,(x,y));parent=name
for n,b in bones.items():b['local']=(np.array(b['rest_world'])-(np.array(bones[b['parent']]['rest_world']) if b['parent'] else np.zeros(2))).tolist()
# User-authored PNG overrides are authoritative; retain exact bytes and canvas origin.
for name in ('head','head_half','head_open','upper_arm_near','torso'):
    override=ROOT/'source/user_overrides'/f'{name}.png'
    if override.exists():
        image=source(override)
        owner='head' if name.startswith('head') else name
        assert list(image.size)==parts[owner]['size'], (name,image.size,parts[owner]['size'])
        atomic(ROOT/'parts'/f'{name}.png',override.read_bytes())
js(ROOT/'rig.json',{'status':'in_progress_small_pose_review','reference':'../../references/identity/volibear_approved.png','canvas':[W,H],'bones':bones,'parts':parts,'principle':'Complete overlapping anatomical surfaces; visual reference similarity, not zero pixel difference','production_approved':False})
neutral=Image.new('RGBA',(W,H))
for n,p in sorted(parts.items(),key=lambda item:item[1]['z']):neutral.alpha_composite(source(ROOT/p['file']),tuple(p['origin']))
save(ROOT/'previews/neutral_assembly.png',neutral)
# Actual standalone texture review, never fill empty regions with another part.
board=Image.new('RGB',(1200,1200),(27,39,52));d=ImageDraw.Draw(board)
for i,(name,p) in enumerate(parts.items()):
    cell=(i%4*300,i//4*240);im=source(ROOT/p['file']);im.thumbnail((280,210),Image.Resampling.LANCZOS)
    board.paste(im,(cell[0]+(300-im.width)//2,cell[1]+20),im);d.text((cell[0]+8,cell[1]+4),name,fill=(225,237,242))
save(ROOT/'review/parts_contact.png',board)
print(json.dumps({'parts':len(parts),'bones':len(bones),'status':'pending_visual_review'}))
