"""Read primary full HTML papers once, retaining original pages and numbered text."""
import json
import time
from html.parser import HTMLParser
from pathlib import Path
import requests

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
directory = OUT / 'evidence/related_work'
directory.mkdir(exist_ok=True)
papers = [('SceneEvolve', '2610.37046'), ('Trace2Skill', '2603.25158'),
    ('SKILL-KD', '2607.28048'), ('SkillGen', '2605.10999'),
    ('Socratic_Skill_Learning', '2610.17860'), ('Teaching_the_Harness', '2611.13144'),
    ('DoVer', '2512.06749'), ('GEPA', '2507.19457'), ('SimWorld_Studio', '2605.09423')]

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        if tag in ('p', 'section', 'div', 'h1', 'h2', 'h3', 'h4', 'tr', 'li', 'figure'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
        if tag in ('p', 'section', 'div', 'h1', 'h2', 'h3', 'h4', 'tr', 'li', 'figure'):
            self.parts.append('\n')
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

records = []
for name, identifier in papers:
    row = {'name': name, 'arxiv_id': identifier, 'url': 'https://arxiv.org/html/' + identifier,
        'started_at': time.time()}
    page = directory / (identifier + '.html')
    try:
        if not page.exists():
            response = requests.get(row['url'], timeout=90)
            response.raise_for_status()
            page.write_text(response.text)
            row['resolved_url'] = response.url
        parser = VisibleText()
        parser.feed(page.read_text())
        lines = [' '.join(line.split()) for line in ''.join(parser.parts).splitlines()]
        lines = [line for line in lines if line]
        full_text = '\n'.join(f'{i:05d}: {line}' for i, line in enumerate(lines, 1))
        if len(full_text) < 12000:
            raise RuntimeError('Page too short to establish full paper access')
        text_path = directory / (identifier + '.txt')
        text_path.write_text(full_text + '\n')
        row.update(status='full_html_text_available', characters=len(full_text), text=str(text_path),
            lines=len(lines), extraction='Visible HTML text, including captions/tables where present. Equations/figures may require native page inspection; no replication of claimed results.')
    except Exception as error:
        row.update(status='access_failed', error=str(error))
    row['finished_at'] = time.time()
    records.append(row)
    (OUT / 'config/related_work_fulltext_sources.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps(row), flush=True)
    time.sleep(2)
