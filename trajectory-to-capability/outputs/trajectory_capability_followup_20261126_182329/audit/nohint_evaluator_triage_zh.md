## 只读评估分诊

**结论：**同一 NoHint 补丁的 900 秒跟进评估未完成；此前成功的 Error 补丁在当前环境控制中完成并获得记录的通过结果。这说明该评估路线在当前环境下**可以**完成，但不能据此确定 NoHint 超时的根因。

### 观测对比

两次记录均为 verifier 900 秒执行上限、8 GB 内存、同一 VM、评分器和测试；均直接使用原补丁，新增学生尝试和模型调用均为 0。

- **NoHint 同补丁跟进** `capability_followup_nohint_same_patch_01`：补丁 8,635 字节；reward 对象为 `{"reward": -1.0}`，exit code **124**，timeout **true**，verifier 耗时 **901.3975106149992 秒**。F2P、P2P 的总数及通过数均缺失。stdout 记录 `model.patch applied (8635 bytes)`，以及写出 `/logs/verifier/base_backend.xml`、`/logs/verifier/base_frontend.xml`；stderr 为 `Terminated`。这些日志尾部未给出评分结果。`-1` 是超时哨兵，**不是普通算法 reward 0**；此前仅因 reward 非空而标记 complete 的通用检查不能覆盖超时分类。
- **已知成功的 Error 补丁环境控制** `capability_followup_known_good_control_01`：补丁 35,809 字节；reward 对象为 `{"reward":1,"f2p_total":7,"f2p_passed":7,"p2p_total":31,"p2p_passed":31,"f2p":1.0,"p2p":1.0,"partial":1.0}`，exit code **0**，timeout **false**，verifier 耗时 **147.04349801399985 秒**。stdout 记录 `/logs/verifier/new.xml`、`/logs/verifier/base-ctrf.json`、`/logs/verifier/new-ctrf.json`，并显示 `P2P 31/31 pass 0 fail; F2P 7/7 pass 0 fail; PARTIAL 1.0; BINARY 1`。同时 stderr 含 `FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory`；它与最终 exit 0、评分记录并存，其影响不能仅凭这些尾部日志确定。

补丁来源分别为以下实际路径，公共前缀均为 `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/runs/`：
- NoHint：`capability_hint_development_claude-code-by-agents-recursive-delegation_NoHint_r1/infer_logs/claude-code-by-agents-recursive-delegation/turn_1/patch.diff`
- Error：`capability_hint_development_claude-code-by-agents-recursive-delegation_Error_r1/infer_logs/claude-code-by-agents-recursive-delegation/turn_1/patch.diff`

### 边界与未解问题

原始约 600 秒记录应单列：它从容器创建计时；本次 900 秒上限从 exec 开始计时，不能直接当作同一计时基准。NoHint 补丁此后没有再编辑或重试。

尚不知道 NoHint 停在何处、为何超时或完成后会得到什么评分；补丁相关行为、资源或评估过程均只能是假设。控制组的记录也不证明全部场景覆盖，更不证明 NoHint 有代码缺陷。改变学生答案或隐藏测试会改变被比较对象；无限重试会改变实验预算并引入选择偏差，均会破坏本次固定条件研究的可比性。本报告仅使用提供的记录，不更新实验或知识库。
