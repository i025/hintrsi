"""Native-image CLI audit of six deterministically selected historical render cases."""
import asyncio
import csv
import json
import os
import sys
import time
from pathlib import Path

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
OLD = OUT.parent / 'trajectory_capability_20261126_020200'
sys.path.insert(0, str(OUT / 'source'))
from codex_cli_bridge import CodexBridge, default_command
os.environ['CODEX_HOME'] = str(Path.cwd() / 'work/cli_home')
for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
    os.environ.pop(key, None)
rows = [r for r in csv.DictReader((OLD / 'audit/scene_artifact_inventory.csv').open())
    if r['kind'] == 'student_trajectory']
selected = []
task_ids = set()
for version, count in [('scene_rsi_v2', 1), ('scene_rsi_v2_1', 1), ('scene_rsi_v2_2', 1), ('scene_rsi_v3', 3)]:
    found = 0
    for row in sorted(rows, key=lambda r: r['path']):
        trace = Path(row['path'])
        task = next((part for part in trace.parts if part.startswith(('commons_', 'bw_'))), None)
        if version not in trace.parts or 'audit_sources' in trace.parts or not task or task in task_ids:
            continue
        reference = trace.parent / 'reference.png'
        if not reference.is_file():
            continue
        steps = sorted(trace.parent.glob('steps/*/final.png'))
        final = trace.parent / 'final.png'
        if not final.is_file() and not steps:
            continue
        images = [reference]
        if steps:
            images.append(steps[0])
        last = final if final.is_file() else steps[-1]
        if last not in images:
            images.append(last)
        case = {'case': f'VX{len(selected)+1:02d}', 'version': version, 'task': task,
            'trajectory': str(trace), 'images': [str(p) for p in images],
            'sampling': 'Lexicographically first available rendered trajectory per version, skipping previously selected task IDs; three distinct task IDs for v3. Not selected by score or observed quality. Missing-render attempts remain in full text audit.'}
        selected.append(case)
        task_ids.add(task)
        found += 1
        if found == count:
            break
manifest = {'saved_before_visual_review': time.time(), 'cases': selected,
    'scope': 'Six cases, six reference task IDs. This is a bounded visual sample, not full population or an efficacy/causal comparison. Exact image-file counts below; task IDs do not prove globally unique photo content.'}
manifest_path = OUT / 'config/scene_visual_expansion_manifest.json'
if manifest_path.exists():
    raise FileExistsError(manifest_path)
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')

async def main():
    for case in selected:
        name = case['case']
        bridge = CodexBridge(OUT / 'logs' / ('visual_' + name), command=default_command() +
            [part for path in case['images'] for part in ('--image', path)])
        prompt = '''Limited historical visual audit, English at most 800 words. Native attachments are unmodified original files. Image 1 is the reference; image 2 is first available rendered step (or final if no steps); image 3, if present, is the last/final selected render. Compare observed 2D multi-object coverage, material/texture detail, visible part adjacency, pose, camera/perspective and lighting/render issues. Separate directly visible observations from geometric hypotheses. Pixels do not establish physical contact, hidden object count, teacher diagnosis, student adoption or causal improvement. This case is a deterministic small sample, not a conclusion about all Scene RSI experiments. No numeric quality score or new scene code. Cite image numbers and source paths, including uncertainty from occlusion and rendering.\n''' + json.dumps(case)
        body = {'model': 'gpt-6.1-terra', 'messages': [{'role': 'user', 'content': prompt}], 'tools': []}
        try:
            response = await bridge.chat(body, route={'session': 'followup-visual-' + name, 'role': 'teacher', 'phase': 'audit'})
            (OUT / 'audit' / ('visual_' + name + '.md')).write_text(response['choices'][0]['message']['content'] + '\n')
            case.update(status='complete', response=response, completed_at=time.time())
        except Exception as error:
            case.update(status='failed', error=str(error))
        finally:
            await bridge.close()
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({k: v for k, v in case.items() if k != 'response'}), flush=True)
asyncio.run(main())
