from pathlib import Path
import numpy as np
import render as r
rows=[]
for name,c in r.CLIPS.items():
    if name in r.DEATH_ATLASES:continue
    upper=[];lower=[];errors=[]
    for t in np.linspace(0,1,101):
        angles,offsets,_=r.pose(name,t);world=r.world(angles,offsets)
        parent,angle=world['chest'];expected=parent+r.rot(angle)@np.array(r.BONES['shoulder_near']['local'])
        errors.append(float(np.linalg.norm(world['shoulder_near'][0]-expected)))
        upper.append(angles['shoulder_near']);lower.append(angles['elbow_near'])
    rows.append({'clip':name,'shoulder_attachment_max_error_px':max(errors),'upper_local_range_deg':float(np.degrees(np.ptp(upper))),'forearm_relative_range_deg':float(np.degrees(np.ptp(lower)))})
report={'scope':'Analytical joint attachment and motion ranges; does not replace visual review','far_braid_under_head':r.PARTS['braid_far']['z']<r.PARTS['head']['z'],'near_arm_in_front_of_braids':min(r.PARTS[n]['z'] for n in ['upper_arm_near','forearm_near','hand_near'])>max(r.PARTS[n]['z'] for n in ['braid_near','braid_far']),'clips':rows}
r.js(r.REPO/'reports/animation_revision_v9/joint_checks.json',report)
assert report['far_braid_under_head'] and report['near_arm_in_front_of_braids']
assert all(x['shoulder_attachment_max_error_px']<1e-8 for x in rows)
assert all(x['forearm_relative_range_deg']>x['upper_local_range_deg'] for x in rows if not r.CLIPS[x['clip']]['loop'])
print('Attachment/layering and active-action forearm amplitude checks passed:',len(rows),'clips')
