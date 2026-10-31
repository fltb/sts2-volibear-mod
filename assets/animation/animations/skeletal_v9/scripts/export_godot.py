"""Native Godot source from the exact V9 rig; requires target-engine validation."""
import json, math
import numpy as np
from PIL import Image
import render as r
ROOT=r.ROOT

def packed(kind,values):return kind+'('+', '.join(format(float(v),'.9g') for v in np.array(values).ravel())+')'
def bonepath(n):return (bonepath(r.BONES[n]['parent'])+'/' if r.BONES[n]['parent'] else '')+n

def main():
    manifest=json.loads((ROOT/'manifest.json').read_text());clips=manifest['clips']+manifest['variants']
    ext=[];resources=[];nodes=[]
    def padded(file):
        im=Image.open(ROOT/file).convert('RGBA');out=Image.new('RGBA',(im.width+64,im.height+64));out.alpha_composite(im,(32,32));dest='godot_parts/'+file.split('/')[-1];r.save(ROOT/dest,out);return dest
    for n,p in r.PARTS.items():ext.append(f'[ext_resource type="Texture2D" path="res://{padded(p["file"])}" id="tex_{n}"]')
    for i,f in enumerate(r.PARTS['head']['cels'][1:],1):ext.append(f'[ext_resource type="Texture2D" path="res://{padded(f)}" id="head_{i}"]')
    for c in clips:
        if c['technique']=='authored_death_cels':ext.append(f'[ext_resource type="Texture2D" path="res://{c["atlas"]["image"]}" id="atlas_{c["name"]}"]')
    for c in clips:
        name=c['name'];data=json.loads((ROOT/'frames'/name/'skeleton_samples.json').read_text());rows=data['samples'];times=[x['time'] for x in rows]
        lines=[f'[sub_resource type="Animation" id="anim_{name}"]',f'resource_name = "{name}"',f'length = {c["duration"]}',f'loop_mode = {int(c["loop"])}'];track=0
        def add(path,values,discrete=False,at=None):
            nonlocal track
            ts=times if at is None else at
            lines.extend([f'tracks/{track}/type = "value"',f'tracks/{track}/path = NodePath("{path}")',f'tracks/{track}/interp = 1',f'tracks/{track}/keys = {{"times": {packed("PackedFloat32Array",ts)}, "transitions": {packed("PackedFloat32Array",np.ones(len(ts)))}, "update": {1 if discrete else 0}, "values": [{", ".join(values)}]}}']);track+=1
        death=c['technique']=='authored_death_cels'
        add('Visuals:visible',['false' if death else 'true'],True,[0]);add('Death:visible',['true' if death else 'false'],True,[0])
        if death:
            add('Death:texture',[f'ExtResource("atlas_{name}")'],True,[0])
            add('Death:frame',[str(min(c['frame_count']-1,i)) for i in range(len(rows))],True)
        else:
            for n,b in r.BONES.items():
                add(f'Visuals/Skeleton2D/{bonepath(n)}:rotation',[str(row['rotations'][n]) for row in rows])
                add(f'Visuals/Skeleton2D/{bonepath(n)}:position',[packed('Vector2',np.array(b['local'])+np.array(row['offsets'].get(n,[0,0]))) for row in rows])
            # Nonlinear sector skinning cannot be represented by Bone2D weights.
            # Bake mesh vertex tracks from the same field, not painted frames.
            from leg_deformation import sector_vertex
            worlds=[r.world(row['rotations'],{n:np.array(v) for n,v in row['offsets'].items()}) for row in rows]
            for side in ('near','far'):
                for part in ('thigh','shin'):
                    mesh_name=part+'_'+side
                    vertices=r.MESHES[mesh_name][0]
                    add(f'Visuals/{mesh_name}:polygon',[
                        packed('PackedVector2Array',[sector_vertex(v,w,r.BONES,side) for v in vertices])
                        for w in worlds])
            add('Visuals/head:texture',[f'ExtResource("{("head_"+str(row["mouth_cel"])) if row["mouth_cel"] else "tex_head"}")' for row in rows],True)
        resources.append('\n'.join(lines))
    resources.append('[sub_resource type="AnimationLibrary" id="library"]\n_data = {'+', '.join(f'&"{c["name"]}": SubResource("anim_{c["name"]}")' for c in clips)+'}')
    nodes=['[node name="VolibearV9" type="Node2D"]','[node name="Visuals" type="Node2D" parent="."]\nposition = Vector2(46.6666667, 74)\nscale = Vector2(0.306666667, 0.306666667)','[node name="Skeleton2D" type="Skeleton2D" parent="Visuals"]']
    for n,b in r.BONES.items():
        parent='Visuals/Skeleton2D'+('/'+bonepath(b['parent']) if b['parent'] else '');x,y=b['local']
        nodes.append(f'[node name="{n}" type="Bone2D" parent="{parent}"]\nposition = Vector2({x}, {y})\nrest = Transform2D(1, 0, 0, 1, {x}, {y})\nautocalculate_length_and_angle = false\nlength = 30.0')
    for n,p in sorted(r.PARTS.items(),key=lambda item:item[1]['z']):
        if n in r.MESHES:v,uv,weights,tris=r.MESHES[n]
        else:
            w,h=p['size'];uv=np.array([[0,0],[w,0],[w,h],[0,h]]);v=uv+np.array(p['origin']);weights=[{p['bone']:1.} for _ in uv];tris=[(0,1,2),(0,2,3)]
        uv=np.array(uv)+32
        lines=[f'[node name="{n}" type="Polygon2D" parent="Visuals"]',f'z_index = {round(p["z"]*2)}',f'texture = ExtResource("tex_{n}")','skeleton = NodePath("../Skeleton2D")',f'polygon = {packed("PackedVector2Array",v)}',f'uv = {packed("PackedVector2Array",uv)}','polygons = ['+', '.join('PackedInt32Array('+', '.join(str(i) for i in tri)+')' for tri in tris)+']']
        if n in ('thigh_near','shin_near','thigh_far','shin_far'):
            # Vertex tracks already contain posed world-space geometry.
            weights=[{} for _ in v]
        for i,b in enumerate(n for n in r.BONES if any(n in ws for ws in weights)):
            lines += [f'bones/{i}/bone = NodePath("{bonepath(b)}")',f'bones/{i}/weights = {packed("PackedFloat32Array",[ws.get(b,0) for ws in weights])}']
        nodes.append('\n'.join(lines))
    nodes+=['[node name="Death" type="Sprite2D" parent="."]\nvisible = false\nposition = Vector2(256,256)\nhframes = 8\nvframes = 5','[node name="AnimationPlayer" type="AnimationPlayer" parent="."]\nlibraries = {&"": SubResource("library")}\nautoplay = "idle_loop"']
    for name,pos in [('IntentPos',(250,70)),('CenterPos',(250,280)),('TalkPos',(360,190))]:nodes.append(f'[node name="{name}" type="Marker2D" parent="."]\nunique_name_in_owner = true\nposition = {packed("Vector2",pos)}')
    nodes.append('[node name="Bounds" type="Control" parent="."]\nunique_name_in_owner = true\noffset_left = 65.0\noffset_top = 75.0\noffset_right = 495.0\noffset_bottom = 445.0\nmouse_filter = 2')
    r.atomic(ROOT/'character.tscn',('\n\n'.join(['[gd_scene load_steps='+str(len(ext)+len(resources)+1)+' format=3]']+ext+resources+nodes)+'\n').encode())
    r.atomic(ROOT/'project.godot',b'config_version=5\n\n[application]\nconfig/name="Volibear V9 candidate"\nrun/main_scene="res://character.tscn"\n\n[display]\nwindow/size/viewport_width=512\nwindow/size/viewport_height=512\n\n[rendering]\nrenderer/rendering_method="gl_compatibility"\nenvironment/defaults/default_clear_color=Color(0.102,0.149,0.204,1)\n')
    r.js(ROOT/'godot_export_status.json',{'status':'source_exported_engine_unvalidated','integration_status':'integration_source_uncompiled','sequences':len(clips),'bones':len(r.BONES),'render_input_sha256':manifest['render_input_sha256'],'events':'Timing remains in atlas JSON. Host dispatches committed events; scene does not run gameplay or effects.'})
    print('Exported native Godot source:',len(clips),'sequences')
if __name__=='__main__':main()
