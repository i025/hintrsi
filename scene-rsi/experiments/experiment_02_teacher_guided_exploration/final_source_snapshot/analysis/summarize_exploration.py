"""Descriptive metrics, costs and evidence indexes for the completed branches."""
from collections import Counter
from copy import deepcopy
import csv
from itertools import combinations
import json
from pathlib import Path
import re
from PIL import Image

from compare_trajectories import jaccard
from image_metrics import metrics
from summarize_run import summarize
from usage_summary import summarize as usage_record

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_02_teacher_guided_exploration'
OLD=ROOT/'experiments/experiment_01_natural_trajectories'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def output_connected_nodes(material):
    names={n['name'] for n in material['nodes'] if n['type']=='ShaderNodeOutputMaterial'}
    while True:
        upstream=names|{link['from_node'] for link in material['links'] if link['to_node'] in names}
        if upstream==names:break
        names=upstream
    return [n['type'] for n in material['nodes'] if n['name'] in names]


def main():
    rows=[];annotations={};raw_annotations={};costs=[]
    audit=json.loads((EXP/'analysis/annotation_audit.json').read_text())
    blind={r['run']:r['anonymous_id'] for r in json.loads((EXP/'configs/blind_order.json').read_text())}
    state_changes={r['run']:r for r in json.loads((EXP/'analysis/state_changes.json').read_text())}
    door_metrics={r['run']:r for r in json.loads((EXP/'analysis/door/metrics.json').read_text())['runs']}
    natural=json.loads((OLD/'analysis/annotations.json').read_text())['runs']
    common=set.intersection(*(set(r['strategies']) for r in natural.values()))
    initial_metrics={scene:metrics(EXP/'checkpoints'/scene/'reference.png',EXP/'checkpoints'/scene/'final.png')
                     for scene in ('S01','S02','S03')}
    for run in sorted((EXP/'runs').iterdir()):
        index=summarize(run)
        scene,condition,repetition=run.name.split('-')
        row={'run':run.name,'scene':scene,'condition':condition,'repetition':int(repetition[1:]),
             'status':index['status']['status'],'model_requests':index['model_requests'],
             'blender_executions':len(index['blender_executions']),
             'blender_nonzero_exits':sum(x['result'] is not None and x['result']['exit_code']!=0 for x in index['blender_executions']),
             'blender_python_traceback_captures':sum(bool(x['python_traceback_logs']) for x in index['blender_executions']),
             'model_errors':len(index['model_errors']),
             'sdk_seconds':json.loads((run/'capture/trajs.json').read_text())['metadata']['wall_seconds'],
             'code_changed':(run/'workspace/build.py').read_bytes()!=(EXP/'checkpoints'/scene/'build.py').read_bytes(),
             'image_metrics':{'reference_vs_final':metrics(run/'workspace/reference.png',run/'workspace/final.png'),
                              'reference_vs_initial':initial_metrics[scene],
                              'initial_vs_final':metrics(EXP/'checkpoints'/scene/'final.png',run/'workspace/final.png')},
             'human_rating':None}
        row['final_image_resolution']=list(Image.open(run/'workspace/final.png').size)
        events=json.loads((run/'analysis/sdk_events.json').read_text())
        row['sdk_tool_errors']=[{'event_index':e['event_index'],'tool_use_id':b.get('tool_use_id'),
                                'message':str(b.get('content'))[:600]}
                               for e in events for b in e['message'].get('content',[])
                               if isinstance(b,dict) and b.get('is_error')]
        row['required_final_resolution_met']=row['final_image_resolution']==[640,360]
        technical=run/'analysis/technical/result.json'
        if technical.exists():
            row['technical']=json.loads(technical.read_text())
            regenerated=run/'analysis/technical/replica/final.png'
            if regenerated.exists():row['image_metrics']['original_vs_regenerated']=metrics(run/'workspace/final.png',regenerated)
        visual=EXP/'visual_reviews'/blind[run.name]/'workspace/visual_evaluation.json'
        if visual.exists():row['automated_visual_evaluation']=json.loads(visual.read_text())
        annotation=EXP/'technical_reviews'/run.name/'workspace/trajectory_annotation.json'
        if annotation.exists():
            raw_annotations[run.name]=json.loads(annotation.read_text())
            annotations[run.name]=deepcopy(raw_annotations[run.name])
            for strategy in annotations[run.name]['strategies']:
                strategy['label']=audit['label_aliases'].get(strategy['label'],strategy['label'])
            for correction in audit['comparison_overrides']:
                if correction['run']!=run.name:continue
                value=correction['value']
                annotations[run.name]['exploration_assessment']['actual_comparison']=value
                for candidate in annotations[run.name]['candidates']:candidate['actual_comparison']=value
                for strategy in annotations[run.name]['strategies']:
                    if strategy['label']=='candidate_comparison':strategy['status']='executed' if value is True else 'unknown'
                if value is True and not any(s['label']=='candidate_comparison' for s in annotations[run.name]['strategies']):
                    annotations[run.name]['strategies'].append({'label':'candidate_comparison','scope':'target','status':'executed',
                        'inherited_from_checkpoint':False,'evidence':correction['evidence']})
            for correction in audit['candidate_comparison_overrides']:
                if correction['run']==run.name:
                    annotations[run.name]['candidates'][correction['candidate_index']]['actual_comparison']='unknown'
        geometry=run/'analysis/technical/capture/target_geometry/geometry.json'
        if geometry.exists():
            state=json.loads(geometry.read_text())
            if scene=='S01':
                row['chairs']=[{'chair':c['chair'],'gap':c['lowest_part_support']['minimum_signed_gap'] if c['lowest_part_support'] else None,
                                'normalized_gap':c['normalized_lowest_gap'],
                                'wheel_gaps':[w['minimum_signed_gap'] for w in c['wheel_support']],
                                'wheels_with_below_floor_samples':sum(w['vertices_below_local_floor_top'] for w in c['wheel_support']),
                                'wheel_axis_abs_z':[abs(part['local_z_world_axis'][2]) for part in c['parts'] if re.search(r'wheel|tyre|tire',part['name'],re.I)],
                                'post_base_seat_connections':c['post_base_seat_connections'],
                                'wheel_base_disconnections_sampled':[x for x in c['wheel_base_connections'] if x['surface_intersection_pairs']==0 and x['sampled_surface_distance']>0.0001]}
                               for c in state['chairs']]
            if scene=='S02':row['door_projection_evidence']=state.get('door_objects',[])
        if scene=='S02':row['door_mask_comparison']=door_metrics[run.name]
        if scene=='S03':
            final_state=json.loads((run/'analysis/technical/capture/final_state.json').read_text())
            target=next(o for o in final_state['objects'] if o['name']=='right marble counter')
            materials=[m for m in final_state['materials'] if m['name'] in target['materials']]
            changes=state_changes[run.name]
            row['countertop']={'target':target['name'],'bound_materials':target['materials'],
                'nodes':{m['name']:[n['type'] for n in m['nodes']] for m in materials},
                'output_connected_nodes':{m['name']:output_connected_nodes(m) for m in materials},
                'geometric_vein_objects':sum('marble vein' in o['name'] for o in final_state['objects']),
                'camera_or_light_changed':changes['camera_or_light_changed'],'world_changed':changes['world_changed'],
                'display_changes':changes['render_changed'],
                'fixed_environment_image':str((run/'analysis/technical/capture/target_geometry/fixed_camera_lighting.png').relative_to(EXP)),
                'scope':'Actual final scene state and bound shader; execution and comparison claims require the SDK trajectory.'}
        rows.append(row)
        costs.append(usage_record(run,'core' if repetition=='R1' else 'extra_repeat'))
    for directory,scope in [('teachers','teacher_diagnosis'),('visual_reviews','automated_visual_evaluation'),('technical_reviews','trajectory_annotation')]:
        for run in sorted((EXP/directory).iterdir()):costs.append(usage_record(run,scope))
    costs.append(usage_record(EXP/'preflight/student','engineering_preflight'))
    costs.append(usage_record(EXP/'preflight/native_agent_fix/session','engineering_preflight'))
    grouped={}
    for scope in sorted({r['scope'] for r in costs}):
        records=[r for r in costs if r['scope']==scope];tokens=Counter()
        for r in records:tokens.update(r['reported_tokens'])
        grouped[scope]={'sessions':len(records),'requests':sum(r['requests'] for r in records),
                        'usage_records':sum(r['usage_records'] for r in records),'known_tokens':dict(tokens),
                        'missing_usage_requests':sum(len(r['requests_without_usage']) for r in records),
                        'sdk_seconds':sum(r.get('sdk_wall_seconds',0) for r in records),
                        'reported_local_child_cpu_seconds':sum(r.get('reported_child_cpu_seconds',0) for r in records),
                        'maximum_sampled_rss_sum_mib':max(r.get('sampled_peak_rss_sum_mib',0) for r in records)}
    totals=Counter()
    for scope in grouped.values():totals.update(scope['known_tokens'])
    errors=[]
    for record in costs:
        path=ROOT/record['directory']/'bridge/model_errors.jsonl'
        if path.exists():
            errors += [{'run':record['run'],'scope':record['scope'],**json.loads(line)} for line in path.read_text().splitlines()]
    write(EXP/'analysis/usage_summary.json',{'scopes':grouped,'sessions':costs,'all_known_tokens':dict(totals),'model_errors':errors,
        'actual_billing_usd':None,'ofox_requests':0,
        'limitations':['Reported token totals are lower bounds when any requests lack usage.',
                       'Cached input/reasoning output are subsets; do not add them again.',
                       'SDK estimated dollar amounts do not represent subscription charges.',
                       'Teacher role is identified from actual session directories; original teacher bridge route labels were legacy student metadata.',
                       'Controller conversation and provider compute are not observed.']})
    write(EXP/'analysis/results.json',{'runs':rows,'human_ratings_collected':0,'independent_reference_tasks':3,
                                      'scope':'Core and repeat separated; no causal certainty, statistical significance, or long-term capability claim.'})
    def strategies(name,kind):
        values=annotations[name]['strategies']
        selected={s['label'] for s in values if s['status'] in ('executed','retained') and (kind!='target' or s['scope']=='target')}
        return selected-common if kind=='without_common' else selected
    pairs=[]
    for scene in ('S01','S02','S03'):
        for rep in (1,2):
            names=[r['run'] for r in rows if r['scene']==scene and r['repetition']==rep and r['run'] in annotations]
            for left,right in combinations(names,2):
                pairs.append({'scene':scene,'repetition':rep,'pair_kind':'within_repeat_conditions','left':left,'right':right,
                              **{kind+'_jaccard':jaccard(strategies(left,kind),strategies(right,kind))
                                 for kind in ('all','without_common','target')}})
        for group in range(5):
            left=scene+'-E'+str(group)+'-R1';right=scene+'-E'+str(group)+'-R2'
            if left in annotations and right in annotations:
                pairs.append({'scene':scene,'repetition':None,'pair_kind':'same_condition_repeats','left':left,'right':right,
                              **{kind+'_jaccard':jaccard(strategies(left,kind),strategies(right,kind))
                                 for kind in ('all','without_common','target')}})
    write(EXP/'analysis/strategy_metrics.json',{'common_generic_labels':sorted(common),'pairs':pairs,'raw_annotations':raw_annotations,
         'metric_annotations':annotations,'annotation_audit':audit,
         'limitations':'One automated evidence annotator with exploratory label granularity. Unknown labels excluded from sets, not declared absent. Inherited code and new actions are distinguished in raw records. Pairs are not independent reference tasks.'})
    with (EXP/'analysis/strategy_metrics.csv').open('w') as f:
        columns=['scene','repetition','pair_kind','left','right','all_jaccard','without_common_jaccard','target_jaccard']
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(pairs)
    knowledge=[{'run':name,'candidate':candidate} for name,a in annotations.items() for candidate in a['candidate_knowledge']]
    write(EXP/'analysis/candidate_knowledge.json',{'candidates':knowledge,'status':'Evidence candidates only, not learned skills or validated transfer.'})
    exploration=[{'run':name,**a['exploration_assessment'],'candidates':a['candidates'],
                  'failure_or_stopping_observations':a['failure_or_stopping_observations']} for name,a in annotations.items()]
    write(EXP/'analysis/exploration_summary.json',{'runs':exploration,'annotation_audit':audit,
        'scope':'Evidence-backed proposals, execution attempts, observations and retention are separate. Path counts are automated annotations, not an overall exploration-quality score.'})
    print('Summarized',len(rows),'branches,',len(pairs),'strategy pairs and',len(knowledge),'candidate knowledge records.')
    print(json.dumps(grouped,indent=2))


if __name__=='__main__':main()
