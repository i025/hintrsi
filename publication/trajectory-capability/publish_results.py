"""Prepare a GitHub publication copy; never edit the original research outputs."""
import datetime
import gzip
import io
import json
import os
import re
import shutil
import tarfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path.cwd()
HOME_SOURCE = Path('/srv/lab-disks/disk2/users/xymo')
REPO = ROOT/'publish/hintrsi'
PREFIX = Path('trajectory-to-capability')
META = REPO/'publication/trajectory-capability'
META.mkdir(parents=True, exist_ok=True)
mapping = {}
sources = {}
excluded = []
external = []
paper_payloads = []
for p in (ROOT/'outputs/trajectory_capability_followup_20261126_182329/evidence/related_work').glob('*.txt'):
    text = p.read_text().strip()
    url = 'https://arxiv.org/html/'+p.stem
    replacement = '[OFFICIAL_PAPER_FULLTEXT_NOT_REPUBLISHED; source='+url+']'
    for value in {text, json.dumps(text, ensure_ascii=False)[1:-1], json.dumps(text, ensure_ascii=True)[1:-1]}:
        paper_payloads.append((value.encode(), replacement.encode()))
    for suffix in ['.txt', '.html']: mapping[str(p.with_suffix(suffix))] = url

def excluded_name(p):
    return any(x in {'.git', '.codex', '__pycache__', 'cli_home'} for x in p.parts) or p.name in {'auth.json', '.credentials.json', 'credentials.json', 'ssh_key', 'ssh_key.pub'} or p.name.startswith('.env') or p.suffix in {'.pyc', '.pem', '.key', '.qcow2', '.img', '.sock', '.sqlite'}

for p in sorted((ROOT/'outputs').rglob('*')):
    if not p.is_file(): continue
    if p.is_symlink() or excluded_name(p):
        excluded.append({'source': str(p.relative_to(ROOT)), 'reason': 'runtime, cache, credential filename or symbolic link'})
        continue
    if p.parent.name == 'related_work' and p.suffix in {'.html', '.txt'}:
        excluded.append({'source': str(p.relative_to(ROOT)), 'reason': 'official third-party fulltext cache; retain source URL and our audit instead'})
        continue
    sources[str(p)] = PREFIX/p.relative_to(ROOT)

# Keep every report link useful, without importing the original large Scene bundles.
for p in (ROOT/'outputs').rglob('*.md'):
    for target in re.findall(r'\]\((/[^\n)]+)\)', p.read_text(errors='replace')):
        path = Path(re.sub(r':\d+$', '', target))
        if str(path) in sources or str(path) in mapping: continue
        if any(str(path).startswith(str(HOME_SOURCE/name)+'/') for name in ['hintrsi', 'hint-codex-experiments', 'hint-baseline-run', 'hint-experiment-handoff']): continue
        if path.is_dir() and path.is_relative_to(ROOT):
            mapping[str(path)] = PREFIX/path.relative_to(ROOT)
            continue
        if not path.exists() and path.is_relative_to(ROOT/'outputs'):
            alternate = ROOT/'outputs'/path.relative_to(ROOT/'outputs').parts[0]/path.name
            if str(alternate) in sources:
                mapping[str(path)] = sources[str(alternate)]
                continue
        if path.is_file() and path.stat().st_size <= 4*1024*1024 and not excluded_name(path):
            sources[str(path)] = PREFIX/'references'/path.relative_to(HOME_SOURCE)
        elif target not in [x['source'] for x in external]:
            external.append({'source': target, 'reason': 'Original external Scene archive remains on server; not a newly produced study artifact', 'bytes': path.stat().st_size if path.is_file() else None})
            mapping[str(path)] = Path('publication/trajectory-capability/EXTERNAL_REFERENCES.md')

for source, path in sources.items():
    mapping[source] = Path(str(path)+'.gz') if Path(source).stat().st_size > 4*1024*1024 else path
original_manifest = json.loads((REPO/'publication/file-manifest.json').read_text())
for item in original_manifest:
    source = str(HOME_SOURCE/item['source'])
    mapping[source] = Path(item['uploaded'])
    mapping[str(HOME_SOURCE/'hintrsi'/item['source'])] = Path(item['uploaded'])

patterns = [
    re.compile(rb'(?<![A-Za-z0-9_-])(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,})'),
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}'),
]
def redact(raw):
    count = 0
    for pattern in patterns:
        raw, n = pattern.subn(b'REDACTED_CREDENTIAL', raw); count += n
    raw, n = re.subn(rb'(https?://)[^\s/<>"\x27]{1,100}:[^\s/@<>"\x27]{1,150}@', rb'\1REDACTED_CREDENTIAL@', raw)
    return raw, count+n

def link_target(target, destination):
    raw_path = re.sub(r':\d+$', '', target)
    mapped = mapping.get(raw_path)
    if mapped is None: return target
    if isinstance(mapped, str) and mapped.startswith('https://'): return mapped
    return quote(os.path.relpath(REPO/mapped, destination.parent), safe='/#')

records = []
for index, (source, published) in enumerate(sorted(sources.items()), 1):
    src = Path(source); dest = REPO/mapping[source]
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = src.read_bytes(); redactions = 0; paper_replacements = 0
    if src.suffix == '.tar':
        output = io.BytesIO()
        with tarfile.open(src) as original, tarfile.open(fileobj=output, mode='w') as archive:
            for member in original.getmembers():
                if member.issym() or member.islnk() or excluded_name(Path(member.name)):
                    excluded.append({'source': source+'::'+member.name, 'reason': 'archive runtime/credential/symlink member'}); continue
                if member.isfile():
                    payload, n = redact(original.extractfile(member).read()); redactions += n; member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
                else: archive.addfile(member)
        raw = output.getvalue()
    elif src.suffix not in {'.png', '.jpg', '.jpeg'}:
        raw, redactions = redact(raw)
        # Retain call envelopes/usage and our analyses; do not republish article payloads.
        if src.suffix in {'.txt', '.json', '.jsonl', '.log'}:
            for original, replacement in paper_payloads:
                n = raw.count(original)
                if n: raw = raw.replace(original, replacement); paper_replacements += n
        if src.suffix == '.md':
            text = raw.decode('utf-8')
            text = re.sub(r'\]\((/[^\n)]+)\)', lambda m: ']('+link_target(m[1], dest)+')', text)
            raw = text.encode()
    wrapped = str(dest).endswith('.gz') and not str(src).endswith('.gz')
    if wrapped:
        with dest.open('wb') as stream:
            with gzip.GzipFile(fileobj=stream, mode='wb', mtime=0, compresslevel=6) as z: z.write(raw)
    else: dest.write_bytes(raw)
    if src.stat().st_mode & 0o111 and not wrapped: dest.chmod(0o755)
    records.append({'source': source, 'uploaded': str(dest.relative_to(REPO)), 'source_bytes': src.stat().st_size,
                    'uploaded_bytes': dest.stat().st_size, 'gzip_wrapped': wrapped, 'credential_redactions': redactions,
                    'official_paper_payloads_replaced': paper_replacements})
    if index % 1000 == 0: print(json.dumps({'copied': index, 'total': len(sources)}), flush=True)

(META/'file-manifest.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n')
(META/'excluded-files.json').write_text(json.dumps(excluded, ensure_ascii=False, indent=2)+'\n')
(META/'external-references.json').write_text(json.dumps(external, ensure_ascii=False, indent=2)+'\n')
summary = {'prepared_at_beijing': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
           'files': len(records), 'source_bytes': sum(r['source_bytes'] for r in records),
           'uploaded_bytes': sum(r['uploaded_bytes'] for r in records), 'gzip_wrapped_files': sum(r['gzip_wrapped'] for r in records),
           'credential_redactions': sum(r['credential_redactions'] for r in records),
           'paper_payloads_replaced': sum(r['official_paper_payloads_replaced'] for r in records),
           'excluded_files': len(excluded), 'external_archives_not_duplicated': len(external),
           'original_experiment_outputs_modified': False, 'hash_or_checksum_system_added': False}
(META/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
(META/'EXTERNAL_REFERENCES.md').write_text('# 外部 Scene 原始分包\n\n这些是原 Scene 工程已有分包，保留在服务器，未重新上传为本次实验的新产物。下列路径不是 GitHub 下载链接；成员索引、抽取证据及审阅在本次结果目录内。\n\n'+''.join('- `'+r['source']+'`（'+str(r['bytes'])+' bytes）\n' for r in external))
(META/'README.md').write_text('''# Trajectory-to-Capability 发布说明

本次新增 `trajectory-to-capability/outputs/`，分别保留原六小时封存实验和用户授权续做的扩展实验；没有覆盖服务器原始结果或旧仓库实验。

- 源码、配置、全部能力库、Hint、学生轨迹、补丁、正式成绩、原始失败、模型调用／用量和审计保留在各自原目录结构。
- 大于 4 MiB 的文件追加 `.gz`；`file-manifest.json` 提供每个文件的来源、发布路径、体积与处理记录。使用 `gzip -dk <文件.gz>` 在分析副本中恢复原文件名。程序／JSON 中的旧绝对路径是历史记录，不代表当前运行配置。
- Markdown 的实验内链接已改为仓库相对链接，并指向实际压缩文件；原 Scene 报告引用的小型证据另复制到 `references/`，大型旧分包仅保留外部清单。
- 不发布认证文件、私钥、环境缓存、虚拟机磁盘或运行时套接字。普通数据和归档成员按同一凭据规则处理，仅修改发布副本；没有新增哈希或签名系统。
- 第三方论文全文缓存不重复发布，论文分析与官方来源保留；模型请求中的对应全文段落标注官方 URL，调用封装、请求 ID、Token 和我们的分析保留。服务器的完整原始调用日志不受影响。
- `summary.json` 是本次增量发布体积和处理统计；`external-references.json` 明确原 Scene 大型分包的服务器位置，不伪造下载地址。

本次整理没有重新调用模型、解题或渲染。代码和第三方任务仍遵循各自原始许可，不统一重新授权。
''')
print(json.dumps(summary), flush=True)
shutil.copy2(Path(__file__), META/'publish_results.py')
