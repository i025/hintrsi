# Formal02首轮协议审查

快照：2026-11-22T00:48:02.943804+00:00。只读审查Anko B1、已完成的共享初始指导及H1初始化产物；没有模型调用、源码修改、服务状态操作或哈希验证。

本次核对期间，批次于2026-11-22T00:46:21.761335+00:00因H1 SDK子进程exit -11而停止，H1未正式评测。以下只对已经实际观察到的部分作结论，不能把M/I未执行步骤写成已验证通过。

| 项目 | 实际证据 |
|---|---|
| B1无Hint | 初始配置append_char_count=0、append_text=null；SDK正常completed、is_error=false |
| H初始产物 | 完整Hint与压缩Hint均逐字等于shared原件；原件分别5441、3749字符 |
| M/I初始产物 | 从未进入组初始化，文件未创建，实际相等尚未验证 |
| 按需复制路径 | 每组首次初始化时use_shared复制同一shared完整Hint/压缩Hint/GT；本次没有提前创建M/I文件 |
| SDK会话 | B1与初始教师的SDK会话均不同于Formal01对应会话 |
| Codex线程 | 两批已有完整Token记录中的线程交集为空 |
| 共享成本 | 生成134,091+压缩7,984=142,075Token，各一个Codex turn，归shared仅一次，无分摊行重复计费 |
| M教师保留 | H1准备期间曾只读确认教师容器running、标签Formal02、8CPU/128GiB；批次停止清理后再次查询已删除 |

B1 SDK墙钟665.003秒，ResultMessage耗时653.178秒、27轮，导出补丁11047字节。新学生SDK会话为 `42c5ccdf-63c0-4bb7-a237-ad07a1bacf98`；新初始教师SDK会话为 `fd7a22bb-fbfd-4eba-bc28-8d78aaad436a`，Codex线程为 `01a200b3-33c6-7c01-a4a9-7275020700f5`。

教师state内keep_teacher=false是save_teacher_state明确保存的后续runner默认值，不代表初始教师没有保留。本次先前的只读Docker查询已确认容器运行；后来404与批次停止后的正常清理一致，不应误判为M开始前擅自丢失会话。M复盘尚未执行，不能声称本批已实测续接成功。

M/I没有实际复制文件符合按需初始化顺序。本批因技术中断不能完成三组初始产物逐字一致及M复盘续接的实测核对；已观察范围内未发现协议违规，也不把H1技术未完成记作正常解题失败。

详细ID、路径、容器历史观察与成本见 [审查JSON](formal_02_protocol_audit.json)。原始状态见 [Formal02状态](../runs/codex_formal_02/experiment_state.json)，冻结配置见 [Formal02配置](../reports/formal_02_config.json)，故障日志见 [Formal02日志](../logs/codex_formal_02.log)。

本批实际总量为1,627,587 Token：B1学生1,485,512、共享初始教师134,091、共享压缩7,984。H1在首个模型请求前退出，没有模型请求或Token记录。含正式前预检/联调1,751,919与Formal01的4,709,961，下一批启动前累计已记录8,089,467 Token；不混拼各批成绩。批次停止的详细说明见 [Formal02中断说明](../reports/formal_02_interruption.md)。
