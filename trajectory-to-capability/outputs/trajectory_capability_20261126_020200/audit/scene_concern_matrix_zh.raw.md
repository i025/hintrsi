### Scene 关注矩阵

| 关注项 | 教师注意到什么 | 诊断／更新 | 学生实际实现 | 已核实结果与限制 |
|---|---|---|---|---|
| 多物体识别／重建 | D01教师称前景植物不可见，无法区分出框与遮挡 | 调整可见性和树冠 | 移动植物父对象并生成叶片［S01，阶段03补丁6–65行］ | 教师称前景可见；阶段05又称植物遮住暖气。独立视觉［SV02］仅见厨房主要家具组，不能证明隐藏物完整 |
| 材质与纹理 | E02教师称木纹不足 | 要求明暗区分和纹理 | M0选定代码有程序化颜色变化；M1有颜色、接缝变化，但无可比的木纹着色器［S03，E02构建代码］ | M1是纹理要求的部分实现，并非质量排名；独立视觉［SV02］见渲染木纹，但比照片更均匀；不能据此评价E02两版 |
| 部件连接 | 教师称E02有黑缝；D01显示器支架接触不清 | 要求面板接合、支架落桌 | E02保留独立框与板；D01改外壳材质和朝向，未移动支架［S03；SG01］ | 黑缝不证明断开。只读几何显示支架包围盒不变；AABB距离为零不证明接触，落桌仍未知［SG01］ |
| 位置／朝向 | E02教师称岛台过小且方向不符，未确定唯一原因 | 联合调整屏幕关系与构图 | M1学生称放大岛台，但台面尺寸未变，摄像机改变［S03，E02 M1步骤001及选定构建］ | 相机可改变投影尺寸而几何不变；目标轮廓和匹配未核实。教师提出诊断本身不证明诊断正确 |
| 相机／光照／渲染 | D01教师称顶边发黑、画面噪声重 | 调相机、材质与灯光 | 学生修改相机和灯光；最终渲染完成［S01，阶段05事件11–13］ | 独立视觉［SV01］仍见深色顶条及颗粒，成因未确定。技术完成不等于视觉质量；H04按规则接受的是H策略，非重建质量保证［S04］ |

**证据边界：**教师／学生描述是各自主张；SV是已有独立二维视觉观察，SG是已有只读几何事实，不能互相替代。既有六幅受审渲染不代表全部 SceneRSI；本矩阵未新增源文件审计，所有覆盖分母不变。S01、S03未报告H/M验收结果；技术完成、规则验收与实际重建质量须分开。

**来源链接图例**（均为实际审计文件）：
- S01：/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_S01.md
- S03：/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_S03.md
- S04：/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_S04.md
- SV01：/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_SV01.md
- SV02：/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_SV02.md
- SG01：/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_SG01.md
