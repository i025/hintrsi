### development：全部预定尝试

| 任务 | 组 | 状态 / 轨迹类别 | 正式成功 | F2P | P2P | 补丁字节 | 停止原因 |
|---|---|---|---|---|---|---|---|
| cattrs-partial-structuring-recovery | K1_v1 | complete / 正式全通过 | 1 | 69/69 | 7/7 | 9329 | end_turn |
| cattrs-partial-structuring-recovery | K2_v1 | complete / 正式全通过 | 1 | 69/69 | 7/7 | 8382 | end_turn |
| aiomonitor-task-snapshots-diff | K2_v1 | complete / 部分通过、未全解 | 0 | 52/53 | 8/8 | 17299 | end_turn |
| aiomonitor-task-snapshots-diff | K1_v1 | complete / 部分通过、未全解 | 0 | 52/53 | 8/8 | 16797 | end_turn |

| 任务 / 组 | 请求 / 已报用量 | 工具请求 / 返回 | 输入 / 输出 / 缓存输入 | 墙钟 / SDK / 正式评测秒 | 学生实际执行秒 / 端到端秒 |
|---|---|---|---|---|---|
| cattrs-partial-structuring-recovery / K1_v1 | 21 / 21 | 47 / 47 | 1236551 / 6356 / 254464 | 1916.335 / 1646.343 / 46.84589984299964 | 1690.789 / 1916.335 |
| cattrs-partial-structuring-recovery / K2_v1 | 23 / 23 | 45 / 45 | 1375248 / 5284 / 277376 | 1387.372 / 1130.911 / 48.80020839700228 | 1168.535 / 1387.372 |
| aiomonitor-task-snapshots-diff / K2_v1 | 13 / 13 | 24 / 24 | 866556 / 6013 / 215680 | 763.203 / 487.714 / 54.67901903500024 | 526.964 / 763.203 |
| aiomonitor-task-snapshots-diff / K1_v1 | 13 / 13 | 27 / 27 | 974955 / 6418 / 339968 | 762.188 / 494.767 / 54.3469738900003 | 532.063 / 762.188 |

### selection：全部预定尝试

| 任务 | 组 | 状态 / 轨迹类别 | 正式成功 | F2P | P2P | 补丁字节 | 停止原因 |
|---|---|---|---|---|---|---|---|
| mashumaro-flattened-dataclass-fields | K1_v1 | complete / 统一上限补评完成 | 1 | 66/66 | 30014/30014 | 9373 | end_turn |
| mashumaro-flattened-dataclass-fields | K2_v2 | complete / 部分通过、未全解 | 0 | 66/66 | 30013/30014 | 9631 | end_turn |
| mashumaro-flattened-dataclass-fields | B0 | complete / 正式全通过 | 1 | 66/66 | 30014/30014 | 9934 | end_turn |
| mashumaro-flattened-dataclass-fields | K1_v2 | complete / 正式全通过 | 1 | 66/66 | 30014/30014 | 8719 | end_turn |
| mashumaro-flattened-dataclass-fields | K0_v1 | complete / 部分通过、未全解 | 0 | 66/66 | 30013/30014 | 9293 | end_turn |
| mashumaro-flattened-dataclass-fields | K0_v2 | complete / 正式全通过 | 1 | 66/66 | 30014/30014 | 8723 | end_turn |
| mashumaro-flattened-dataclass-fields | K2_v1 | complete / 正式全通过 | 1 | 66/66 | 30014/30014 | 9949 | end_turn |

| 任务 / 组 | 请求 / 已报用量 | 工具请求 / 返回 | 输入 / 输出 / 缓存输入 | 墙钟 / SDK / 正式评测秒 | 学生实际执行秒 / 端到端秒 |
|---|---|---|---|---|---|
| mashumaro-flattened-dataclass-fields / K1_v1 | 21 / 21 | 28 / 28 | 1245906 / 6839 / 297088 | 1682.79 / 584.754 / 1427.1788096160017 | 621.41 / 12277.35 |
| mashumaro-flattened-dataclass-fields / K2_v2 | 39 / 39 | 70 / 70 | 2404198 / 8926 / 232320 | 2640.389 / 911.287 / 1530.8230551369998 | 945.613 / 2640.389 |
| mashumaro-flattened-dataclass-fields / B0 | 30 / 30 | 39 / 39 | 1849715 / 6797 / 360320 | 2477.235 / 789.251 / 1483.243425503002 | 825.056 / 2477.235 |
| mashumaro-flattened-dataclass-fields / K1_v2 | 24 / 24 | 31 / 31 | 1681410 / 7065 / 529536 | 2391.101 / 670.525 / 1513.4859336350055 | 706.671 / 2391.101 |
| mashumaro-flattened-dataclass-fields / K0_v1 | 25 / 25 | 37 / 37 | 1314914 / 6854 / 156928 | 2541.733 / 651.228 / 1681.9424237659987 | 689.645 / 2541.733 |
| mashumaro-flattened-dataclass-fields / K0_v2 | 15 / 15 | 21 / 21 | 979273 / 4846 / 316544 | 2743.15 / 572.049 / 1912.1729355569987 | 617.105 / 2743.15 |
| mashumaro-flattened-dataclass-fields / K2_v1 | 33 / 33 | 56 / 56 | 1969109 / 7801 / 260096 | 2591.992 / 737.395 / 1633.513158085996 | 777.031 / 2591.992 |

### test：全部预定尝试

| 任务 | 组 | 状态 / 轨迹类别 | 正式成功 | F2P | P2P | 补丁字节 | 停止原因 |
|---|---|---|---|---|---|---|---|
| adaptix-name-mapping-aliases | K1_v2 | complete / 正式全通过 | 1 | 44/44 | 2738/2738 | 11433 | end_turn |
| adaptix-name-mapping-aliases | B0 | complete / 解题预算耗尽、已评测 | 1 | 44/44 | 2738/2738 | 12646 | student_timeout |
| adaptix-name-mapping-aliases | K2_v1 | complete / 正式全通过 | 1 | 44/44 | 2738/2738 | 12020 | end_turn |
| adaptix-name-mapping-aliases | K0_v1 | complete / 正式全通过 | 1 | 44/44 | 2738/2738 | 11816 | end_turn |
| adaptix-name-mapping-aliases | K0_v2 | complete / 正式全通过 | 1 | 44/44 | 2738/2738 | 11827 | end_turn |
| adaptix-name-mapping-aliases | K2_v2 | complete / 正式全通过 | 1 | 44/44 | 2738/2738 | 13020 | end_turn |
| adaptix-name-mapping-aliases | K1_v1 | complete / 正式全通过 | 1 | 44/44 | 2738/2738 | 13175 | end_turn |
| python-statemachine-state-data-scoping | K2_v2 | complete / 空补丁 | 0 | 0/72 | 1285/1286 | 0 | end_turn |
| python-statemachine-state-data-scoping | K0_v1 | complete / 空补丁 | 0 | 0/72 | 1285/1286 | 0 | end_turn |
| python-statemachine-state-data-scoping | K0_v2 | complete / 空补丁 | 0 | 0/72 | 1285/1286 | 0 | end_turn |
| python-statemachine-state-data-scoping | K1_v1 | complete / 部分通过、未全解 | 0 | 69/72 | 1285/1286 | 16185 | end_turn |
| python-statemachine-state-data-scoping | K2_v1 | complete / 空补丁 | 0 | 0/72 | 1285/1286 | 0 | end_turn |
| python-statemachine-state-data-scoping | B0 | complete / 部分通过、未全解 | 0 | 69/72 | 1285/1286 | 16528 | end_turn |
| python-statemachine-state-data-scoping | K1_v2 | complete / 部分通过、未全解 | 0 | 69/72 | 1285/1286 | 14962 | end_turn |

| 任务 / 组 | 请求 / 已报用量 | 工具请求 / 返回 | 输入 / 输出 / 缓存输入 | 墙钟 / SDK / 正式评测秒 | 学生实际执行秒 / 端到端秒 |
|---|---|---|---|---|---|
| adaptix-name-mapping-aliases / K1_v2 | 21 / 21 | 31 / 31 | 1453625 / 5903 / 343040 | 1837.432 / 1122.471 / 503.3864705070009 | 1160.39 / 1837.432 |
| adaptix-name-mapping-aliases / B0 | 28 / 28 | 59 / 58 | 2020669 / 7802 / 280704 | 2843.717 / 缺失 / 470.7193844039939 | 1800.764 / 2843.717 |
| adaptix-name-mapping-aliases / K2_v1 | 19 / 19 | 43 / 43 | 1213764 / 5599 / 220544 | 1477.866 / 808.04 / 464.08585102600046 | 843.978 / 1477.866 |
| adaptix-name-mapping-aliases / K0_v1 | 23 / 23 | 44 / 44 | 1605014 / 6197 / 323072 | 1669.505 / 993.609 / 466.59178242099733 | 1031.102 / 1669.505 |
| adaptix-name-mapping-aliases / K0_v2 | 17 / 17 | 47 / 47 | 1049111 / 5462 / 113408 | 1435.496 / 775.975 / 445.1053032179989 | 815.4 / 1435.496 |
| adaptix-name-mapping-aliases / K2_v2 | 19 / 19 | 30 / 30 | 1138849 / 6321 / 82432 | 1590.682 / 909.937 / 470.4108983959959 | 947.504 / 1590.682 |
| adaptix-name-mapping-aliases / K1_v1 | 17 / 17 | 29 / 29 | 1058550 / 5750 / 71808 | 1429.943 / 761.361 / 455.58817185599764 | 797.483 / 1429.943 |
| python-statemachine-state-data-scoping / K2_v2 | 1 / 1 | 0 / 0 | 27827 / 41 / 0 | 480.789 / 10.617 / 261.4521008779993 | 46.872 / 480.789 |
| python-statemachine-state-data-scoping / K0_v1 | 4 / 4 | 13 / 13 | 191015 / 721 / 4096 | 607.65 / 138.081 / 236.15435520700703 | 175.39 / 607.65 |
| python-statemachine-state-data-scoping / K0_v2 | 6 / 6 | 16 / 16 | 310651 / 1024 / 6144 | 645.21 / 156.218 / 259.26163948599424 | 192.241 / 645.21 |
| python-statemachine-state-data-scoping / K1_v1 | 31 / 31 | 67 / 67 | 3120611 / 8140 / 176128 | 1695.704 / 1234.646 / 233.64795515900187 | 1271.098 / 1695.704 |
| python-statemachine-state-data-scoping / K2_v1 | 5 / 5 | 14 / 14 | 234436 / 728 / 6144 | 603.481 / 123.845 / 255.30956601099751 | 159.265 / 603.481 |
| python-statemachine-state-data-scoping / B0 | 33 / 33 | 62 / 62 | 3379326 / 8204 / 541952 | 2016.643 / 1557.808 / 232.8200900869997 | 1593.239 / 2016.643 |
| python-statemachine-state-data-scoping / K1_v2 | 36 / 36 | 93 / 93 | 3819688 / 9790 / 466560 | 1921.472 / 1485.112 / 214.58204621599725 | 1519.747 / 1921.472 |

### hint_transfer：全部预定尝试

| 任务 | 组 | 状态 / 轨迹类别 | 正式成功 | F2P | P2P | 补丁字节 | 停止原因 |
|---|---|---|---|---|---|---|---|
| python-statemachine-state-data-scoping | HT_Exploration | complete / 部分通过、未全解 | 0 | 69/72 | 1285/1286 | 14250 | end_turn |
| python-statemachine-state-data-scoping | HT_NoHint | complete / 部分通过、未全解 | 0 | 69/72 | 1285/1286 | 15755 | end_turn |
| python-statemachine-state-data-scoping | HT_Error | complete / 部分通过、未全解 | 0 | 69/72 | 1285/1286 | 17853 | end_turn |
| python-statemachine-state-data-scoping | HT_Strategy | complete / 解题预算耗尽、已评测 | 0 | 69/72 | 1285/1286 | 16247 | student_timeout |

| 任务 / 组 | 请求 / 已报用量 | 工具请求 / 返回 | 输入 / 输出 / 缓存输入 | 墙钟 / SDK / 正式评测秒 | 学生实际执行秒 / 端到端秒 |
|---|---|---|---|---|---|
| python-statemachine-state-data-scoping / HT_Exploration | 31 / 31 | 88 / 88 | 3440148 / 8368 / 576000 | 2019.28 / 1564.176 / 217.72446602099808 | 1601.667 / 2019.28 |
| python-statemachine-state-data-scoping / HT_NoHint | 36 / 36 | 94 / 94 | 3885679 / 9358 / 362624 | 2178.254 / 1708.31 / 238.31172741099726 | 1747.521 / 2178.254 |
| python-statemachine-state-data-scoping / HT_Error | 18 / 18 | 82 / 82 | 1905808 / 8062 / 281344 | 1640.912 / 1182.605 / 230.31391317299858 | 1216.569 / 1640.912 |
| python-statemachine-state-data-scoping / HT_Strategy | 28 / 28 | 101 / 100 | 3253549 / 9259 / 485248 | 2313.716 / 缺失 / 229.5217995540006 | 1800.764 / 2313.716 |

### 评价修复、异常与保留记录

| 任务 / 组 | 评价次数 | 额外诊断秒 | 统一上限补评秒 | 记录 |
|---|---|---|---|---|
| mashumaro-flattened-dataclass-fields / K1_v1 | 3 | 912.661 | 1439.114 |  Original Selection evaluation timed out; one bounded identical-patch diagnostic is separately retained. No new student attempt. Diagnostic did not produce complete formal counts; outcome remains unknown. One uniform 3600s evaluation repair is retained separately after the 900s attempt and diagnostic; no additional student. |
| adaptix-name-mapping-aliases / B0 | 1 | 缺失 | 缺失 |  Student stopped at the unchanged 1800s deadline. Original cancellation/technical state preserved; first formal evaluation of the identical saved deadline patch, no additional student or model call. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/runs/capability_followup_v2_test_adaptix-name-mapping-aliases_B0_r1/budget_stop_evaluation.json |
| python-statemachine-state-data-scoping / K2_v2 | 1 | 缺失 | 缺失 |  Premature final response after one model request, zero tool calls and zero-byte patch; no access error was observed. The grader explicitly evaluated pristine base. Its sole P2P failure is the same 60s statistical-distribution timeout as HT_Exploration. Retain original formal0; distinguish empty-patch termination from attempted algorithm implementation and from baseline-associated timeout. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/statemachine_baseline_timeout_diagnosis_zh.md |
| python-statemachine-state-data-scoping / K0_v1 | 1 | 缺失 | 缺失 |  Empty patch after branch creation, repository reads and missing-API reproduction; student explicitly reported no implementation or commit. One local uv setup command timed out, then reproduction succeeded. No forced budget/technical stop is established. Pristine-base grading reproduces the same known statistical-distribution 60s timeout; retain official score. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/posthoc_test_python-statemachine-state-data-scoping_K0_v1.md |
| python-statemachine-state-data-scoping / K0_v2 | 1 | 缺失 | 缺失 |  Normal end_turn after branch creation and issue reproduction, with no implementation or commit and an empty saved patch. No budget stop, permission denial or bridge model error observed. The sole existing-suite failure is the same statistical-test 60s timeout on pristine base; official F2P0/72 and P2P1285/1286 retained. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/posthoc_test_python-statemachine-state-data-scoping_K0_v2.md |
| python-statemachine-state-data-scoping / K1_v1 | 1 | 缺失 | 缺失 |  Normal end_turn with actual implementation, formal F2P69/72. The sole existing-suite failure is the same weighted statistical-distribution 60s timeout observed on pristine base, not established as a new student regression. Official P2P1285/1286 and formal success0 retained. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/posthoc_test_python-statemachine-state-data-scoping_K1_v1.md |
| python-statemachine-state-data-scoping / K2_v1 | 1 | 缺失 | 缺失 |  Normal end_turn after branch creation and missing-API reproduction, 14 tool calls but no source modification or commit, empty patch. No student budget stop or bridge model error. Sole existing-suite failure matches the statistical-distribution 60s timeout on pristine base; official F2P0/72 P2P1285/1286 retained. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/posthoc_test_python-statemachine-state-data-scoping_K2_v1.md |
| python-statemachine-state-data-scoping / B0 | 1 | 缺失 | 缺失 |  Base student completed normally with a real implementation and commit, formal F2P69/72. Sole existing-suite failure is the same statistical-distribution 60s timeout observed on pristine base; no other base-suite failed IDs observed. Official P2P1285/1286 and formal0 retained. Same pass counts as K1v1 and completed HT groups are not evidence of a knowledge-caused benefit. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/posthoc_test_python-statemachine-state-data-scoping_B0.md |
| python-statemachine-state-data-scoping / K1_v2 | 1 | 缺失 | 缺失 |  Normal end_turn with a real implementation, formal F2P69/72. Sole existing-suite failure matches the weighted statistical-distribution 60s timeout on pristine base and other completed runs; no other formal base failure IDs observed. Official P2P1285/1286 and formal0 retained. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/posthoc_test_python-statemachine-state-data-scoping_K1_v2.md |
| python-statemachine-state-data-scoping / HT_Exploration | 1 | 缺失 | 缺失 |  Formal log includes a 60-second pytest timeout in a callback path. Outer verifier completed normally and official scores remain unchanged. Timeout cause and relationship to the single P2P failure are unverified; three F2P behavior mismatches are separately observed. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/posthoc_hint_transfer_python-statemachine-state-data-scoping_HT_Exploration.md Updated pristine-base comparison: the sole P2P failure is the same test_weighted_transitions.py::TestWeightedTransitionsBasic::test_statistical_distribution timeout on unchanged base and this patch. It cannot be attributed directly to student-introduced regression. Root cause remains unverified and formal scores are retained. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/statemachine_baseline_timeout_diagnosis_zh.md |
| python-statemachine-state-data-scoping / HT_NoHint | 1 | 缺失 | 缺失 |  The sole existing-suite failure is the same statistical-distribution 60s timeout observed on pristine base; not established as a student-introduced regression. Official F2P69/72 and P2P1285/1286 retained; separate new-test failures still require posthoc analysis. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/runs/capability_followup_hint_transfer_hint_transfer_python-statemachine-state-data-scoping_HT_NoHint_r1/eval_output/python-statemachine-state-data-scoping/verifier_stdout.log |
| python-statemachine-state-data-scoping / HT_Error | 1 | 缺失 | 缺失 |  Normal end_turn with real implementation, formal F2P69/72. The sole existing-suite failure is the same weighted statistical-distribution 60s timeout observed on pristine base, not established as a student-introduced regression. Official P2P1285/1286 and formal success0 retained. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/posthoc_hint_transfer_python-statemachine-state-data-scoping_HT_Error.md |
| python-statemachine-state-data-scoping / HT_Strategy | 1 | 缺失 | 缺失 |  Student stopped at the unchanged 1800s deadline. Original cancellation/technical state preserved; first formal evaluation of the identical saved deadline patch, no additional student or model call. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/runs/capability_followup_hint_transfer_hint_transfer_python-statemachine-state-data-scoping_HT_Strategy_r1/budget_stop_evaluation.json Student stopped at the 1800s deadline; first formal evaluation of the unchanged exported patch completed with F2P69/72 and P2P1285/1286, formal0. Sole existing-suite failure matches the pristine-base weighted statistical-distribution 60s timeout; local thread-test teardown issues do not establish another formal P2P regression. No student retry or additional solving. Source: /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/posthoc_hint_transfer_python-statemachine-state-data-scoping_HT_Strategy.md |

Input 已包含 Cached Input；两者不相加。SDK 时长、正式评测时长已处于活动墙钟内，也不相加。首个 Selection 的端到端时间另含接入中断与补评等待，原始墙钟不被覆盖。技术中断与缺失正式成绩保持其实际分类。完整逐项路径与字段见 [attempt_metrics.csv](../attempt_metrics.csv)。

### 独立评价诊断：不新增学生

| 运行 | 状态 | 原始reward | F2P | P2P | 墙钟 / 验证器秒 | 新增学生 / 模型调用 |
|---|---|---|---|---|---|---|
| capability_followup_nohint_same_patch_01 | evaluation_timeout | -1.0 | 缺失/缺失 | 缺失/缺失 | 913.327 / 901.3975106149992 | 0 / 0 |
| capability_followup_known_good_control_01 | complete | 1 | 7/7 | 31/31 | 157.562 / 147.04349801399985 | 0 / 0 |

NoHint 的 -1 是超时哨兵，F2P/P2P 缺失，不能改写为普通失败。此表两次诊断不属于29次学生尝试，也不与上表 Selection 的补评成本重复相加。完整记录见 [additional_evaluation_metrics.csv](../additional_evaluation_metrics.csv)。
