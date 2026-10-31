#!/usr/bin/env python3
"""Finalize metadata for already reviewed art. Does not generate images or grant approval."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import csv, hashlib, json, shutil, sys
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'scripts'))
import card_repo as cr

def read(p):return json.loads((R/p).read_text())
def save(p,x):cr.savejson(R/p,x)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=datetime.now(timezone.utc).isoformat(timespec='seconds')
source=read('data/cards_source.json'); m=read('data/asset_manifest.json'); lock=read('data/v7/user_locked_cards.json'); plan=read('data/v7/redesign_plan.json'); state=read('data/v7/state.json')
assert sha(R/'data/cards_source.json')=='e74335e588b5b0b7be8a1f1ec08dff94091c1af158efa718e1cedbfff115c17c'
assert state['visually_approved']==61 and state['remaining']==0
ids=[c['id'] for c in source['cards']];locked={c['id'] for c in lock['cards']};redrawn=[i for i in ids if i not in locked]
assert len(locked)==28 and len(redrawn)==61 and 'U28' in redrawn and 'U35' in locked
old_root=R.parents[1]/'revision_v5/volibear_cards_repo'
old= json.loads((old_root/'data/asset_manifest.json').read_text()) if old_root.exists() else None
preserved=[]
for c in lock['cards']:
    cid=c['id'];a=m['cards'][cid]
    assert sha(R/a['master'])==c['sha256']
    c.setdefault('original_source_audit_path',c['source_file'])
    c['source_file']=a['master'];c['reference_file']=a['master'];c['locked_exports']=a['exports']
    if old:
        assert a['master_sha256']==old['cards'][cid]['master_sha256']
        assert a['exports']==old['cards'][cid]['exports']
        assert (R/a['master']).read_bytes()==(old_root/a['master']).read_bytes()
        for e in a['exports']:assert (R/e['path']).read_bytes()==(old_root/e['path']).read_bytes()
    preserved.append({'id':cid,'master_sha256':c['sha256'],'export_sha256s':{e['profile']:e['sha256'] for e in a['exports']},'master_and_four_exports_unchanged':True})
lock.update(revision='V7_completed',updated_at=now)
save('data/v7/user_locked_cards.json',lock)
save('reports/revision_v7/locked_preservation.json',{'checked_at':now,'comparison':'V5 delivered card repository, actual byte comparison' if old else 'previously verified locked manifest','locked_cards':28,'unchanged_masters':28,'unchanged_exports':112,'source_rules_sha256':sha(R/'data/cards_source.json'),'cards':preserved})
# Preserve the original design plan, then make the current plan point to the actual delivered image/prompt/review.
if not (R/'data/v7/redesign_plan_initial.json').exists():shutil.copyfile(R/'data/v7/redesign_plan.json',R/'data/v7/redesign_plan_initial.json')
actual_overrides={
 'C04':('上中缘短腕下压的敌盔近景','大敌盔—颈—肩承力块；顶部紧凑掌，不留横贯长臂','受击盔壳与短下压掌的上下关系'),
 'C25':('右下小掌牵引细雷的局部近景', '右下紧凑竖腕与小掌，单条窄雷斜向左上延伸', '以短小接点牵引一条受控雷路'),
 'R14':('俯视熊与猎物穿过低矮障碍的远景', '低岩让开连续追猎路线，熊与前方猎物分离', '沿完整地面路线追猎，用低障碍保持身体可读'),
 'U31':('斜向石路的远近透视','五个坑沿透视收小，路面保持完整大形','连续落足与坑底雷线属于同一路段'),
 'R27':('俯视同一熊影扫过一大一小两件器物','同一明暗影界切过两物旧面与新面','外部器物随同一道熊影局部转换'),
 'U41':('完整护片掀角的斜侧近景','旧外壳、单翻角、连续扁平内刃三层','一体硬刃藏于旧壳内，不使用活体手爪'),
 'U05':('熊双掌协同翻顶巨岩的侧向全身','左下地面支点、完整双足和上方撞盾点','借地面支点与双掌协同翻顶岩块撞盾')}
briefs=read('data/cards_art_briefs.json');brief_by={c['id']:c for c in briefs['cards']};ranking=[]
for p in plan['cards']:
    cid=p['id'];a=m['cards'][cid];review=read(a['review']);g=read(f'reviews/v7/generation_{cid}.json')
    assert a['revision']=='revised_v7' and review['decision']=='approve'
    assert review['master_sha256']==a['master_sha256'] and review['inspected_actual_images']
    assert int(str(g['attempt']).replace('attempt',''))==a['provenance']['attempt']
    actual=(R/a['prompt']).read_text().rstrip('\n')
    assert actual==(g.get('original_request_prompt') or g.get('prompt') or g.get('actual_prompt') or g.get('request',{}).get('prompt'))
    p.setdefault('initial_planned_prompt_file',p['prompt_file'])
    p.update(status='approved_exported',image_generated=True,image_visual_approved=True,selected_attempt=a['provenance']['attempt'],current_image=a['master'],current_image_sha256=a['master_sha256'],raw_image=a['provenance']['raw_path'],prompt_file=a['prompt'],prompt_sha256=a['prompt_sha256'],prompt=actual,final_review_file=a['review'],generation_record=a['provenance']['generation_record'],actual_observation=review['observations'],scene=review['observations'],anchors=review['anchors'])
    if cid in actual_overrides:p['camera'],p['shape'],p['semantic']=actual_overrides[cid]
    p['reference_files']=[{'role':'identity','file':'references/identity/volibear_approved.png','sha256':sha(R/'references/identity/volibear_approved.png')}] + [{'role':'fixed_benchmark','id':rid,'file':f'cards/masters/{rid}.png','sha256':m['cards'][rid]['master_sha256']} for rid in p['anchors']]
    p['actual_generation_reference_manifest']='references/generation_inputs/manifest.json'
    b=brief_by[cid];art=b['art']
    art.update(abstraction_level=p['level'],representation_mode=p['family'],visual_family=p['family'],primary_verb=p['verb'],camera=p['camera'],silhouette=p['shape'],composition=p['scene'],signature=p['semantic'],revision='V7',actual_observation=review['observations'],negative_space='主形之外保留连贯背景；具体分布与裁切以已审母图和125像素对照为准。',visual_checks=[review['observations'],review['baseline_comparison'],review['paw_orientation_observation']],primary_reference_role='28张用户固定成品用于风格与质量比较；身份图仅用于角色比例和身份。纯环境图不硬塞熊头或肢体。')
    art['identity_anchors']=(['深蓝与青白的机制色','一个清楚的能量、材料或环境因果'] if p['level']=='M2' else ['镜头实际可见的灰白/深蓝熊体大形','短厚熊吻或连贯腕掌等可见身份结构','克制的青色身份强调'])
    art['reference_notes']=[{'id':rid,'path':f'cards/masters/{rid}.png','role':'user_locked_quality_benchmark','application_to_this_card':review['baseline_comparison']} for rid in p['anchors']]
    b.update(prompt=actual,prompt_zh=actual,reference_ids=p['anchors'],reference_categories=[p['family'],p['level']],similarity_group=p['family'])
    ranking.append({'id':cid,'name':b['name'],'source_order':ids.index(cid),'score':sum(review['quality_axes'].values()),'quality_axes':review['quality_axes'],'anchors':review['anchors'],'attempt':a['provenance']['attempt'],'master_sha256':a['master_sha256'],'review':a['review'],'comparison':review['comparison_file'],'observations':review['observations'],'baseline_comparison':review['baseline_comparison']})
ranking.sort(key=lambda c:(-c['score'],c['source_order']))
for i,c in enumerate(ranking,1):c['rank']=i
save('reports/revision_v7/quality_ranking.json',{'schema_version':7,'review_method':'Actual full image + fixed benchmarks + 250/125/gray + export-mask inspection. Five subjective axes, each 0–20. Scores organize review priority; they are not an objective guarantee of taste.','fixed_originals_unscored':sorted(locked),'axes':{'main_read':'动作/语义第一读法','large_shapes':'完整大形与留白','tone':'厚重气质与身份','finish':'结构、遮挡与成品细节','distinctiveness':'相邻卡的构图差异'},'cards':ranking})
with (R/'reports/revision_v7/quality_ranking.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['排名','ID','卡名','总分','主读','大形','气质','完成度','差异','定稿尝试','固定基准','观察'])
    for c in ranking:w.writerow([c['rank'],c['id'],c['name'],c['score'],*c['quality_axes'].values(),c['attempt'],' / '.join(c['anchors']),c['observations']])
md=['# V7 重绘卡图质量排序','', '61张重绘逐张实际检查后的主观比较。28张用户固定原图作为基准，不替用户重新打分。先通过结构、朝向、遮挡、因果、缩图和裁切硬门槛，再按五项各20分排序；同分按原卡表顺序。分数不抵消硬伤，也不保证个人审美一致。','', '| 排名 | 卡号 | 卡名 | 分数 | 主读 / 大形 / 气质 / 完成 / 差异 | 固定基准 | 定稿 |','|---:|---|---|---:|---|---|---:|']
for c in ranking:md.append(f"| {c['rank']} | {c['id']} | {c['name']} | {c['score']} | {' / '.join(map(str,c['quality_axes'].values()))} | {'、'.join(c['anchors'])} | a{c['attempt']:02d} |")
md+=['','每卡实际发现、基准比较、原图SHA和对照图路径见同目录JSON；详细图像记录在 `reviews/<ID>.json`。','', '## 跨组复审说明','', '生成作者之外的审稿者交叉看61张最终候选。两份交叉记录在 `reviews/v7/cross_review_artist_b.json` 与 `cross_review_artist_c.json`。明确阻断已返修；U05双掌协同翻岩、R25用地面边界槽表达重连的语义解释保留在 `root_cross_review_responses.json`。']
(R/'reports/revision_v7/QUALITY_RANKING.md').write_text('\n'.join(md)+'\n')
plan.update(schema_version=7,status='completed_actual_images_and_exports',image_generation_completed=True,completed_image_count=61,locked_cards_sha256=sha(R/'data/v7/user_locked_cards.json'),completed_at=now)
save('data/v7/redesign_plan.json',plan)
briefs.update(schema_version='7.0',source_sha256=sha(R/'data/cards_source.json'),readme='V7实际成品：28张用户固定原图，61张真实重绘含U28，89张卡与356个游戏导出。当前构图、提示词和审查对应实际最终图。',counts_by_abstraction=dict(Counter(b['art']['abstraction_level'] for b in briefs['cards'])),counts_by_representation=dict(Counter(b['art']['representation_mode'] for b in briefs['cards'])),reference_note_v7='固定基准28张直接在cards/masters中；U28已返工，U35固定。身份立绘在references/identity。无需全量下载研究图。')
briefs['abstraction_levels']['M2']='图形概括：允许完整环境、外部器物、轨迹或少量符号承载动作；用本组色彩与因果统一，不强加熊头、断肢或身份贴纸。'
briefs.pop('reference_note_v3',None)
if 'reference_mapping_research_snapshot' in briefs:briefs['reference_mapping_research_snapshot']['status']='Historical optional research snapshot; not the V7 generation input map. See references/generation_inputs/manifest.json.'
save('data/cards_art_briefs.json',briefs)
m.update(schema_version=7,status='complete_reviewed_exported',delivery_revision=7,reviewed_card_count=89,redrawn_card_count=61,user_locked_card_count=28,revised_ids=redrawn,latest_revision_ids=redrawn,completed_at=now)
save('data/asset_manifest.json',m)
save('state/style_lock.json',{'version':'volibear-v7-complete','positive_anchors':[{'id':cid,'path':f'cards/masters/{cid}.png','sha256':m['cards'][cid]['master_sha256']} for cid in ids if cid in locked],'identity':'references/identity/volibear_approved.png','body_logic_standard':'docs/ART_REVIEW_V7.md','source_of_lock':'User explicit keep list minus U28 in latest correction','U28':'Redrawn; must differ from fixed U35','scope':'Current approved images only; historical approval does not approve a new image.'})
print(json.dumps({'approved':61,'locked':28,'cards':89,'exports':356,'score_range':[min(c['score'] for c in ranking),max(c['score'] for c in ranking)]}))
