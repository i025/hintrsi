"""Insert recorded numeric results into the unchanged CLI-written report template."""
import csv
import datetime
import json
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
rows=json.loads((OUT/'results/attempt_metrics.json').read_text())
usage=json.loads((OUT/'results/actual_usage_summary.json').read_text())
def cell(v):
    if v is None or v=='':return '缺失'
    return str(v).replace('|','\\|').replace('\n',' ')
def ratio(r,p):
    return f"{cell(r.get(p+'_passed'))}/{cell(r.get(p+'_total'))}"
def table(headers,body):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
        ['| '+' | '.join(cell(v) for v in row)+' |' for row in body])
aliases={'superjson-error-stack-serialization':'SuperJSON（Selection）',
    'tomlkit-toml-table-converters':'TOMLKit（Test）','httpx-deterministic-cookie-store':'HTTPX（Test）'}
core=table(['题目','组','状态','正式成功','F2P','P2P','工具调用','模型请求','输入Token','输出Token','缓存输入','墙钟/SDK秒','停止原因'],[
    [aliases[r['task']],r['group'],r['status'],str(r['formal_success'])+('*' if r.get('evaluation_attempts')==2 else ''),ratio(r,'f2p'),ratio(r,'p2p'),
     r['tool_calls_requested'],r['model_requests'],r['input_tokens'],r['output_tokens'],r['cached_input_tokens'],str(r['wall_seconds'])+'/'+str(r['sdk_seconds']),r['stop_reason']] for r in rows])
core+='\n\n墙钟覆盖初始化、SDK、产物收集与正式评价等；SDK秒为原SDK报告时长，两者不相加。`bridge_model_errors`只统计模型桥错误，本地段错误等进程现象另列在CSV与逐案审计中，不能将本地失败自动等同于正式失败。'
if (OUT/'config/evaluation_triage.json').exists():
    core+='\n\n*Selection K2首次缺少新增测试报告，原评分器记0/80、80/116；同一未修改补丁仅一次实际诊断复评生成完整报告80/80、116/116。主表采用首个完整评价，原始结果、路径及诊断成本全部保留，根因仍未知；该格墙钟包含诊断等待与恢复，不能归因为技能效率差异。见 [评测恢复记录]('+str(OUT/'config/evaluation_triage.json')+')。'
extra_rows=list(csv.DictReader((OUT/'extra_attempt_metrics.csv').open()))
extra=table(['额外启动','分类','正式成功','F2P','P2P','CLI调用','输入/输出/缓存','墙钟秒'],[
    [r['group'],r['classification'],r['formal_success'],ratio(r,'f2p'),ratio(r,'p2p'),r['model_calls_with_usage'],
     '/'.join(r[k] for k in ['input_tokens','output_tokens','cached_input_tokens']),r['wall_seconds']] for r in extra_rows])
diagnostic=OUT/'evaluation_diagnostics.csv'
if diagnostic.exists():
    ds=list(csv.DictReader(diagnostic.open()))
    extra+='\n\n固定补丁诊断（没有新增学生或模型作答）：\n\n'+table(['评测调用','分类','结果','F2P','P2P','模型调用','新学生尝试','墙钟秒'],[
        [r['run_name'],r['classification'],r['reward'],ratio(r,'f2p'),ratio(r,'p2p'),r['model_calls'],r['new_student_attempts'],r['wall_seconds']] for r in ds])
    extra+='\n\n诊断01没有找到归档后的补丁，未运行评测；纠正入口后诊断02直接复制原补丁并完成唯一一次实际复评。主表K2墙钟已覆盖恢复等待，上表是其成本拆分，不再相加。'
optional=OUT/'hint_attempt_metrics.csv'
plan=json.loads((OUT/'config/optional_hint_plan.json').read_text())
if optional.exists():
    hint_rows=list(csv.DictReader(optional.open()))
    hint=table(['开发题Hint类型','状态','正式成功','F2P','P2P','学生/教师请求','检查/交付Hint','工具调用','学生输入/输出/缓存','墙钟秒','技术记录'],[
        [r.get('group'),r.get('status'),r.get('formal_success'),ratio(r,'f2p'),ratio(r,'p2p'),str(r.get('model_requests'))+'/'+str(r.get('teacher_model_requests')),
         str(r.get('server_teacher_checks'))+'/'+str(r.get('delivered_hints')),
         r.get('tool_calls_requested'),'/'.join(cell(r.get(k)) for k in ['input_tokens','output_tokens','cached_input_tokens']),r.get('wall_seconds'),
         '评价超时，正式结果未知' if r.get('evaluation_timed_out')=='True' else 'Node堆OOM；正式报告完整' if r.get('evaluation_heap_oom_observed')=='True' else r.get('stop_reason')]
        for r in hint_rows])
    hint+='\n\n实际过程Hint、教师检查、筛选与采用证据见 [Hint探索记录]('+str(OUT/'audit/hint_exploration_analysis.md')+')。这仅是开发题即时效果，不是独立迁移试验。'
    hint_analysis=OUT/'audit/hint_exploration_analysis.md'
    if hint_analysis.exists():hint+='\n\n'+hint_analysis.read_text()
else:
    hint='可选Hint探索状态：'+cell(plan.get('status','not_started'))+'；'+cell(plan.get('skip_reason','尚无已运行的结果，不能声称完成。'))
totals=usage['actual_cli_usage']
accounting='统计快照：'+datetime.datetime.now(datetime.timezone.utc).isoformat()+'。本表统计本次派生CLI调用（含审计、提取、预检、正式学生、额外失败启动及报告撰写）；不包含监控对话自身的编排Token。\n\n'
accounting+=table(['已报告CLI调用','输入Token','输出Token','缓存输入Token（输入子集）','已记录请求','尚未报告用量的请求'],[[
    totals.get('model_calls_with_usage'),totals.get('input_tokens'),totals.get('output_tokens'),totals.get('cached_input_tokens'),
    usage['recorded_bridge_or_native_cli_requests'],len(usage['usage_unreported_requests'])]])
accounting+='\n\n缓存输入不重复计入总输入；未报告用量不填零。实际美元结算费用未知，SDK代理估算费用不作为账单。历史原求解费用单列，不混入本次派生CLI总量。逐会话明细见 [实际用量]('+str(OUT/'results/actual_usage_summary.json')+') 和 [成本分解]('+str(OUT/'results/cost_breakdown.csv')+')。'
resource=OUT/'results/resource_summary.json'
if resource.exists():
    r=json.loads(resource.read_text())
    accounting+='\n\n资源监控快照：'+str(r['samples'])+'次观测，自'+r['first_observation_utc']+'至'+r['last_observation_utc']+'，最大采样间隔'+str(round(r['maximum_gap_seconds'],2))+'秒。本次登记容器采样内存合计峰值'+str(round(r['peak_observed_sum_container_memory_bytes']/1e9,3))+'GB；短时峰值可能未捕获。详见 [资源记录]('+str(resource)+')，宿主负载包含其他用户，不能全部归因本实验。'
cleanup=OUT/'logs/deadline_cleanup.json'
if cleanup.exists():
    accounting+='\n\n六小时截止清理已有实际记录，详见 [截止清理]('+str(cleanup)+') 和 [最终运行核验]('+str(OUT/'results/final_verification.json')+')。仅处理本次实验登记的队列、服务和容器；原有VM、镜像与其他用户任务保留。'
else:
    accounting+='\n\n此为结果报告快照，六小时监控窗口仍未结束；截止清理尚未发生。'
template=OUT/'research_report_zh.template.md'
if not template.exists():
    template.write_text((OUT/'research_report_zh.md').read_text())
text=template.read_text()
for name in ['benchmark/deepswe/run_loop_by_hint.py','benchmark/deepswe/run_one_loop.sh','run_multi_turn_loop.py',
             'run_cc_sdk.py','benchmark/deepswe/eval_deep_swe.py','run_capability_experiments.py','run_hint_exploration.py']:
    text=text.replace('`'+name+'`','['+name+']('+str(OUT/'source'/name)+')')
historical=OUT/'audit/historical_comparison_addendum_zh.md'
if historical.exists():
    text=text.replace('学生中深审 10 个文件、共 913 个事件','学生中深审 17 个文件、共 1210 个事件')
    text=text.replace('另有 107 个学生文件和 100 个教师文件未深审','另有 100 个学生文件和 100 个教师文件未深审')
    text=text.replace('它们未输入知识生成或学生。','它们未输入知识生成或学生。后续E03—E09又补审7条、297个事件，累计冻结后9条、813个事件，同样未反馈学习或学生。')
    marker='## B. 原工程复用、真实条件与工程修复'
    supplemental=historical.read_text().strip()
    supplemental='\n'.join('#'+line if line.startswith('## ') else line for line in supplemental.splitlines())
    text=text.replace(marker,supplemental+'\n\n'+marker)
if cleanup.exists():
    text=text.replace('这不等于六小时监测窗口、可选工作和清理核算已经结束。',
        '可选工作与窗口结束前的清理核算也已结束，实际时间与退出核验见文末。')
if plan.get('status')!='running':text=text.replace('该探索若有结果，也只是开发任务上的即时观察：','该探索的结果只是开发任务上的即时观察：')
repair=OUT/'audit/optional_evaluation_repair_zh.md'
if repair.exists():
    text=text.replace('仅在验证器执行后另存完整 stdout/stderr，不改评分、测试、命令或环境。',
        '核心阶段仅在验证器执行后另存完整 stdout/stderr；后续可选评价的超时包装见下方补充。')
    marker='原 Bridge、评分逻辑、测试定义、工具执行和任务初始化均未重写。'
    text=text.replace(marker,repair.read_text().strip()+'\n\n'+marker)
scene_matrix=OUT/'audit/scene_concern_matrix_zh.md'
if scene_matrix.exists():
    marker='## G. 文献重叠与贡献边界'
    text=text.replace(marker,scene_matrix.read_text().strip()+'\n\n'+marker)
for key,value in [('CORE_RESULTS_TABLE',core),('EXTRA_RESULTS_TABLE',extra),('OPTIONAL_HINT_RESULTS',hint),('FINAL_ACCOUNTING',accounting)]:
    placeholder='<<'+key+'>>'
    if placeholder not in text:raise RuntimeError('Report writer omitted required placeholder '+key)
    text=text.replace(placeholder,value)
(OUT/'research_report_zh.md').write_text(text)
print(json.dumps({'report':str(OUT/'research_report_zh.md'),'characters':len(text),'cleanup_record_present':cleanup.exists()}))
