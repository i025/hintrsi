#!/usr/bin/python3
"""Pass through Blender execution and preserve the files it actually produces."""
from pathlib import Path
import difflib
import json
import os
import shutil
import subprocess
import sys
import threading
import time

root = Path(os.environ.get('SCENE_WORKSPACE', '/work'))
capture = Path('/capture') / ('blender_' + str(time.time_ns()))
capture.mkdir(parents=True)
args = sys.argv[1:]
start = time.time()
before = {str(p): (p.stat().st_mtime_ns, p.stat().st_size)
          for p in root.rglob('*') if p.is_file()}
sources = set(root.rglob('*.py'))
for i, arg in enumerate(args):
    if arg in ('--python', '-P') and i + 1 < len(args):
        sources.add(Path(args[i + 1]).resolve())
    if arg == '--python-expr' and i + 1 < len(args):
        (capture / 'python_expr.txt').write_text(args[i + 1])
previous = sorted(Path('/capture').glob('blender_*'))
previous = next((p for p in reversed(previous) if p != capture), None)
for source in sorted(sources):
    if not source.is_file():
        continue
    relative = source.relative_to(root) if root in source.parents else Path('external') / source.name
    target = capture / 'code' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    old = previous / 'code' / relative if previous else None
    old_text = old.read_text() if old and old.exists() else ''
    diff = ''.join(difflib.unified_diff(old_text.splitlines(True), source.read_text().splitlines(True),
                                     fromfile='previous/' + str(relative), tofile=str(relative)))
    target.with_suffix(target.suffix + '.diff').write_text(diff)
(capture / 'command.json').write_text(json.dumps({'argv': args, 'cwd': os.getcwd(), 'started_at': start}, indent=2))
process = subprocess.Popen(['/opt/blender/blender', '--threads', '8', *args],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def relay(stream, target, output):
    with target.open('wb') as saved:
        while True:
            chunk = stream.read1(65536)
            if not chunk:
                break
            saved.write(chunk)
            saved.flush()
            output.buffer.write(chunk)
            output.buffer.flush()


threads = [threading.Thread(target=relay, args=(process.stdout, capture / 'stdout.log', sys.stdout)),
           threading.Thread(target=relay, args=(process.stderr, capture / 'stderr.log', sys.stderr))]
for thread in threads:
    thread.start()
returncode = process.wait()
for thread in threads:
    thread.join()
artifacts = []
for path in sorted(root.rglob('*')):
    if not path.is_file() or path == root / 'reference.png':
        continue
    if path.suffix.lower() not in ('.blend', '.blend1', '.blend2', '.png', '.jpg', '.jpeg', '.exr'):
        continue
    state = (path.stat().st_mtime_ns, path.stat().st_size)
    if before.get(str(path)) == state:
        continue
    relative = path.relative_to(root)
    target = capture / 'artifacts' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    artifacts.append(str(relative))
(capture / 'result.json').write_text(json.dumps({'exit_code': returncode, 'seconds': time.time() - start,
                                                'saved_artifacts': artifacts}, indent=2))
sys.exit(returncode)
