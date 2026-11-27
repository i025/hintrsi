"""Two fixed-budget CLI calls, then a recorded length-only delivery transform."""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
PYTHON = '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
parser = argparse.ArgumentParser()
parser.add_argument('name')
args = parser.parse_args()
name = args.name
analysis = OUT / 'knowledge' / (name + '_analysis.md')
delivery = OUT / 'knowledge' / (name + '.md')
if delivery.exists():
    raise FileExistsError(delivery)
record = {'name': name, 'started_at': time.time(), 'model': 'gpt-6.1-terra', 'effort': 'low', 'calls_budget': 2}

def call(suffix, prompt, output):
    code = subprocess.run([PYTHON, '-u', '-B', str(Path(__file__).with_name('model_job.py')),
        'followup-knowledge-' + name + '-' + suffix, str(prompt), str(output)], check=False).returncode
    if code:
        raise RuntimeError('Knowledge extraction call failed; preserve without silent retry')

call('analysis', OUT / 'config' / (name + '_analysis_prompt.txt'), analysis)
generation = OUT / 'config' / (name + '_library_prompt.txt')
generation.write_text('''Convert only the supplied Development analysis into a persistent capability library in English. You may add, revise, delete or merge previous units if the analysis supports doing so. No Selection/Test data or files are available. Return only <persistent_capabilities> ... </persistent_capabilities> containing exactly four Markdown sections headed "## 1. ..." through "## 4. ...". Each unit must include: capability name in heading; Applicable problems; Transferable knowledge/behavior constraint; Candidate methods; Verification steps; When not applicable; Evidence sources. Write 450-650 words total, absolute upper bound 700. Prefer implemention-independent constraints and evidence-bounded verification. Do not include complete task solutions, Golden Patches, task-specific code, hidden tests or concrete benchmark answers. Teacher-only condition must cite Development descriptions and general knowledge rather than invented observations. Distinguish observed behavior from hypotheses, and do not claim causal learning or universal correctness. No introduction or closing prose outside the tags.\nDEVELOPMENT ANALYSIS:\n''' + analysis.read_text())
raw_dir = OUT / 'knowledge/raw_candidates'
raw_dir.mkdir(exist_ok=True)
raw = raw_dir / (name + '.md')
call('library', generation, raw)
content = raw.read_text().strip()
if content.startswith('```'):
    content = re.sub(r'^```[^\n]*\n', '', content)
    content = re.sub(r'\n```$', '', content)
start = content.find('<persistent_capabilities>')
end = content.find('</persistent_capabilities>')
if start < 0 or end < 0:
    raise RuntimeError('Invalid library tags; raw output preserved')
content = content[start:end + len('</persistent_capabilities>')]
sections = re.split(r'(?m)(?=^## \d+\.)', content.replace('<persistent_capabilities>', '').replace('</persistent_capabilities>', '').strip())
sections = [s.strip() for s in sections if s.strip()][:4]
removed = 0
while sections and len(('<persistent_capabilities>\n\n' + '\n\n'.join(sections) + '\n\n</persistent_capabilities>').split()) > 700:
    sections.pop()
    removed += 1
if not sections:
    raise RuntimeError('No deliverable complete unit within common length cap')
delivered = '<persistent_capabilities>\n\n' + '\n\n'.join(sections) + '\n\n</persistent_capabilities>\n'
delivery.write_text(delivered)
record.update(finished_at=time.time(), raw_candidate=str(raw), delivery=str(delivery),
    raw_words=len(raw.read_text().split()), delivered_words=len(delivered.split()),
    delivered_units=len(sections), removed_trailing_units_for_length=removed,
    transform='Strip optional Markdown fence and outer prose; keep first four complete units, drop trailing whole units only if over 700 words. No score-dependent edits.')
(OUT / 'knowledge' / (name + '_delivery.json')).write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record), flush=True)
