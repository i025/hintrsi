"""Measure positive vertical separation within each student coordinate system."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]/'experiments/experiment_01_natural_trajectories'
ann=json.loads((ROOT/'analysis/annotations.json').read_text());rows=[]
for name,a in ann['runs'].items():
 if name.startswith('S03'):continue
 state=json.loads((ROOT/a['state_file']).read_text());objects={o['name']:o for o in state['objects']}
 if name.startswith('S01'):
  support=set(a['state_component_evidence']['room:floor']+a['state_component_evidence']['room:boards']);target={n for k,ns in a['state_component_evidence'].items() if k.startswith('chair:') for n in ns};assembly='chair'
 else:
  support=set(a['state_component_evidence']['room:floor']+a['state_component_evidence']['rug:slab']);target=set(a['state_component_evidence']['bed:base']+a['state_component_evidence']['bed:mattress']);assembly='bed'
 top=max(p[2] for n in support for p in objects[n]['world_bbox_corners']);bottom=min(p[2] for n in target for p in objects[n]['world_bbox_corners']);gap=bottom-top
 rows.append({'run':name,'assembly':assembly,'support_max_z':top,'assembly_min_z':bottom,'positive_vertical_separation':gap,'units':'student Blender coordinate units, not GT-aligned metric distance','proof_scope':'Strict positive vertical separation proves no contact with the listed floor/rug surfaces. Overlapping bounding boxes do not establish contact. No dynamics claim.','support_objects':sorted(support),'assembly_objects':sorted(target),'state_evidence':a['state_file']})
 print(name,assembly,round(gap,6))
(ROOT/'analysis/support_separation.json').write_text(json.dumps(rows,indent=2))
for row in rows:
 if row['positive_vertical_separation']>0:
  defects=ann['runs'][row['run']]['defects'];key=row['assembly']+'_floor_separation'
  if not any(item['id']==key for item in defects):
   defects.append({'id':key,'object':row['assembly'],'observation':'The complete inspected assembly is vertically separated from the highest floor/rug surface by '+str(row['positive_vertical_separation'])+' student coordinate units. No connecting support geometry was found in the delivered source/state.','evidence':['analysis/support_separation.json',row['state_evidence']],'kind':'measured_intra_scene_geometry'})
(ROOT/'analysis/annotations.json').write_text(json.dumps(ann,indent=2))
