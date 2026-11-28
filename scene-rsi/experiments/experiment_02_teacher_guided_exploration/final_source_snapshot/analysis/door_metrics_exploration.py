"""Reference-view door measurements using the dataset's explicit instance mapping."""
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_02_teacher_guided_exploration'
OUT=EXP/'analysis/door'


def features(mask):
    y,x=np.nonzero(mask)
    if not len(x):return {'pixels':0,'fraction':0,'centroid_xy':None,'bbox_xy':None}
    h,w=mask.shape
    return {'pixels':int(len(x)),'fraction':float(mask.mean()),
            'centroid_xy':[float((x.mean()+.5)/w),float((y.mean()+.5)/h)],
            'bbox_xy':[float(x.min()/w),float(y.min()/h),float((x.max()+1)/w),float((y.max()+1)/h)]}


def reference_mask():
    OUT.mkdir(parents=True,exist_ok=True)
    config=next(s for s in json.loads((ROOT/'configs/scenes.json').read_text())['scenes'] if s['id']=='S02')
    gt=Path(config['evaluation_directory'])
    metadata=json.loads((gt/'metadata.json').read_text())
    mapping=metadata['instance_map']['object_index_map']
    ids=[int(key) for key,value in mapping.items() if 'paneldoorfactory' in value.lower()]
    labels=np.asarray(Image.open(gt/'instance_segmentation.png').resize((640,360),Image.Resampling.NEAREST))
    mask=np.isin(labels,ids)
    info={'source':str(gt/'metadata.json'),'instance_source':str(gt/'instance_segmentation.png'),
          'matched_ids':ids,'matched_names':{str(i):mapping[str(i)] for i in ids},
          'mapping_reliable':len(ids)==1 and bool(mask.any()),'features':features(mask),
          'scope':'Explicit PanelDoorFactory instance in the provided uint16 segmentation. Nearest-neighbor resize to640x360. Not a global 3D coordinate alignment or hidden-structure metric.'}
    Image.fromarray(mask.astype(np.uint8)*255).save(OUT/'gt_door_mask.png')
    rgb=np.array(Image.open(gt/'color.png').convert('RGB').resize((640,360),Image.Resampling.LANCZOS))
    overlay=rgb.copy();overlay[mask]=(rgb[mask]*.5+np.array([255,30,40])*.5).astype(np.uint8)
    Image.fromarray(overlay).save(OUT/'gt_door_overlay.png')
    (OUT/'reference_mapping.json').write_text(json.dumps(info,indent=2))
    return mask,info


def measure(directory,mask,info):
    path=directory/'door_visible_mask.png'
    if not path.exists():return {'available':False,'reason':'No successfully produced student semantic mask.'}
    visible=np.asarray(Image.open(path).convert('RGB')).mean(axis=2)>128
    amodal=np.asarray(Image.open(directory/'door_amodal_mask.png').convert('RGB')).mean(axis=2)>128
    geometry=json.loads((directory/'geometry.json').read_text())
    names=[obj['name'] for obj in geometry['door_objects']]
    union=np.logical_or(visible,mask).sum()
    reliable=info['mapping_reliable'] and bool(names)
    return {'available':True,'student_door_names':names,'visible':features(visible),'amodal':features(amodal),
            'visible_fraction_of_projected_door':float(visible.sum()/amodal.sum()) if amodal.any() else None,
            'gt_instance_iou':float(np.logical_and(visible,mask).sum()/union) if reliable and union else None,
            'gt_recall':float(np.logical_and(visible,mask).sum()/mask.sum()) if reliable else None,
            'hinges':geometry['hinges'],'openings_and_frames':geometry.get('openings_and_frames',[]),
            'scope':'Student leaf/panel union from actual source-named geometry with emission override. Camera/door edits can both change image overlap. Mask score does not prove hinge/frame plausibility; reference-invisible GT parts are not graded.'}


def main():
    mask,info=reference_mask()
    baseline=measure(EXP/'analysis/baselines/S02/capture/target_geometry',mask,info)
    results=[]
    for run in sorted((EXP/'runs').glob('S02-*')):
        row=measure(run/'analysis/technical/capture/target_geometry',mask,info)
        row['run']=run.name
        if row['available']:
            row['iou_change_from_initial']=row['gt_instance_iou']-baseline['gt_instance_iou'] if row['gt_instance_iou'] is not None and baseline['gt_instance_iou'] is not None else None
        results.append(row)
    (OUT/'metrics.json').write_text(json.dumps({'reference':info,'initial':baseline,'runs':results},indent=2))
    print('GT mapping:',info['matched_names'],'pixels:',info['features']['pixels'],'initial IoU:',baseline.get('gt_instance_iou'))
    for row in results:print(row['run'],row.get('gt_instance_iou'),row.get('iou_change_from_initial'))


if __name__=='__main__':main()
