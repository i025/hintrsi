"""Update the audit coverage prose from finished records and a CLI-written addendum."""
import shutil
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
addon=OUT/'audit/historical_comparison_addendum_zh.md'
raw=addon.with_name('historical_comparison_addendum_zh.raw.md')
if not raw.exists():shutil.copy2(addon,raw)
text=raw.read_text().replace(']( /srv/','](/srv/')
text=text.replace('知识队列8人397事件','知识提取队列8条轨迹397事件').replace('冻结后仅审计9人813事件','冻结后仅审计9条轨迹813事件').replace('100名学生未深审','100份学生轨迹文件未深审')
addon.write_text(text)
report=OUT/'audit_hintrsi.md';before=OUT/'audit_hintrsi.before_historical_comparisons.md'
if not before.exists():shutil.copy2(report,before)
text=before.read_text()
text=text.replace('知识冻结后另补审2份Ofox学生记录（516个事件），累计10/117份学生文件、913个事件；另外107份只做轻量索引。',
    '知识冻结后先补审2份Ofox学生记录（516个事件），随后补审7份Claude同题比较记录（297个事件），累计17/117份学生文件、1210个事件；另外100份只做轻量索引。')
text=text.replace('补充的245/271个事件号全部提供给CLI，但单个长字符串截断为1800字符，不能称通读全部原文字节。',
    '9份补审记录的全部事件号均已提供给CLI，但单个长事件字段截断为1800字符，不能称通读全部原文字节；新增7份另行提供捕获提示、最终补丁和正式评价全文。')
text=text.replace('补审E01/E02没有回传学生或用于更新。','全部补审E01–E09均没有回传学生或用于更新。')
report.write_text(text+'\n\n'+addon.read_text())
print('Integrated actual seven-case historical addendum; knowledge files unchanged.')
