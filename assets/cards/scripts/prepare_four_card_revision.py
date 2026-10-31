"""Record explicitly authorized four-card revision; preserve historical originals."""
from pathlib import Path
import json, shutil, hashlib
R=Path(__file__).resolve().parents[1]
def read(p): return json.loads((R/p).read_text())
def save(p,x): (R/p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p): return hashlib.sha256((R/p).read_bytes()).hexdigest()
archive=R/'reports/revision_v7/before_four_card_revision'
archive.mkdir(exist_ok=True)
ids=['B01','C12','U36','T02']
for cid in ids:
    for rel in [f'cards/masters/{cid}.png',f'reviews/{cid}.json']:
        dest=archive/Path(rel).name
        if not dest.exists(): shutil.copy2(R/rel,dest)
for rel in ['data/v7/user_locked_cards.json','data/v7/redesign_plan.json','data/v7/state.json','state/style_lock.json']:
    dest=archive/Path(rel).name
    if not dest.exists(): shutil.copy2(R/rel,dest)
lock=read('data/v7/user_locked_cards.json')
lock['cards']=[c for c in lock['cards'] if c['id'] not in ['B01','C12']]
lock.update(locked_count=26,revision_count=63,revision='V7_four_card_revision',user_decision='2026-10-30: user authorized B01 C12 U36 T02 redraw after detailed design approval; other locked originals unchanged')
save('data/v7/user_locked_cards.json',lock)
style=read('state/style_lock.json')
style['positive_anchors']=[c for c in style['positive_anchors'] if c['id'] not in ['B01','C12']]
style['source_of_lock']=lock['user_decision']
save('state/style_lock.json',style)
plans=read('data/v7/redesign_plan.json')
design={
'B01':dict(name='打击',level='M0',family='基础肉搏',verb='短挥',anchors=['U17','U23'],camera='正常透视侧前半身',scene='肩带动短促斜挥，头肩胸臂比例自然；暗赭背景与一条克制动作弧',shape='完整肩臂连接与自然头身比',semantic='耐看直接的基础打击',avoid=['巨掌小头','满幅黄红爆裂','塑料刀片青爪']),
'C12':dict(name='厚重皮毛',level='M0',family='承力与接触',verb='挡开',anchors=['U17','U23'],camera='三分之二侧后肩背',scene='颈根肩峰上臂明确，少数毛面稳住小箭斜擦偏转',shape='连续肩背实体非毛团',semantic='厚实皮毛抗击',avoid=['毛垫','钻入毛团的尖物','无身体定位']),
'U36':dict(name='奔雷',level='M0',family='发力与路径',verb='蹬出',anchors=['U19','U40'],camera='低机位侧后单足近景',scene='单只后足前掌承重脚跟抬起，短小腿自然出画，细雷向前延续',shape='蹬地支点与前进路径',semantic='返能起步非攻击落地',avoid=['胯部两腿毛裤','悬垂大脚','爆炸攻击']),
'T02':dict(name='风暴之躯',level='M1',family='躯体与风暴',verb='护住并释放',anchors=['U19','U40'],camera='偏侧半身剪影',scene='宽肩低头厚胸肩颈明确，来击止于外缘，两侧雷向外扫出',shape='稳定连续半身熊形非对称毛山',semantic='躯体风暴化防护与释放',avoid=['毛山圆顶','小头大圆身','软胶体态'])}
for cid,d in design.items():
    p=next((p for p in plans['cards'] if p['id']==cid),None)
    if p is None: p={'id':cid};plans['cards'].append(p)
    p.update(d,status='needs_redraw',image_visual_approved=False,revision_reason='User requested corrected abstraction and natural tone 2026-10-30')
plans.update(plan_count=len(plans['cards']),status='four_card_revision_in_progress',image_generation_completed=False,locked_cards_sha256=sha('data/v7/user_locked_cards.json'))
save('data/v7/redesign_plan.json',plans)
s=read('data/v7/state.json')
for cid in ids:
    s['cards'].setdefault(cid,{'attempts':[]})['status']='needs_redraw'
s.update(locked=26,to_redraw=63,status='four_card_revision_in_progress',remaining=4,visually_approved=59)
save('data/v7/state.json',s)
print('Recorded four-card queue; archived prior masters and metadata; remaining 26 locked unchanged.')
