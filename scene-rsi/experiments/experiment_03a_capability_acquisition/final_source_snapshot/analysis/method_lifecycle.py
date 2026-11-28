"""Separate visible claims, written programs, successful executions, and retained states."""
from pathlib import Path
import ast
import json

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_01_natural_trajectories'
rows=[]
for run in sorted((EXP/'runs').iterdir()):
 events=json.loads((run/'analysis/sdk_events.json').read_text())
 visible=[{'event_index':ev['event_index'],'text':block['text']} for ev in events if ev['type']=='assistant'
          for block in ev['message'].get('content',[]) if 'text' in block]
 written=[{'event_index':ev['event_index'],'tool':block['name'],'file':block['input'].get('file_path')}
          for ev in events if ev['type']=='assistant' for block in ev['message'].get('content',[])
          if block.get('name') in ('Write','Edit')]
 executed=[]
 for capture in sorted((run/'capture').glob('blender_*')):
  result=capture/'result.json';code=capture/'code/build.py'
  if result.exists() and code.exists():
   result=json.loads(result.read_text());executed.append({'source':str(code.relative_to(ROOT)),'exit_code':result['exit_code'],
                                                        'saved_artifacts':result['saved_artifacts']})
 program=ast.parse((run/'workspace/build.py').read_text())
 random_calls=[node.func.attr for node in ast.walk(program) if isinstance(node,ast.Call)
               and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='random']
 rows.append({'run':run.name,'observable_assistant_text':visible,'proposal_limit':'No hidden reasoning inferred; final delivery claims do not establish a proposed technical method.',
              'written_file_tool_events':written,'actually_executed_source_versions':executed,
              'retained_source':str((run/'workspace/build.py').relative_to(ROOT)),
              'retained_scene_state':str((run/'analysis/technical/capture/final_state.json').relative_to(ROOT)),
              'declared_seed_without_other_random_call':bool('seed' in random_calls and not any(call!='seed' for call in random_calls)),
              'interpretation':'A declared unused random seed is not evidence of executed randomized geometry. Reachability and actual scene properties ground strategy labels.'})
(EXP/'analysis/method_lifecycle.json').write_text(json.dumps(rows,indent=2))
print('written/executed/retained evidence indexed for',len(rows),'runs')
