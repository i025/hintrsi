"""Research figures, source provenance and local publication index for teacher baselines."""
import argparse
import datetime
import difflib
import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_03b_teacher_alignment'
SOURCES = ['harness/run_teacher_alignment.py', 'analysis/make_teacher_alignment_review.py',
           'analysis/human_teacher_alignment.py', 'analysis/summarize_teacher_alignment.py',
           'analysis/report_teacher_alignment.py', 'analysis/evaluate_teacher_alignment.py']


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def figures():
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)
    for split in ('development', 'independent'):
        path = EXP / 'configs' / (split + '_cases.json')
        if not path.exists(): continue
        cases = json.loads(path.read_text())
        groups = {}
        for case in cases: groups.setdefault(case['reference_group'], []).append(case)
        columns = max(len(rows) for rows in groups.values()) + 1
        canvas = Image.new('RGB', (columns * 400, len(groups) * 250), 'white')
        draw = ImageDraw.Draw(canvas)
        for i, (group, rows) in enumerate(groups.items()):
            images = [('Reference ' + str(i + 1), Path(rows[0]['seed']) / 'reference.png')]
            images += [(row['anonymous_id'], Path(row['seed']) / 'final.png') for row in rows]
            for j, (label, image) in enumerate(images):
                draw.text((j * 400 + 6, i * 250 + 4), label, fill='black', font=font)
                canvas.paste(Image.open(image).convert('RGB').resize((400, 225), Image.Resampling.LANCZOS), (j * 400, i * 250 + 25))
        canvas.save(EXP / 'analysis' / (split + '_gallery.png'))


def report():
    source = EXP / 'research_analyses/research_reporter/workspace/REPORT_ZH.md'
    usage = json.loads((EXP / 'analysis/usage_summary.json').read_text())
    text = source.read_text()
    text += '\n\n## 报告运行后补记：最终数值账本\n\n'
    text += '本节由控制器在研究报告会话结束后机械补入数值，不更改模型的研究判断。完整原始模型报告保存在research_analyses/research_reporter/workspace/REPORT_ZH.md。\n\n'
    text += f"包含报告会话和工程旧批后，共{len(usage['sessions'])}个已结束/中断SDK会话；已知输入+输出{usage['known_input_plus_output']:,}Token，缺失用量请求{usage['missing_usage_requests']}。缓存输入与推理输出为子集，没有再相加。Ofox调用0，Codex真实美元费用未知。\n\n"
    text += f"从首个模型会话启动到最后一个会话结束的实际时间跨度为{usage['first_to_last_session_wall_seconds'] / 60:.2f}分钟，包括其间离线工作和工程旧批；不含首个模型调用前的全部共同准备。\n\n"
    text += '|范围|会话|请求|有用量返回|会话墙钟秒之和|\n|---|---:|---:|---:|---:|\n'
    for scope, row in usage['scopes'].items():
        text += f"|{scope}|{row['sessions']}|{row['requests']}|{row['usage_records']}|{row['total_session_seconds']:.1f}|\n"
    text += f"\n已知模型会话子进程用户CPU秒{usage['known_child_user_cpu_seconds']:.1f}、系统CPU秒{usage['known_child_system_cpu_seconds']:.1f}；单会话采样RSS加和最大{usage['largest_session_sampled_rss_sum_mib']:.1f}MiB。RSS加和可能重复计共享页；独立再生成另计阶段耗时。会话时间和不是全研究总墙钟。\n"
    (EXP / 'REPORT_ZH.md').write_text(text)
    print('Copied actual SDK research report and appended final numeric ledger.')


def index():
    source_directory = EXP / 'final_source_snapshot'
    origin = []
    source_diff = []
    for name in SOURCES:
        source = ROOT / name
        if not source.exists(): continue
        target = source_directory / name
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
        origin.append({'path': name, 'kind': 'new_scene_teacher_alignment_logic', 'reuse': 'Existing SDK supervisor, original isolation, Experiment02 review/teacher prompt and offline human-form pattern; no replacement Agent loop.'})
        source_diff += difflib.unified_diff([], source.read_text().splitlines(True), fromfile='/dev/null', tofile=name)
    (EXP / 'source_changes.diff').write_text(''.join(source_diff))
    write(EXP / 'source_origin.json', {'recorded_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'new_sources': origin,
          'shared_runtime_sources': ['harness/run_sdk_session.py', 'harness/isolation.py', 'harness/sdk_student.py', 'sdk/codex_cli_bridge.py'],
          'runtime_versions': 'source_at_formal_critic; shared_v2 origins in03-A/infrastructure',
          'prompt_source': 'Experiment02 review format generalized to independent untargeted perceptual evaluation; T1 contains only the explicit user principle.',
          'no_hash_or_checksum_system': True})
    records = []
    excluded = {'.git', '__pycache__', 'home', 'backend_home', 'tmp'}
    for path in sorted(EXP.rglob('*')):
        if path.is_symlink() or not path.is_file() or excluded & set(path.relative_to(EXP).parts): continue
        if path.name in ('sync_manifest.json', 'auth.json') or path.suffix == '.pyc': continue
        records.append({'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size})
    write(EXP / 'sync_manifest.json', {'generated_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'repository': 'https://github.com/i025/hintrsi', 'publication_status': 'local_only_pending_sync',
          'files': records, 'file_count': len(records), 'total_bytes': sum(row['bytes'] for row in records),
          'large_local_assets': [row for row in records if row['bytes'] >= 10 * 1024 ** 2],
          'source_files': origin, 'excluded': ['credentials', 'temporary backend home', 'student home', 'runtime tmp', 'cache', 'workspace Git metadata'],
          'reused_data_in_place': ['Experiment01/02 original workspaces and traces indexed in configs/development_cases.json', 'New reference GT indexed in configs/independent_reference_scenes.json and03-A frozen_split.json'],
          'hashes_or_checksums_added': False})
    print('Indexed', len(records), 'scientific files.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('stage', choices=['figures', 'report', 'index'])
    stage = parser.parse_args().stage
    {'figures': figures, 'report': report, 'index': index}[stage]()
