#!/usr/bin/env python3
"""Apply an explicit independent visual decision; never infer aesthetic approval."""
from pathlib import Path
import argparse, hashlib, json, shutil, sys
from datetime import datetime, timezone
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import card_repo as cr

def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x): cr.savejson(p,x)

def generation_history(obj):
    if isinstance(obj,dict):
        if 'attempt' in obj and (obj.get('output_sha256') or obj.get('raw_output_sha256')):
            yield obj
        for key in ('attempts','prior_attempts','attempt_history','subsequent_attempts'):
            if key in obj:yield from generation_history(obj[key])
    elif isinstance(obj,list):
        for item in obj:yield from generation_history(item)

def refresh():
    state=read(ROOT/'data/v7/state.json')
    assets=read(ROOT/'data/asset_manifest.json')['cards']
    for id,s in state['cards'].items():
        attempts_by_number={}
        gp=ROOT/f'reviews/v7/generation_{id}.json'
        if gp.exists():
            g=read(gp)
            for rec in generation_history(g):
                n=int(str(rec['attempt']).replace('attempt',''))
                attempts_by_number[n]={'attempt':n,'sha256':rec.get('output_sha256') or rec.get('raw_output_sha256'),
                    'source_artifact_state':'historical_generation_record'}
        for p in sorted((ROOT/f'cards/candidates_v7/{id}').glob('attempt*.png')):
            n=int(p.stem.replace('attempt',''))
            attempts_by_number[n]={'attempt':n,'raw_path':str(p.relative_to(ROOT)),'sha256':sha(p),'source_artifact_state':'candidate_present'}
        a=assets[id]
        if a.get('revision')=='revised_v7':
            prov=a['provenance'];selected=prov['attempt']
            attempts_by_number.setdefault(selected,{'attempt':selected}).update(raw_path=prov['raw_path'],sha256=prov['selected_source_sha256'],source_artifact_state='delivered_selected_raw')
        attempts=[]
        for n,rec in sorted(attempts_by_number.items()):
            d=ROOT/f'reviews/v7/decisions/{id}_attempt{n:02d}.json'
            rec['status']=read(d)['decision'] if d.exists() else ('superseded_by_later_attempt' if n<max(attempts_by_number) else 'awaiting_independent_review')
            if d.exists():rec['decision_file']=str(d.relative_to(ROOT))
            attempts.append(rec)
        s['attempts']=attempts
        if a.get('revision')=='revised_v7':
            selected=a['provenance']['attempt']
            decision_path=ROOT/f'reviews/v7/decisions/{id}_attempt{selected:02d}.json'
            current_decision=read(decision_path)['decision'] if decision_path.exists() else None
            s.update(status='approved_exported' if current_decision=='approve' and selected==max(attempts_by_number) else 'needs_redraw',selected_attempt=selected,master_sha256=a['master_sha256'])
        elif attempts:s['status']='needs_redraw' if attempts[-1]['status']=='reject' else 'awaiting_independent_review'
    state['generated']=sum(bool(s['attempts']) for s in state['cards'].values())
    state['visually_approved']=sum(s['status']=='approved_exported' for s in state['cards'].values())
    state['remaining']=state['to_redraw']-state['visually_approved']
    state['status']='complete' if state['remaining']==0 else 'generating'
    state['updated_at']=datetime.now(timezone.utc).isoformat(timespec='seconds')
    save(ROOT/'data/v7/state.json',state)
    return {k:v for k,v in state.items() if k!='cards'}

def apply(d):
    id=d['id'];attempt=d['attempt'];stagepath=ROOT/f'cards/candidates_v7/{id}/stage{attempt:02d}/stage.json'
    raw=ROOT/f'cards/candidates_v7/{id}/attempt{attempt:02d}.png'
    if not raw.exists() and stagepath.exists():raw=ROOT/read(stagepath)['raw_file']
    assert sha(raw)==d['raw_sha256'],f'{id}: decision is for a different raw image'
    assert d['reviewer']=='root_independent_visual_review' and d['inspected_actual_images'] is True
    assert d['observations'],f'{id}: actual observations required'
    locked=read(ROOT/'data/v7/user_locked_cards.json')['cards']
    assert id not in {x['id'] for x in locked},'Cannot replace a user-locked card'
    for x in locked:assert sha(ROOT/f"cards/masters/{x['id']}.png")==x['sha256']
    dest=ROOT/f'reviews/v7/decisions/{id}_attempt{attempt:02d}.json'
    d['recorded_at']=datetime.now(timezone.utc).isoformat(timespec='seconds')
    if d['decision']=='reject':
        assert d['defects'];save(dest,d);return
    assert d['decision']=='approve' and not d.get('defects')
    st=read(stagepath)
    assert st['master_sha256']==d['master_sha256'] and sha(ROOT/st['master_file'])==d['master_sha256']
    assert st['comparison_sha256']==d['comparison_sha256'] and sha(ROOT/st['comparison_file'])==d['comparison_sha256']
    assert set(d['views_inspected'])=={'raw_full','comparison_anchors','250','125','grayscale','sts1_masks'}
    assert all(d['gates'].get(k) is True for k in cr.GATES+['paw_orientation'])
    assert len(d['quality_axes'])==5 and all(0<=v<=20 for v in d['quality_axes'].values())
    g=read(ROOT/f'reviews/v7/generation_{id}.json')
    matches=[rec for rec in generation_history(g)
             if int(str(rec['attempt']).replace('attempt',''))==attempt
             and (rec.get('output_sha256') or rec.get('raw_output_sha256'))==st['raw_sha256']]
    assert matches,f'{id}: selected attempt and raw SHA missing from generation history'
    g=matches[0]
    prompt=g.get('original_request_prompt') or g.get('prompt') or g.get('actual_prompt') or g.get('request',{}).get('prompt')
    assert prompt and len(prompt)>100
    rawrel=f'cards/source_v7/{id}.png';(ROOT/rawrel).parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(raw,ROOT/rawrel)
    shutil.copyfile(ROOT/st['master_file'],ROOT/f'cards/masters/{id}.png')
    cr.save(ROOT/f'cards/prompts/{id}.txt',prompt+'\n')
    comparisonrel=f'reviews/v7/comparisons/{id}.jpg';(ROOT/comparisonrel).parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/st['comparison_file'],ROOT/comparisonrel)
    review=dict(d,master=f'cards/masters/{id}.png',revision='V7',unresolved_defects=[],
                reviewer={'name':d.get('actual_reviewer','root'),'role':'independent visual reviewer','independent_from_generator':True},
                comparison_file=comparisonrel,anchors=st['anchors'],scope='Visual judgment from actual images, not a guarantee of user preference.')
    save(ROOT/f'reviews/{id}.json',review);save(dest,d)
    manifest=read(ROOT/'data/asset_manifest.json');a=manifest['cards'][id]
    a.update(revision='revised_v7',master_sha256=sha(ROOT/f'cards/masters/{id}.png'),
             review=f'reviews/{id}.json',review_sha256=sha(ROOT/f'reviews/{id}.json'),
             prompt=f'cards/prompts/{id}.txt',prompt_sha256=sha(ROOT/f'cards/prompts/{id}.txt'))
    a['provenance']={'provider':g.get('actual_provider',g.get('provider',g.get('runtime_default_at_call',{}).get('provider','builtin image_gen.imagegen'))),'raw_path':rawrel,
        'selected_source_sha256':st['raw_sha256'],'selected_source_size':st['raw_size'],
        'crop_box':st['crop_box'],'resized_for_master':False,'attempt':attempt,
        'crop_area_removed_fraction':1-st['master_size'][0]*st['master_size'][1]/(st['raw_size'][0]*st['raw_size'][1]),
        'generation_record':f'reviews/v7/generation_{id}.json'}
    card=next(c for c in read(ROOT/'data/cards_source.json')['cards'] if c['id']==id)
    a['exports']=[];im=Image.open(ROOT/a['master'])
    for p in read(ROOT/'config/export_profiles.json')['profiles']:
        rel=p['path'].format(asset_key=card['asset_key']);out=cr.render(ROOT,card,im,p);cr.png(ROOT/rel,out)
        a['exports'].append({'profile':p['name'],'path':rel,'sha256':sha(ROOT/rel),'size':list(out.size),'mode':out.mode,'master_sha256':a['master_sha256']})
    manifest['status']='v7_generation_in_progress';save(ROOT/'data/asset_manifest.json',manifest)
    briefs=read(ROOT/'data/cards_art_briefs.json');b=next(c for c in briefs['cards'] if c['id']==id)
    plan=next(c for c in read(ROOT/'data/v7/redesign_plan.json')['cards'] if c['id']==id)
    b['art'].update(abstraction_level=plan['level'],representation_mode=plan['family'],visual_family=plan['family'],
       primary_verb=plan['verb'],camera=plan['camera'],silhouette=plan['shape'],composition=plan['scene'],
       signature=plan['semantic'],fail_if=plan['avoid'],revision='V7',actual_observation=d['observations'])
    b['prompt']=prompt;b['prompt_zh']=prompt;b['reference_ids']=plan['anchors']
    save(ROOT/'data/cards_art_briefs.json',briefs)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('decisions',nargs='?',type=Path);a=p.parse_args()
    if a.decisions:
        for d in read(a.decisions):apply(d)
    print(json.dumps(refresh(),ensure_ascii=False))
