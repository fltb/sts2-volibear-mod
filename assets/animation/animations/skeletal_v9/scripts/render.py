from pathlib import Path
import json,math,io,os,hashlib,argparse
import numpy as np
from PIL import Image,ImageDraw
from leg_deformation import NEAR_BEND_CAP, sector_vertex
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1]
RIG=json.loads((ROOT/'rig.json').read_text());BONES=RIG['bones'];PARTS=RIG['parts']
MOTION_DATA=json.loads((REPO/'animations/rig/motions.json').read_text());MOTIONS=MOTION_DATA['clips']+MOTION_DATA.get('variants',[]);CLIPS={c['name']:c for c in MOTIONS}
def atomic(p,data):
    p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name('.'+p.name+'.tmp');t.write_bytes(data);os.replace(t,p)
def save(p,im):
    b=io.BytesIO();im.save(b,format='PNG');atomic(p,b.getvalue())
def js(p,d):atomic(p,(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode())
def rot(a):return np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
def interpolate(keys,t):
    if t<=keys[0][0]:return keys[0][1]
    if t>=keys[-1][0]:return keys[-1][1]
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if a<=t<=b:
            f=(t-a)/(b-a);f=f*f*(3-2*f);return x+(y-x)*f
def world(angles,offsets):
    out={}
    for n,b in BONES.items():
        local=np.array(b['local'])+offsets.get(n,np.zeros(2))
        if b['parent']:
            p,a=out[b['parent']];out[n]=(p+rot(a)@local,a+angles[n])
        else:out[n]=(local,angles[n])
    return out
def rest_bend(side,proximal='shoulder',middle='elbow',distal='wrist'):
    first,joint,last=[np.array(BONES[n+'_'+side]['rest_world'],float) for n in (proximal,middle,distal)]
    u=joint-first;v=last-joint
    return math.atan2(u[0]*v[1]-u[1]*v[0],float(np.dot(u,v)))

def leg_target(side,p,air):
    target=np.array(BONES['ankle_'+side]['rest_world'],float)+air
    # Deliberately airborne clips retain their authored translation and leg tuck.
    return target+np.array([40 if side=='near' else -30,-85])*p.get('air',0)

def solve_legs(a,offsets,p,air):
    initial=world(a,offsets);legs=[];lower=-math.inf;upper=math.inf
    for side in ('near','far'):
        hip,knee,ankle=[n+'_'+side for n in ('hip','knee','ankle')]
        h0,k0,f0=[np.array(BONES[n]['rest_world'],float) for n in (hip,knee,ankle)]
        l1=np.linalg.norm(k0-h0);l2=np.linalg.norm(f0-k0)
        target=leg_target(side,p,air);hp=initial[hip][0]
        # Keep at least the rest bend: a near-straight rest leg cannot support
        # upward root translation without either pelvis compensation or foot slip.
        max_reach=min(np.linalg.norm(f0-h0),l1+l2-1e-6)
        dx=target[0]-hp[0]
        if abs(dx)>max_reach:
            raise ValueError('Leg target exceeds horizontal reach: '+side)
        extent=math.sqrt(max(0.,max_reach*max_reach-dx*dx))
        lower=max(lower,target[1]-hp[1]-extent)
        upper=min(upper,target[1]-hp[1]+extent)
        legs.append((hip,knee,ankle,h0,k0,f0,l1,l2,target))
    if lower>upper:raise ValueError('No shared pelvis height can reach both feet')
    correction=float(np.clip(0.,lower,upper))
    offsets['root']=offsets.get('root',np.zeros(2))+np.array([0.,correction])
    initial=world(a,offsets)
    for hip,knee,ankle,h0,k0,f0,l1,l2,target in legs:
        hp=initial[hip][0];d=target-hp;dist=np.linalg.norm(d)
        if dist<abs(l1-l2)+1e-6:raise ValueError('Leg target inside minimum reach: '+hip)
        # User-corrected near knee bends toward image-right, not the almost
        # straight source knee's outward branch. Keep far-leg branch unchanged.
        axis=f0-h0;k=k0-h0;cross=axis[0]*k[1]-axis[1]*k[0]
        sign=-1 if hip=='hip_near' else (1 if cross>=0 else -1)
        if hip=='hip_near':
            # Follow the unchanged far IK's flexion, with one gain for ALL clips.
            # Never normalize a small action to the full near-knee range.
            fh,fk,fa,fh0,fk0,ff0,fl1,fl2,ftarget=legs[1]
            far_dist=np.linalg.norm(ftarget-initial[fh][0])
            far_bend=math.acos(float(np.clip((far_dist*far_dist-fl1*fl1-fl2*fl2)/(2*fl1*fl2),-1,1)))
            far_rest=math.acos(float(np.clip((np.linalg.norm(ff0-fh0)**2-fl1*fl1-fl2*fl2)/(2*fl1*fl2),-1,1)))
            near_rest=math.acos(float(np.clip((np.linalg.norm(f0-h0)**2-l1*l1-l2*l2)/(2*l1*l2),-1,1)))
            # 100 degrees is a shared full-tuck reference, not a per-clip peak.
            gain=(NEAR_BEND_CAP-near_rest)/(math.radians(100.)-far_rest)
            desired=float(np.clip(near_rest+gain*(far_bend-far_rest),0.,NEAR_BEND_CAP))
            reach=math.sqrt(l1*l1+l2*l2+2*l1*l2*math.cos(desired))
            # Solve length from the desired angle, without a bend/compress switch.
            compression=dist/reach
            offsets[knee]=np.array(BONES[knee]['local'])*(compression-1.)
            offsets[ankle]=np.array(BONES[ankle]['local'])*(compression-1.)
            l1*=compression;l2*=compression
        phi=math.atan2(d[1],d[0])
        bend=math.acos(float(np.clip((l1*l1+dist*dist-l2*l2)/(2*l1*dist),-1,1)))
        theta=phi+sign*bend;kp=hp+l1*np.array([math.cos(theta),math.sin(theta)])
        theta2=math.atan2(target[1]-kp[1],target[0]-kp[0])
        rest1=math.atan2(k0[1]-h0[1],k0[0]-h0[0]);rest2=math.atan2(f0[1]-k0[1],f0[0]-k0[0])
        parent_angle=initial[BONES[hip]['parent']][1]
        a[hip]=theta-rest1-parent_angle
        # Equivalent shortest rotation prevents exported curves jumping by 2*pi
        # when atan2 crosses its branch cut during inward knee flexion.
        knee_delta=theta2-rest2-parent_angle-a[hip]
        a[knee]=(knee_delta+math.pi)%(2*math.pi)-math.pi
        a[ankle]=-parent_angle-a[hip]-a[knee]

def pose(clip,t):
    c=CLIPS[clip];p={n:interpolate(v,t) for n,v in c['channels'].items()};a={n:0. for n in BONES};offsets={}
    breath=c.get('procedural',{}).get('breath',0)*math.sin(t*math.tau)
    sway=c.get('procedural',{}).get('sway',0)*math.sin(t*math.tau)
    body=math.radians(p.get('torso_rot',0)+.8*sway)
    a['spine']=body*.55;a['chest']=body*.45
    a['head']=math.radians(p.get('head_rot',0)+.5*breath)
    offsets['head']=np.array([p.get('head_x',0),p.get('head_y',0)])/.46
    air=np.array([p.get('air_x',0),p.get('air_y',0)])/.46
    offsets['root']=air+np.array([p.get('root_x',0)*.25,p.get('root_y',0)*.75])/.46
    offsets['spine']=np.array([p.get('root_x',0)*.75,-1.2*breath])/.46
    for side in ['near','far']:
        a['shoulder_'+side]=math.radians(p.get(side+'_shoulder',0)+(.5*breath if side=='near' else -.4*breath))
        a['elbow_'+side]=math.radians(p.get(side+'_elbow',0))
        a['wrist_'+side]=math.radians(p.get(side+'_wrist',0))
    # Shoulder stays attached to chest; action comes from joint rotation.
    a['shoulder_near']*=.55
    # Do not add shoulder rotation into elbow flexion: that doubled up the
    # block/cast/heavy windup and let positive release keys cross elbow lock.
    a['elbow_near']=math.radians(interpolate([[u,min(0.,v)] for u,v in c['channels'].get('near_elbow',[[0,0],[1,0]])],t))
    offsets['shoulder_near']=np.zeros(2)
    if clip in ['attack','domain_attack']:
        # Compact swipe with a bent recovery, not a 103-degree shoulder arc.
        a['shoulder_near']=math.radians(interpolate([[0,0],[.22,6],[.48,-48],[.62,-42],[.78,-18],[1,0]],t))
        a['elbow_near']=math.radians(interpolate([[0,0],[.22,-48],[.48,-26],[.62,-30],[.78,-20],[1,0]],t))
    if clip=='counter':
        # Remap key values before interpolation, so the release does not pass
        # through a straight elbow or acquire an abs() cusp mid-segment.
        a['elbow_near']=math.radians(interpolate([[u,-abs(v)] for u,v in c['channels']['near_elbow']],t))
    # Respect the actual rest geometry if the source-layer owner relocates the
    # elbow. Cap total flexion, not just the local animation offset.
    bend=rest_bend('near')
    a['elbow_near']=float(np.clip(a['elbow_near'],-math.radians(100)-bend,max(0.,-math.radians(8)-bend)))
    # The far arm is also nearly straight at rest. Positive elbow keys in
    # heavy/counter/leap formerly reversed its anatomical bend.
    a['elbow_far']=math.radians(interpolate([[u,min(0.,v)] for u,v in c['channels'].get('far_elbow',[[0,0],[1,0]])],t))
    for side in ['near','far']:
        for i in range(4):a[f'braid_{side}_{i}']=math.radians(1.2*math.sin(t*math.tau-i*.55)-p.get('torso_rot',0)*.15)
    # IK solves real hip/knee/ankle transforms, not display-only markers.
    solve_legs(a,offsets,p,air)
    return a,offsets,p

IMAGES={n:Image.open(ROOT/p['file']).convert('RGBA') for n,p in PARTS.items()}
HEAD_CELS=[Image.open(ROOT/f).convert('RGBA') for f in PARTS['head'].get('cels',['parts/head.png'])]
DEATH_ATLASES={n:Image.open(ROOT/'source'/f'{n}_authored_atlas.png').convert('RGBA') for n in ['die','domain_die']}
def build_mesh(name,p):
    x,y=p['origin'];w,h=p['size'];side=name.split('_')[-1]
    arm=name.startswith(('upper_arm_','forearm_','hand_'));leg=name.startswith(('thigh_','shin_','foot_'))
    if arm or leg:
        chain=[('shoulder_' if arm else 'hip_')+side,('elbow_' if arm else 'knee_')+side,('wrist_' if arm else 'ankle_')+side]
        first,middle,last=[np.array(BONES[n]['rest_world'],float) for n in chain]
        direction=(last-middle)/np.linalg.norm(last-middle)
        radius1=100 if arm else 85;radius2=55 if arm else 45
        step=28
        xs=np.arange(math.floor(x/step)*step,math.ceil((x+w)/step)*step+1,step)
        ys=np.arange(math.floor(y/step)*step,math.ceil((y+h)/step)*step+1,step)
        if leg:
            ys=np.unique(np.r_[ys,[v for v in (last[1]-100,last[1]-30) if ys[0]<v<ys[-1]]])
    else:
        chain=['chest','spine','pelvis'] if name=='torso' else [p['bone'][:-1]+str(i) for i in range(4)]
        centers=[BONES[n]['rest_world'][1] for n in chain]
        xs=np.linspace(x,x+w,7 if name=='torso' else 3);ys=np.linspace(y,y+h,15)
    vertices=[];uv=[];weights=[]
    def smooth(value):
        value=float(np.clip(value,0,1));return value*value*(3-2*value)
    for yy in ys:
        for xx in xs:
            v=np.array([xx,yy]);vertices.append(v);uv.append([xx-x,yy-y])
            if arm or leg:
                f=smooth((np.dot(v-middle,direction)+radius1)/(2*radius1))
                g=smooth((np.dot(v-last,direction)+radius2)/(2*radius2))
                ws={chain[0]:1-f,chain[1]:f*(1-g),chain[2]:f*g}
                if leg:
                    # Hip root shares pelvis motion, smoothly handing off to thigh.
                    axis=(middle-first)/np.linalg.norm(middle-first)
                    hip_mix=smooth((np.dot(v-first,axis)+35)/170)
                    # Horizontal ankle transition matches the source caps. A
                    # diagonal shin-axis projection lets wide toes inherit knee
                    # rotation even below the ankle. All overlapping leg layers
                    # use this same field, with a grid row at its rigid boundary.
                    g=smooth((v[1]-(last[1]-100))/70)
                    ws={chain[0]:(1-f)*(1-g)*hip_mix,
                        chain[1]:f*(1-g)*hip_mix,
                        chain[2]:g,'pelvis':(1-hip_mix)*(1-g)}
                    if name.startswith('foot_'):ws={chain[2]:1.}
            elif v[1]<=centers[0]:ws={chain[0]:1.}
            elif v[1]>=centers[-1]:ws={chain[-1]:1.}
            else:
                i=next(i for i in range(len(chain)-1) if centers[i]<=v[1]<=centers[i+1]);f=(v[1]-centers[i])/(centers[i+1]-centers[i]);ws={chain[i]:1-f,chain[i+1]:f}
            weights.append(ws)
    triangles=[];cols=len(xs)
    for row in range(len(ys)-1):
        for col in range(cols-1):
            i=row*cols+col;triangles.extend([(i,i+1,i+cols),(i+1,i+cols+1,i+cols)])
    return np.array(vertices),np.array(uv),weights,triangles
MESHES={n:build_mesh(n,p) for n,p in PARTS.items() if n not in ['head','back_spikes']}
def draw_mesh(canvas,src,definition,worlds,scale,origin):
    vertices,uv,weights,tris=definition;out=[]
    src=src.convert("RGBa")  # Premultiply once per part, not once per triangle.
    leg_side=next((side for side in ('near','far')
                   if any(definition is MESHES[name+'_'+side] for name in ('thigh','shin'))),None)
    for v,ws in zip(vertices,weights):
        if leg_side:
            p=sector_vertex(v,worlds,BONES,leg_side)
        else:
            p=np.zeros(2)
            for n,weight in ws.items():p+=weight*(worlds[n][0]+rot(worlds[n][1])@(v-np.array(BONES[n]['rest_world'])))
        out.append(p*scale+origin)
    out=np.array(out)
    for ids in tris:
        dst=out[list(ids)];tex=uv[list(ids)];lo=np.floor(dst.min(axis=0)).astype(int);hi=np.ceil(dst.max(axis=0)).astype(int)+1;size=hi-lo
        if min(size)<=0:continue
        coeff=np.linalg.solve(np.column_stack([dst,np.ones(3)]),tex);off=np.array([lo[0],lo[1],1])@coeff
        crop=src.transform(tuple(size),Image.Transform.AFFINE,(coeff[0,0],coeff[1,0],off[0],coeff[0,1],coeff[1,1],off[1]),Image.Resampling.BICUBIC)
        crop=crop.convert("RGBA")
        mask=Image.new('L',tuple(size));ImageDraw.Draw(mask).polygon([tuple(v-lo) for v in dst],fill=255)
        crop.putalpha(Image.fromarray(np.minimum(np.asarray(crop.getchannel('A')),np.asarray(mask))))
        canvas.alpha_composite(crop,tuple(lo))
def render(clip,t,size=512,debug=False,neutral=False):
    if clip in DEATH_ATLASES and not neutral:
        i=min(39,int(t*40+1e-8));x=i%8*512;y=i//8*512
        return DEATH_ATLASES[clip].crop((x,y,x+512,y+512)).resize((size,size),Image.Resampling.LANCZOS)
    scale=.46*size/768;origin=np.array([70,111])*size/768
    a,off,p=pose(clip,t)
    if neutral:a={n:0. for n in BONES};off={}
    worlds=world(a,off);im=Image.new('RGBA',(size,size))
    for name,part in sorted(PARTS.items(),key=lambda item:item[1]['z']):
        src=IMAGES[name]
        if name=='head':
            mouth=p.get('roar',0);src=HEAD_CELS[0 if mouth<.12 else 1 if mouth<.85 else 2]
        if name in MESHES:draw_mesh(im,src,MESHES[name],worlds,scale,origin);continue
        bone=part['bone'];point,angle=worlds[bone];inv=rot(-angle)/scale
        offset=np.array(BONES[bone]['rest_world'])-np.array(part['origin'])-inv@(point*scale+origin)
        layer=src.transform((size,size),Image.Transform.AFFINE,(inv[0,0],inv[0,1],offset[0],inv[1,0],inv[1,1],offset[1]),Image.Resampling.BICUBIC)
        im.alpha_composite(layer)
    if debug:
        d=ImageDraw.Draw(im)
        for n,(pt,angle) in worlds.items():
            pt=pt*scale+origin;parent=BONES[n]['parent']
            if parent:d.line([tuple(worlds[parent][0]*scale+origin),tuple(pt)],fill=(35,230,205,255),width=2)
            d.ellipse((pt[0]-2,pt[1]-2,pt[0]+2,pt[1]+2),fill=(255,202,70,255))
    return im
def panel(im,label):
    bg=Image.new('RGB',im.size,(26,38,52));bg.paste(im,(0,0),im);ImageDraw.Draw(bg).text((12,12),label,fill=(223,237,244));return bg
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--extremes',action='store_true');args=ap.parse_args()
    if args.extremes:
        checks=[('idle_loop',0),('attack',.5),('block',.5),('counter',.4),('counter',.63),('storm_leap',.15),('storm_leap',.48),('roar',.5)]
        for name,t in checks:
            im=render(name,t,768,neutral=name=='idle_loop');save(ROOT/'review'/f'{name}_{t:.2f}.png',panel(im,name+f' {t:.2f}'))
        save(ROOT/'review/skeleton_neutral.png',panel(render('idle_loop',0,768,True,True),'V9 bone placement / reference coordinates'))
    js(ROOT/'meshes.json',{n:{'vertices':v.tolist(),'uv':uv.tolist(),'weights':ws,'triangles':tri} for n,(v,uv,ws,tri) in MESHES.items()})
