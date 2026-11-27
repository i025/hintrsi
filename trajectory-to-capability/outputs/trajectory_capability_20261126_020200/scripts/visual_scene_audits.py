import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
BASE=Path('/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs')
sys.path.insert(0,str(OUT/'source'))
from codex_cli_bridge import CodexBridge,default_command
os.environ['CODEX_HOME']=str(Path.cwd()/'work/cli_home')
for n in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):os.environ.pop(n,None)

cases=[('SV01',[BASE/'stagewise_teaching_student_selfcheck_pilot'/p for p in ['sources/D01.jpg','tasks/D01/stages/01/initial_build/final.png','tasks/D01/stages/01/visual_revision_build/final.png']],
    'Image order: original office photograph, initial stage-1 room/viewpoint render, stage-1 visual-revision render. This stage intentionally omits furniture. Compare camera, room shell, illumination, image borders and projection. Do not criticize missing later-stage objects as a failure of this stage.'),
 ('SV02',[BASE/'stagewise_teaching_student_selfcheck_pilot'/p for p in ['sources/T01.jpg','tasks/T01/stages/05/initial_build/final.png','tasks/T01/delivery/final.png']],
    'Image order: original kitchen photograph, stage-5 initial render, final delivered render. Inspect multi-object coverage, spatial position/direction, visible component contacts, material/texture detail, lighting, camera and borders. These are the same historical test image, not a new run.'),
 ('SV03',[BASE/'teacher_self_evolution_human_pilot'/p for p in ['sources/E02.jpg','tasks/E02_M0_R2/final.png','tasks/E02_M1_R2/final.png']],
    'Image order: original kitchen photograph, M0-guided R2 final render, M1-guided R2 final render. These are separate student generations with history-dependent R2 guidance, not a strict common-state intervention. Identify visible discrepancies without asserting a causal M1 effect or a universal quality ranking.')]

async def main():
    manifest=[]
    for name,images,context in cases:
        missing=[str(p) for p in images if not p.exists()]
        if missing:
            manifest.append({'case':name,'completed':False,'missing_images':missing});continue
        directory=OUT/'evidence/scene_visual_inputs'/name;directory.mkdir(parents=True)
        copies=[]
        for i,p in enumerate(images,1):
            target=directory/f'{i}_{p.name}';shutil.copy2(p,target);copies.append(str(target))
        bridge=CodexBridge(OUT/'logs'/f'visual_{name}',command=default_command()+[part for p in images for part in ('--image',str(p))])
        prompt='''Perform a limited observational visual audit, in English, at most 900 words. The three native image attachments are actual historical source/render images, unedited. Separate directly visible 2D observations from hypotheses about 3D geometry or code. Image appearance alone cannot establish physical connectivity, object counts behind occlusion, correctness of hidden geometry, teacher diagnosis, or student adoption. Do not infer all experiments from this case. No numeric automated score or causal advantage claim. Cite image numbers and describe evidence for each observed concern.\n'''+context
        body={'model':'gpt-6.1-terra','messages':[{'role':'user','content':prompt}],'tools':[]}
        (directory/'request.json').write_text(json.dumps({'prompt':prompt,'native_image_paths':[str(p) for p in images],'copies':copies,'model':'gpt-6.1-terra','reasoning_effort':'low'},indent=2)+'\n')
        try:
            response=await bridge.chat(body,route={'session':'capability-visual-'+name,'role':'teacher','phase':'audit'})
            text=response['choices'][0]['message']['content']
            (OUT/'audit'/f'audit_{name}.md').write_text(text+'\n')
            manifest.append({'case':name,'completed':True,'original_images':[str(p) for p in images],'copies':copies,'response':response})
        except Exception as e:manifest.append({'case':name,'completed':False,'error':str(e)})
        finally:await bridge.close()
    (OUT/'audit/scene_visual_audit_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps([{k:v for k,v in r.items() if k!='response'} for r in manifest]),flush=True)

asyncio.run(main())
