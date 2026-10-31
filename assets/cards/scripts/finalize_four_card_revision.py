"""Finalize only the explicitly authorized four-card revision after visual approval."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads((R/p).read_text())
def save(p,x):(R/p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
ids=['B01','C12','U36','T02'];s=read('data/v7/state.json');m=read('data/asset_manifest.json');p=read('data/v7/redesign_plan.json')
assert s['remaining']==0
assert sha('data/cards_source.json')=='e74335e588b5b0b7be8a1f1ec08dff94091c1af158efa718e1cedbfff115c17c'
for c in p['cards']:
 if c['id'] not in ids:continue
 a=m['cards'][c['id']];rv=read(a['review']);assert rv['decision']=='approve' and rv['master_sha256']==sha(a['master'])
 c.update(status='approved_exported',image_generated=True,image_visual_approved=True,selected_attempt=a['provenance']['attempt'],current_image=a['master'],current_image_sha256=a['master_sha256'],raw_image=a['provenance']['raw_path'],prompt_file=a['prompt'],prompt_sha256=a['prompt_sha256'],prompt=(R/a['prompt']).read_text().strip(),final_review_file=a['review'],generation_record=a['provenance']['generation_record'],actual_observation=rv['observations'])
p.update(status='complete',image_generation_completed=True,plan_count=63)
save('data/v7/redesign_plan.json',p)
m['status']='v7_complete';save('data/asset_manifest.json',m)
lock=read('data/v7/user_locked_cards.json');pres=[]
for c in lock['cards']:
 assert sha(f"cards/masters/{c['id']}.png")==c['sha256']
 for e in c['locked_exports']:assert sha(e['path'])==e['sha256']
 pres.append(c['id'])
save('reports/revision_v7/four_card_preservation.json',{'locked_unchanged':pres,'unchanged_masters':26,'unchanged_exports':104,'rules_unchanged':True,'selected':{i:m['cards'][i]['provenance']['attempt'] for i in ids}})
text=(R/'README.md').read_text().replace('28张','26张').replace('61张','63张').replace('61份','63份').replace('112个','104个').replace('固定原图：B01、B03','固定原图：B03').replace('C09、C12、C13','C09、C13')
text=text.replace('## 先看这些','## 四张追加返修（2026-10-30）\n\nB01、C12经用户授权解除旧锁定；连同U36、T02完成真实重画及独立复审。C12背后错位辫饰已删除；旧图与旧清单备份于 `reports/revision_v7/before_four_card_revision/`。本次26张固定母图与104导出字节保留检查见 `reports/revision_v7/four_card_preservation.json`。此前总览/质量榜/ZIP是历史交付，当前图像以离线图库和asset_manifest为准。\n\n## 先看这些')
(R/'README.md').write_text(text)
print('Finalized four-card metadata and confirmed remaining locked assets unchanged.')
