"""Descriptive metrics, costs and evidence indexes for the completed branches."""
from collections import Counter
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


def main():
    rows=[];annotations={};costs=[]
    blind={r['run']:r['anonymous_id'] for r in json.loads((EXP/'configs/blind_order.json').read_text())}
    natural=json.loads((OLD/'analysis/annotations.json').read_text())['runs']
    common=set.intersection(*(set(r['strategies']) for r in natural.values()))
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
                              'initial_vs_final':metrics(EXP/'checkpoints'/scene/'final.png',run/'workspace/final.png')},
             'human_rating':None}
        row['final_image_resolution']=list(Image.open(run/'workspace/final.png').size)
        row['required_final_resolution_met']=row['final_image_resolution']==[640,360]
        technical=run/'analysis/technical/result.json'
        if technical.exists():
            row['technical']=json.loads(technical.read_text())
            regenerated=run/'analysis/technical/replica/final.png'
            if regenerated.exists():row['image_metrics']['original_vs_regenerated']=metrics(run/'workspace/final.png',regenerated)
        visual=EXP/'visual_reviews'/blind[run.name]/'workspace/visual_evaluation.json'
        if visual.exists():row['automated_visual_evaluation']=json.loads(visual.read_text())
        annotation=EXP/'technical_reviews'/run.name/'workspace/trajectory_annotation.json'
        if annotation.exists():annotations[run.name]=json.loads(annotation.read_text())
        geometry=run/'analysis/technical/capture/target_geometry/geometry.json'
        if geometry.exists():
            state=json.loads(geometry.read_text())
            if scene=='S01':
                row['chairs']=[{'chair':c['chair'],'gap':c['lowest_part_support']['minimum_signed_gap'] if c['lowest_part_support'] else None,
                                'normalized_gap':c['normalized_lowest_gap'],
                                'wheel_gaps':[w['minimum_signed_gap'] for w in c['wheel_support']],
                                'floor_penetration_samples':sum(w['vertices_below_local_floor_top'] for w in c['wheel_support']),
                                'wheel_axis_abs_z':[abs(part['local_z_world_axis'][2]) for part in c['parts'] if re.search(r'wheel|tyre|tire',part['name'],re.I)],
                                'wheel_base_disconnections_sampled':[x for x in c['wheel_base_connections'] if x['surface_intersection_pairs']==0 and x['sampled_surface_distance']>0.0001]}
                               for c in state['chairs']]
            if scene=='S02':row['door_projection_evidence']=state.get('door_objects',[])
        rows.append(row)
        costs.append(usage_record(run,'core' if repetition=='R1' else 'extra_repeat'))
    for directory,scope in [('teachers','teacher_diagnosis'),('visual_reviews','automated_visual_evaluation'),('technical_reviews','trajectory_annotation')]:
        for run in sorted((EXP/directory).iterdir()):costs.append(usage_record(run,scope))
    costs.append(usage_record(EXP/'preflight/student','engineering_preflight'))
    grouped={}
    for scope in sorted({r['scope'] for r in costs}):
        records=[r for r in costs if r['scope']==scope];tokens=Counter()
        for r in records:tokens.update(r['reported_tokens'])
        grouped[scope]={'sessions':len(records),'requests':sum(r['requests'] for r in records),
                        'usage_records':sum(r['usage_records'] for r in records),'known_tokens':dict(tokens),
                        'missing_usage_requests':sum(len(r['requests_without_usage']) for r in records),
                        'sdk_seconds':sum(r.get('sdk_wall_seconds',0) for r in records)}
    totals=Counter()
    for scope in grouped.values():totals.update(scope['known_tokens'])
    write(EXP/'analysis/usage_summary.json',{'scopes':grouped,'sessions':costs,'all_known_tokens':dict(totals),
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
    write(EXP/'analysis/strategy_metrics.json',{'common_generic_labels':sorted(common),'pairs':pairs,'raw_annotations':annotations,
         'limitations':'One automated evidence annotator with exploratory label granularity. Unknown labels excluded from sets, not declared absent. Inherited code and new actions are distinguished in raw records. Pairs are not independent reference tasks.'})
    with (EXP/'analysis/strategy_metrics.csv').open('w') as f:
        columns=['scene','repetition','pair_kind','left','right','all_jaccard','without_common_jaccard','target_jaccard']
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(pairs)
    knowledge=[{'run':name,'candidate':candidate} for name,a in annotations.items() for candidate in a['candidate_knowledge']]
    write(EXP/'analysis/candidate_knowledge.json',{'candidates':knowledge,'status':'Evidence candidates only, not learned skills or validated transfer.'})
    print('Summarized',len(rows),'branches,',len(pairs),'strategy pairs and',len(knowledge),'candidate knowledge records.')
    print(json.dumps(grouped,indent=2))


if __name__=='__main__':main()
