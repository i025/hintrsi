"""Fetch only the seven preselected independent scenes and record their sources."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
DATA = ROOT / 'data/experiment_03/evaluation_gt'
BASE = 'https://huggingface.co/datasets/IDEAL-Benchmark/IDEAL-Scenes/resolve/main/'
API = 'https://huggingface.co/api/datasets/IDEAL-Benchmark/IDEAL-Scenes/tree/main/'
FILES = ['color.png', 'scene.blend', 'GT.json', 'objects_in_view.json',
         'metadata.json', 'instance_segmentation.png']
SCENES = [('A-T01', 'test_a', 'office/office_s1210607562'),
          ('A-T02', 'test_a', 'bedroom/bedroom_s1379154151'),
          ('A-T03', 'test_a', 'kitchen/kitchen_s1256694276'),
          ('A-T04', 'test_a', 'livingroom/livingroom_s1399412440'),
          ('A-S01', 'selection_a', 'diningroom/diningroom_s1627438743'),
          ('B-T01', 'test_b', 'classroom/classroom_s1476231586'),
          ('B-T02', 'test_b', 'meetingroom/meetingroom_s1487880933')]


def fetch(row):
    anonymous, split, scene = row
    folder = DATA / scene
    folder.mkdir(parents=True, exist_ok=True)
    listing = json.load(urlopen(API + scene, timeout=60))
    (folder / 'source_file_listing.json').write_text(json.dumps(listing, indent=2))
    records = []
    for name in FILES:
        path = folder / name
        previous = ROOT / 'data/evaluation_gt' / scene / name
        expected = next(item['size'] for item in listing if item['path'] == scene + '/' + name)
        if path.exists() and path.stat().st_size == expected:
            action = 'reused_experiment_03_download'
        elif previous.exists():
            shutil.copy2(previous, path)
            action = 'reused_local_candidate'
        else:
            with urlopen(BASE + scene + '/' + name + '?download=true', timeout=180) as response, path.open('wb') as output:
                shutil.copyfileobj(response, output, 1024 * 1024)
            action = 'downloaded_required_file'
        records.append({'file': name, 'path': str(path), 'bytes': path.stat().st_size,
                        'source_url': BASE + scene + '/' + name, 'action': action})
    result = {'id': anonymous, 'split': split, 'scene': scene, 'directory': str(folder),
              'reference': str(folder / 'color.png'), 'blend': str(folder / 'scene.blend'),
              'license': 'CC-BY-4.0', 'files': records,
              'selection_basis': 'Preselected by existing unused layout or first dataset-listed scene in a new category; independent of student outcomes.'}
    (folder / 'source.json').write_text(json.dumps(result, indent=2))
    print(anonymous, scene, 'ready', sum(item['bytes'] for item in records), flush=True)
    return result


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as executor:
        rows = list(executor.map(fetch, SCENES))
    manifest = {'prepared_at_utc': datetime.now(timezone.utc).isoformat(),
                'dataset': 'IDEAL-Benchmark/IDEAL-Scenes', 'license': 'CC-BY-4.0',
                'dataset_url': 'https://huggingface.co/datasets/IDEAL-Benchmark/IDEAL-Scenes',
                'selection_rule': 'Reuse three unused local layouts; use first listed complete scene from livingroom, diningroom, classroom, meetingroom. Replace only for completeness or real engineering failures, before student testing.',
                'all_gt_evaluation_only': True, 'scenes': rows}
    (OUT / 'new_scene_candidates.json').write_text(json.dumps(manifest, indent=2))
