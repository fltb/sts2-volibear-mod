#!/usr/bin/env python3
"""Rebuild and verify reviewed Volibear card assets. Never approves artwork."""
from __future__ import annotations
import argparse, hashlib, json, tempfile, os
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageOps, ImageDraw, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
RARITY = {'basic':'基础','common':'普通','uncommon':'罕见','rare':'稀有','token':'衍生'}
GATES = ['limb_connections','joints_and_paws','head_and_torso','occlusion',
         'action_causality','thumbnail_readability','series_identity','crop_and_mask']

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def objsha(x): return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p, data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    if not isinstance(data,bytes): data=data.encode('utf-8')
    fd,tmp=tempfile.mkstemp(prefix='.'+p.name+'.',dir=p.parent)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def savejson(p,x):save(p,json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def png(p,im):
    import io
    b=io.BytesIO();meta=PngImagePlugin.PngInfo();meta.add(b'sRGB',b'\0')
    im.save(b,format='PNG',pnginfo=meta,icc_profile=None);save(p,b.getvalue())
def inside(root,rel):
    p=(root/rel).resolve()
    if not p.is_relative_to(root):raise ValueError('Escaped repository: '+rel)
    return p
def need(ok,message):
    if not ok:raise ValueError(message)
def filerec(root,rel):
    p=inside(root,rel);r={'path':rel,'href':'../'+rel,'sha256':sha(p)}
    if p.suffix.lower()=='.png':
        with Image.open(p) as im:r['size']=list(im.size)
    return r

def load(root):
    source=read(root/'data/cards_source.json');manifest=read(root/'data/asset_manifest.json')
    config=read(root/'config/export_profiles.json')
    need(manifest['export_config_sha256']==sha(root/'config/export_profiles.json'),'Export configuration changed: crop/mask review required')
    masks={v for p in config['profiles'] for v in p.get('mask_by_type',{}).values()}
    need(set(manifest['mask_sha256s'])==masks,'Mask inventory changed: review required')
    for rel in masks:need(sha(inside(root,rel))==manifest['mask_sha256s'][rel],'Mask changed: '+rel)
    cards=source['cards'];ids=[c['id'] for c in cards]
    need(len(ids)==len(set(ids))==source['card_count'],'Source ID/count mismatch')
    need(len({c['asset_key'] for c in cards})==len(ids),'Duplicate asset keys')
    need(manifest['source_sha256']==sha(root/'data/cards_source.json'),'Source changed: explicit review required')
    assets=manifest['cards'];need(set(assets)==set(ids),'Source and manifest IDs differ')
    locked=read(root/'data/v7/user_locked_cards.json')['cards']
    for item in locked:
        need(sha(root/f"cards/masters/{item['id']}.png")==item['sha256'],item['id']+': user-locked original changed')
        for e in item.get('locked_exports',[]):
            need(sha(root/e['path'])==e['sha256'],item['id']+': user-locked export changed')
    for c in cards:
        a=assets[c['id']];master=inside(root,a['master'])
        need(sha(master)==a['master_sha256'],c['id']+': master changed after review')
        need(a['source_record_sha256']==objsha(c),c['id']+': source semantics changed')
        rp=inside(root,a['review']);need(sha(rp)==a['review_sha256'],c['id']+': review record changed')
        r=read(rp)
        need(r['id']==c['id'] and r['decision']=='approve',c['id']+': missing approval')
        need(r['master_sha256']==a['master_sha256'],c['id']+': approval bound to another image')
        need(r['inspected_actual_images'] is True,c['id']+': actual image inspection required')
        need(r['reviewer']['independent_from_generator'] is True,c['id']+': independent review required')
        need(all(r['gates'].get(k) is True for k in GATES),c['id']+': anatomy/action/crop gate failed')
        if a.get('revision') in {'revised_v4', 'revised_v7'}:
            need(r['gates'].get('paw_orientation') is True,c['id']+': palm/knuckle/claw orientation review required')
            need(bool(r.get('paw_orientation_observation')),c['id']+': missing actual orientation observation')
        need(not r.get('unresolved_defects'),c['id']+': unresolved visual defect')
        need(sha(inside(root,a['prompt']))==a['prompt_sha256'],c['id']+': prompt changed')
        with Image.open(master) as im:
            im.load();need(im.width>=1000 and im.height>=760,c['id']+': source too small')
            need(abs(im.width/im.height/(25/19)-1)<.001,c['id']+': unreviewed aspect crop')
            need('A' not in im.getbands() or im.getchannel('A').getextrema()==(255,255),c['id']+': unexpected alpha')
            prov=a.get('provenance',{})
            if prov.get('raw_path'):
                raw=inside(root,prov['raw_path']);need(sha(raw)==prov['selected_source_sha256'],c['id']+': raw generation source changed')
                original=Image.open(raw).convert('RGB');expected=original.crop(tuple(prov['crop_box']))
                need(expected.size==im.size and expected.tobytes()==im.convert('RGB').tobytes(),c['id']+': master differs from recorded crop')
    return cards,manifest,config

def render(root,card,im,profile):
    out=ImageOps.fit(im.convert('RGB'),tuple(profile['size']),method=Image.Resampling.LANCZOS)
    if profile.get('mask_by_type'):
        mask=Image.open(inside(root,profile['mask_by_type'][card['type']])).convert('L')
        need(mask.size==out.size,'Wrong mask size')
        out.putalpha(mask.point(lambda p:255 if p>0 else 0))
    return out

def rebuild(root):
    cards,m,cfg=load(root)
    locked={c['id'] for c in read(root/'data/v7/user_locked_cards.json')['cards']}
    for card in cards:
        if card['id'] in locked:continue
        a=m['cards'][card['id']];im=Image.open(inside(root,a['master'])).convert('RGB');a['exports']=[]
        for p in cfg['profiles']:
            rel=p['path'].format(asset_key=card['asset_key'])
            out=render(root,card,im,p);png(root/rel,out)
            a['exports'].append({'profile':p['name'],'path':rel,'sha256':sha(root/rel),
                                 'size':list(out.size),'mode':out.mode,'master_sha256':a['master_sha256']})
    savejson(root/'data/asset_manifest.json',m)
    gallery(root,cards,m)
    return verify(root)

def proof(root,card,a):
    by={x['profile']:x for x in a['exports']}
    large=Image.open(root/by['sts2_big']['path']).convert('RGB')
    board=Image.new('RGB',(1120,845),'#202b36');d=ImageDraw.Draw(board)
    version='V7' if a.get('revision') == 'revised_v7' else 'USER LOCKED'
    d.text((18,10),card['id']+' / reviewed '+version+' master / 250 / 125 / gray / STS1 mask',fill='white')
    board.paste(large.resize((700,532),Image.Resampling.LANCZOS),(18,38))
    small=Image.open(root/by['sts2_small']['path']).convert('RGB');board.paste(small,(750,38))
    tiny=small.resize((125,95),Image.Resampling.LANCZOS);board.paste(tiny,(750,250))
    board.paste(ImageOps.grayscale(tiny).convert('RGB'),(895,250))
    for key,xy in [('sts1_large',(18,590)),('sts1_small',(550,615))]:
        im=Image.open(root/by[key]['path']).convert('RGBA')
        if key=='sts1_large':im.thumbnail((330,251),Image.Resampling.LANCZOS)
        bg=Image.new('RGB',im.size,'#76818a');dr=ImageDraw.Draw(bg)
        for y in range(0,im.height,16):
            for x in range(0,im.width,16):
                if (x//16+y//16)%2:dr.rectangle((x,y,x+15,y+15),fill='#48535d')
        bg.paste(im,mask=im.getchannel('A'));board.paste(bg,xy)
    path=root/f'cards/proofs/{card["id"]}.jpg';path.parent.mkdir(parents=True,exist_ok=True)
    board.save(path,quality=94)

def gallery(root,cards,m):
    briefs={c['id']:c for c in read(root/'data/cards_art_briefs.json')['cards']};records=[]
    locked={c['id'] for c in read(root/'data/v7/user_locked_cards.json')['cards']}
    ranking_path=root/'reports/revision_v7/quality_ranking.json'
    ranking={c['id']:c for c in read(ranking_path)['cards']} if ranking_path.exists() else {}
    for order,c in enumerate(cards):
        a=m['cards'][c['id']];art=briefs[c['id']].get('art',{});exports={x['profile']:filerec(root,x['path']) for x in a['exports']}
        review=read(root/a['review']);quality=review.get('quality_axes',{})
        sm=Image.open(root/exports['sts2_small']['path']).convert('RGB')
        for label in ['tiny','gray']:
            im=sm.resize((125,95),Image.Resampling.LANCZOS)
            if label=='gray':im=ImageOps.grayscale(im).convert('RGB')
            png(root/f'cards/gallery_previews/{label}/{c["asset_key"]}.png',im)
        proof(root,c,a)
        records.append(dict(c,order=order,rarity_label=RARITY[c['rarity']],
            abstraction=art.get('abstraction_level','M0'),representation=art.get('representation_mode',''),
            intent=art.get('composition',''),signature=art.get('signature',''),verb=art.get('primary_verb',''),
            camera=art.get('camera',''),silhouette=art.get('silhouette',''),negative_space=art.get('negative_space',''),
            identity_anchors=art.get('identity_anchors',[]),palette=art.get('suggested_palette',{}).get('colors',[]),
            state_status='exported',approval_valid=True,production=True,
            display_status='固定保留' if c['id'] in locked else 'V7 重绘',
            revision=7 if a.get('revision') == 'revised_v7' else 2,
            user_locked=c['id'] in locked,score=sum(quality.values()) if quality else None,
            quality_axes=quality,quality_rank=ranking.get(c['id'],{}).get('rank'),
            benchmark_comparison=review.get('baseline_comparison','用户指定固定保留，母图及四套导出保持原字节。'),
            actual_observation=review.get('observations',''),
            comparison=filerec(root,review['comparison_file']) if review.get('comparison_file') else None,
            candidate=filerec(root,a['master']),large=exports['sts2_big'],small=exports['sts2_small'],
            tiny=filerec(root,f'cards/gallery_previews/tiny/{c["asset_key"]}.png'),
            gray=filerec(root,f'cards/gallery_previews/gray/{c["asset_key"]}.png'),
            proof=filerec(root,f'cards/proofs/{c["id"]}.jpg'),review=filerec(root,a['review']),exports=exports))
    data={'schema_version':7,'delivery_version':'V7','generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'source_version':read(root/'data/cards_source.json').get('source_version'),
          'stats':{'total':len(cards),'approved':len(cards),'production':len(cards),'available':len(cards),
                   'locked':len(locked),'redrawn':len(cards)-len(locked),
                   'by_type':dict(Counter(c['type'] for c in cards))},'cards':records,'all_production':True,'warnings':[]}
    savejson(root/'cards/gallery_manifest.json',data)
    save(root/'cards/gallery_data.js','window.VOLIBEAR_CARD_GALLERY = '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n')

def verify(root):
    cards,m,cfg=load(root);profiles={p['name']:p for p in cfg['profiles']};seen=set();pixels=set();report=[]
    for c in cards:
        a=m['cards'][c['id']];im=Image.open(root/a['master']).convert('RGB')
        pix=hashlib.sha256(im.tobytes()).hexdigest();need(pix not in pixels,c['id']+': duplicate artwork');pixels.add(pix)
        need(len(a['exports'])==4 and {e['profile'] for e in a['exports']}==set(profiles),c['id']+': missing export profile')
        for e in a['exports']:
            p=profiles[e['profile']];rel=p['path'].format(asset_key=c['asset_key'])
            need(e['path']==rel and rel not in seen,c['id']+': export path mismatch');seen.add(rel)
            need(e['master_sha256']==a['master_sha256'],c['id']+': stale export')
            need(sha(root/rel)==e['sha256'],rel+': SHA256 mismatch')
            expected=render(root,c,im,p)
            with Image.open(root/rel) as actual:
                need(actual.size==expected.size and actual.mode==expected.mode,rel+': format/size mismatch')
                need(actual.tobytes()==expected.tobytes(),rel+': pixels differ from approved source and mask')
        report.append({'id':c['id'],'master_sha256':a['master_sha256'],'anatomy_review_bound':True,'exports':4})
    actual={p.relative_to(root).as_posix() for p in (root/'production').rglob('*.png')}
    need(actual==seen,'Unexpected or missing production PNGs')
    data=read(root/'cards/gallery_manifest.json');need([c['id'] for c in data['cards']]==[c['id'] for c in cards],'Gallery/source order differs')
    js=(root/'cards/gallery_data.js').read_text();need(json.loads(js.removeprefix('window.VOLIBEAR_CARD_GALLERY = ').rstrip(';\n'))==data,'Gallery JS/JSON mismatch')
    for c in data['cards']:
        for name in ['candidate','large','small','tiny','gray','proof','review']+(['comparison'] if c.get('comparison') else []):
            r=c[name];need(sha(root/r['path'])==r['sha256'],c['id']+': stale gallery '+name)
        source=next(x for x in cards if x['id']==c['id'])
        need(all(c[k]==source[k] for k in source),c['id']+': gallery changed original game text')
        expected_exports={e['profile']:e for e in m['cards'][c['id']]['exports']}
        need(set(c['exports'])==set(expected_exports),c['id']+': gallery export profiles differ')
        for name,e in expected_exports.items():
            r=c['exports'][name]
            need(r['path']==e['path'] and r['sha256']==e['sha256'] and r['href']=='../'+e['path'],c['id']+': gallery export binding differs: '+name)
            need(sha(root/r['path'])==r['sha256'],c['id']+': stale gallery export: '+name)
    result={'passed':True,'card_count':len(cards),'export_count':len(seen),'unique_artwork':len(pixels),
            'source_sha256':sha(root/'data/cards_source.json'),'manifest_sha256':sha(root/'data/asset_manifest.json'),
            'checks':['source IDs and original rule text','current-image independent approval, eight anatomy/action gates and V7 claw orientation',
                      '89 unique decoded artwork images','356 exact export pixels, masks, dimensions and SHA256 bindings',
                      'all gallery files and original card text'],
            'scope':'Technical validation binds actual visual reviews. It does not automatically judge anatomy or claim in-game execution.',
            'cards':report}
    savejson(root/'reports/technical_validation.json',result);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['verify','rebuild','gallery']);p.add_argument('--root',type=Path,default=ROOT)
    args=p.parse_args();root=args.root.resolve()
    if args.command=='gallery':
        cards,m,_=load(root);gallery(root,cards,m);r=verify(root)
    else:r=rebuild(root) if args.command=='rebuild' else verify(root)
    print(json.dumps({k:r[k] for k in ['passed','card_count','export_count','unique_artwork']},ensure_ascii=False))
if __name__=='__main__':main()
