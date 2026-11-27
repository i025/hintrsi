"""Insert recorded values into the CLI-written final presentation, without analysis."""
import datetime
import json
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
rows=json.loads((OUT/'results/attempt_metrics.json').read_text())
if len(rows)!=29 or any(r['status'] in ('running','not_started') for r in rows):
    raise RuntimeError('All saved attempt cells must have terminal records')

def cell(value):
    if value is None or value=='':return '缺失'
    return str(value).replace('|','\\|').replace('\n',' ')

def ratio(row,name):
    return cell(row.get(name+'_passed'))+'/'+cell(row.get(name+'_total'))

def table(headers,body):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
        ['| '+' | '.join(cell(value) for value in row)+' |' for row in body])

tables=[]
outcomes={'formal_success':'正式全通过','partial_correct_formally_unsolved':'部分通过、未全解',
    'formally_unsolved':'未全解','empty_patch_formally_unsolved':'空补丁',
    'student_budget_exhausted_with_formal_grade':'解题预算耗尽、已评测',
    'budget_exhausted_with_formal_grade':'解题预算耗尽、已评测',
    'evaluation_timeout_incomplete_report':'评测超时、成绩缺失',
    'student_timeout_with_incomplete_formal_evaluation':'解题截止且评测未完成',
    'technical_interruption_with_or_without_observed_grade':'技术中断',
    'technical_incomplete_with_or_without_grade':'技术中断',
    'complete_evaluation_after_uniform_budget_repair':'统一上限补评完成',
    'complete_evaluation_after_same_patch_diagnostic':'同补丁诊断完成'}
for stage in ['development','selection','test','hint_transfer']:
    selected=[r for r in rows if r['stage']==stage]
    tables.append('### '+stage+'：全部预定尝试\n\n'+table(
        ['任务','组','状态 / 轨迹类别','正式成功','F2P','P2P','补丁字节','停止原因'],
        [[r['task'],r['group'],r['status']+' / '+outcomes.get(r['outcome'],r['outcome']),r['formal_success'],
          ratio(r,'f2p'),ratio(r,'p2p'),r['patch_bytes'],r['stop_reason']] for r in selected]))
    tables.append(table(['任务 / 组','请求 / 已报用量','工具请求 / 返回','输入 / 输出 / 缓存输入','墙钟 / SDK / 正式评测秒','学生实际执行秒 / 端到端秒'],
        [[r['task']+' / '+r['group'],str(r['model_requests'])+' / '+str(r['model_calls_with_usage']),
          str(r['tool_calls_requested'])+' / '+str(r['tool_calls_with_returns']),
          ' / '.join(cell(r[k]) for k in ['input_tokens','output_tokens','cached_input_tokens']),
          ' / '.join(cell(r[k]) for k in ['wall_seconds','sdk_seconds','verifier_elapsed_seconds']),
          ' / '.join(cell(r[k]) for k in ['student_execution_seconds','end_to_end_seconds'])] for r in selected]))
exceptions=[r for r in rows if r['notes'] or (isinstance(r['evaluation_attempts'],int) and r['evaluation_attempts']>1) or r['status']!='complete']
tables.append('### 评价修复、异常与保留记录\n\n'+table(
    ['任务 / 组','评价次数','额外诊断秒','统一上限补评秒','记录'],
    [[r['task']+' / '+r['group'],r['evaluation_attempts'],r['diagnostic_evaluation_seconds'],r['uniform_evaluation_repair_seconds'],r['notes']] for r in exceptions]))
tables.append('Input 已包含 Cached Input；两者不相加。SDK 时长、正式评测时长已处于活动墙钟内，也不相加。首个 Selection 的端到端时间另含接入中断与补评等待，原始墙钟不被覆盖。技术中断与缺失正式成绩保持其实际分类。完整逐项路径与字段见 [attempt_metrics.csv]('+str(OUT/'attempt_metrics.csv')+')。')
diagnostics=json.loads((OUT/'results/additional_evaluation_metrics.json').read_text())
tables.append('### 独立评价诊断：不新增学生\n\n'+table(
    ['运行','状态','原始reward','F2P','P2P','墙钟 / 验证器秒','新增学生 / 模型调用'],
    [[r['run_name'],r['status'],r['raw_reward'],ratio(r,'f2p'),ratio(r,'p2p'),
      str(r['wall_seconds'])+' / '+str(r['verifier_elapsed_seconds']),str(r['new_student_attempts'])+' / '+str(r['model_calls'])] for r in diagnostics]))
tables.append('NoHint 的 -1 是超时哨兵，F2P/P2P 缺失，不能改写为普通失败。此表两次诊断不属于29次学生尝试，也不与上表 Selection 的补评成本重复相加。完整记录见 [additional_evaluation_metrics.csv]('+str(OUT/'additional_evaluation_metrics.csv')+')。')
body='\n\n'.join(tables)
(OUT/'results/attempt_tables_zh.md').write_text(body+'\n')
template=OUT/'research_report_zh.template.md'
if not template.exists():template.write_text((OUT/'research_report_zh.md').read_text())
text=template.read_text()
marker='<<ALL_PLANNED_ATTEMPTS_TABLE>>'
if marker not in text:raise RuntimeError('Report writer omitted required table placeholder')
(OUT/'research_report_zh.md').write_text(text.replace(marker,body))
record={'rendered_at_beijing':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    'planned_rows':len(rows),'source':str(OUT/'results/attempt_metrics.json'),'template':str(template)}
(OUT/'results/report_table_render.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
