# Scene RSI Experiment 01：自然重建轨迹分析

报告生成：2026-11-27 13:43:33 UTC；北京时间 2026-11-27 21:43:33。

本次完成了独立工程、真实多模态预检、三个场景各三次独立重建，以及执行结束后的分析。九份源代码均成功再生成场景和渲染；这不是完整 RSI，没有教师、Hint、Skill 学习、持久能力注入、Harness Evolution、Meta Evolution 或微调。

主要观察：在本次探索性标签下，同题策略集合平均 Jaccard 为办公室 **0.937**、卧室 **0.804**、厨房 **0.725**。共同方法并不保证共同视觉质量；重复出现了构图、材质和支撑问题，也实际出现了程序化纹理、几何纹路、层级门轴等互补方法。只有三个任务，不能据此推断统计显著性或基础模型能力上限。

## 1. 工程、SDK 与独立 Harness

工程位置：`/srv/lab-disks/disk2/users/xymo/scene-rsi`。没有覆盖、修改已有 scene 或 hintrsi 实验，没有修改原环境中的包。SDK 直接来自本机最新 trajectory-to-capability 的已验证源码，发布参考为 [hintrsi 8fcb002](https://github.com/i025/hintrsi/commit/8fcb002f2aedbcc249df6a408adf3c456c5ef827)。实际来源路径和逐文件归属见 [source_origin.json](source_origin.json)。

实际链路是：

```text
匿名参考图 + 统一英文任务
  → Claude Agent SDK 保存当前会话
  → 原 LiteLLM Anthropic/OpenAI 转换及 streaming_fix
  → 原 Codex CLI Bridge 返回一个结构化决策
  → SDK 执行 Bash / Read / Write / Edit / Glob / Grep
  → Python / Blender 生成代码、场景及图像
  → SDK Read 返回真实图像 → 下一次模型请求
```

`run_cc_sdk.py` 的学生执行循环直接复用，没有另写 Agent 框架。CLI 每次以 `codex exec --ephemeral` 调用 `gpt-6.1-terra`、low，只输出 SDK 的下一条结构化响应；不通过 CLI 原生 Agent 执行学生工具。CLI 不负责学生会话续接：同一运行内的记忆由 SDK 的完整消息历史维护，每次独立重复则建立全新 SDK 会话、工作区和 home。

保留原系统提示追加、Hint 和持久能力相关接口，但没有提供对应文件、Hook、教师 URL 或知识内容。正式运行显式关闭 SDK 自动 Memory；实际初始化 tools 只有六项、skills 为空，MCP 为空。SDK 自带的通用编码系统提示仍被保留，并不等于完全没有任何 Agent 系统提示。

新建的 Scene Harness 只承担图像输入、文件工具、Blender/Python 环境、保存和被动记录。没有继承 SceneEvolve 的重建 Prompt、Skill、建模/材质函数、相机优化、任务分解、演化 Harness、Memory 或教师反馈。Blender 二进制来自已有 image-to-3d 环境，旧重建 wrapper 没有复用。学生自行选择了建模顺序、材质、相机、渲染和修复方法。

新增/修改代码的完整归属见 `source_origin.json`；SDK 相对 hintrsi 的差异见 `sdk_changes.diff`。正式九次使用的完整源码和配置单独保存在 `source_at_formal_run/`，不依赖事后修改的源码来解释旧结果。

## 2. 冻结配置与一轮的定义

这里一次运行是一个独立的 SDK 解题会话，可以包含多次模型响应、工具调用、渲染和修改；三个重复不是教师迭代轮次，也没有 RSI 外循环。九次使用相同的上限，学生可自行提前结束。

| 配置 | 实际值 |
|---|---|
| 模型 / reasoning effort | `gpt-6.1-terra` / `low`；没有切换模型或配置回退模型 |
| SDK / SDK 内置 CLI | claude-agent-sdk 0.2.186 / Claude Code 2.1.329 |
| 模型后端 CLI | Codex 0.163.0，stateless exec action Bridge |
| Blender | 5.2.2；已有安装只读复用 |
| 工具 | Bash、Read、Write、Edit、Glob、Grep |
| 会话 | 每次全新；不 resume、不继承其他学生结果 |
| 时间 / 请求上限 | 每次学生进程 1500 秒；最多 120 次进入 Bridge 的模型请求 |
| SDK turn 上限 | 120；SDK turn 与模型请求数分开记录 |
| 上下文 | SDK 原 400000 自动压缩窗口；CLI catalog context_window 500000；本次未发生上下文压缩 |
| CPU / 并行 | 每个学生 8 个逻辑 CPU、nice 15；两路并行，分别使用 32–39、40–47 |
| 内存 | 学生每进程地址空间上限 32 GiB；没有修改共享服务器全局配置 |
| GPU | 本机驱动不可用；全部采用 CPU，未使用共享 GPU |
| 最终图 | 640×360；输入原图为 1280×720 |
| 模型请求超时 | 正式源代码前端 240 秒；S03-R3 触发过一次 |
| 路径 | 学生仅见 `/app`、匿名 `reference.png`、通用环境；交付 `build.py`、`scene.blend`、`final.png` |

渲染引擎不是 Harness 指定的技术指导；九次学生都自行选择了 Cycles、32 samples、denoising 和 AgX。学生代码中的随机种子也是各自生成策略的一部分，不能冒充实验控制的模型采样种子。CLI 没有提供可核验的模型采样 seed/temperature 控制。

正式提示词见 [formal_prompt.txt](../../configs/formal_prompt.txt)，由用户指定的英文任务和统一资源/交付附录组成，未添加重建技术提示：

```text
Given the reference image, reconstruct the depicted scene as an editable 3D scene in Blender.

You may write and execute Blender Python code, inspect the generated scene, render images, and revise your implementation.

Your objective is to reconstruct the reference scene as faithfully as possible, including visible objects, geometry, spatial relationships, materials, lighting, and camera viewpoint.

Choose your own reconstruction strategy and workflow.

Use the provided reference image and the available Blender environment. Do not retrieve an existing reconstruction or access external reference scene data.

Deliver:

- Executable Blender Python source code.
- The reconstructed .blend scene.
- A final rendered image.

Workspace and resources:
Your writable task workspace is /app. The reference image is also available at /app/reference.png. Blender 5.2.2 is available as blender. Rendering uses CPU only with eight threads. The student time budget is 25 minutes, with at most 120 model requests. Save the executable source entry point as /app/build.py, the editable final scene as /app/scene.blend, and the final rendered image as /app/final.png at 640 x 360 pixels. Keep any other required local source or material resources in /app so the delivered source can reproduce the scene.
```

实际请求审计确认九次都含同一任务文本。SDK 自动附带的新 Git 快照标识、会话 UUID 和临时图片路径会不同，因此不宣称整个序列化请求逐字节相同。全部原始请求、命令、工具定义和图片关联均保留。

## 3. 多模态是否真的工作

原 Bridge 只序列化图像字段，没有把它交给 CLI 的真实视觉入口。本次在原转换流程上增加图像提取和 `--image` 附件，兼容初始 image block、单图 tool_result 的 data URI、多图/文本混合返回；保留 MIME、原消息位置、tool_call_id 和实际返回。原请求不被删改，也未用另一模型的文字描述替代图像。

真实非正式预检中，模型正确读出未写进 Prompt 的随机六字符 **F85CBE**，通过 SDK 写代码并运行 Blender，再用 SDK Read 读取新渲染。它观察到的灰色球体与真实渲染一致，并没有仅根据代码中的 Blue 材料名猜蓝色。另有两路同时运行的不同图像标签测试，均返回各自标签、独立会话，未见串扰。原 Bridge 22 项回归测试及图像关联检查通过。

正式参考 PNG 由 SDK 自身转成真实 JPEG 图像消息，实际视觉输入仍是 **1280×720**。三个场景在各自三次重复中得到相同的 JPEG 内容；相对原图辅助 SSIM 约 0.990–0.993。后续自渲染 Read 返回 PNG，实际进入之后请求的附件列表，和原参考图保持独立的消息/工具关联。三个没有读自渲染的运行是学生自主结束的行为，不是图像通路缺失。

六次运行读过自己渲染，六次调整过相机；S03-R2 还调整三盏面积光。没有要求学生固定渲染次数或强制固定阶段。详细证据见 `preflight/multimodal_validation.json`、`parallel_validation.json`、`memory_validation.json` 和各运行 `bridge/*/image_attachments.json`。

## 4. 数据、真实 GT 与隔离

数据仅来自 [IDEAL-Scenes](https://huggingface.co/datasets/IDEAL-Benchmark/IDEAL-Scenes)，许可 **CC BY 4.0**；[项目主页](https://ideal3d.github.io/)。没有使用它的 Agent 或重建 Harness，也没有使用备用的 Blender 官方场景。

先检查本地数据，再仅下载少量候选元数据/RGB 和选中的三个 Blender 文件，没有下载约 56 GB 的全数据集。每类按字典序优先取满足 5–15 个可见语义物体、至少四类、文件完整且可打开重渲染的第一个场景。选择在学生正式结果产生前冻结；没有按学生表现重选。

| 匿名任务 | 类别 / 真实场景 | 可见物体 / 类别 | GT mesh 数（仅描述） | GT 原图与重渲染辅助 SSIM |
|---|---|---:|---:|---:|
| S01 | office / office_s1210607561 | 7 / 6 | 36 | 0.888 |
| S02 | bedroom / bedroom_s1379154150 | 7 / 5 | 30 | 0.934 |
| S03 | kitchen / kitchen_s1075679984 | 5 / 5 | 30 | 0.937 |

三个 `.blend` 均实际打开，未发现缺失外部纹理。使用其原相机和材质实际重渲染；为了验证成本，重渲染从 1280×720、128 samples 改为 640×360、32 samples、CPU，因此不是像素一致性证明。办公室百叶/噪声等细节差异较大，构图和主要物体保持一致。实际差异见 `gt_validation_metrics.json` 和 `gt_reference_rerender.png`。正式学生和评价比较的参考始终是原始 RGB，而非这次验证图。

每个场景保留 `scene.blend`、`GT.json`、`objects_in_view.json`、`metadata.json`、`color.png`、`instance_segmentation.png`。实例图实际为 1280×720 的 I;16 PNG，三个场景分别含 15、14、11 个实例像素值，含背景/结构，不能直接当语义资产数量。

学生工作区只放匿名参考图。bwrap 建立独立挂载、PID 和网络空间，未挂载 GT、旧工程、其他运行结果或用户 home；仅开放到模型代理的 Unix socket。实测学生访问 GT 目录和 `/home/xymo` 不可达，直接 TCP 返回 network unreachable。SDK 内层 sandbox 被关闭，由外层隔离执行访问限制，不是只靠 Prompt 保密。

隔离属于本机执行边界的实测结果，不是对抗性安全形式证明。模型 CLI 后端仍在宿主信任边界内，凭据只放后端短期文件并在结束后删除；原生工具被关闭且事件中未出现成功的原生工具执行。不能因此宣称 CLI 包装与未来原生 API 在内部行为上完全等价。

## 5. 每次学生实际完成什么

九次均有可执行源码、可打开 `.blend`、640×360 最终图；九次独立再生成全部成功，并且再生成图与交付图 **RGB 逐像素一致**。材质没有缺失外部资源；源码和场景未见用参考图片平面替代整个三维重建。薄叶片等局部平面属于真实部件建模，不能混同为整图贴片伪造。

| 运行 | SDK 秒 | 请求/有用量返回 | 实际建场景并渲染次数 | Read 自渲染次数 | 最终对象数（不作 GT 得分） | 焦距 mm | 参考-最终辅助 SSIM |
|---|---:|---:|---:|---:|---:|---:|---:|
| S01-R1 | 245.7 | 6/6 | 2 | 2 | 616 | 43 | 0.525 |
| S01-R2 | 113.1 | 2/2 | 1 | 0 | 719 | 26 | 0.571 |
| S01-R3 | 169.1 | 5/5 | 2 | 3 | 490 | 24 | 0.556 |
| S02-R1 | 142.8 | 3/3 | 1 | 0 | 102 | 23 | 0.541 |
| S02-R2 | 133.5 | 3/3 | 1 | 0 | 104 | 34 | 0.641 |
| S02-R3 | 148.4 | 4/4 | 2 | 1 | 113 | 27 | 0.673 |
| S03-R1 | 199.3 | 5/5 | 2 | 1 | 206 | 19 | 0.599 |
| S03-R2 | 162.9 | 5/5 | 2 | 2 | 166 | 22 | 0.595 |
| S03-R3 | 430.2 | 7/6 | 2 | 2 | 181 | 20 | 0.592 |

版本检查不计入“建场景并渲染次数”；对象数差异主要反映板条、叶片等分拆，不能用它与 GT mesh 数的差距给质量打分。SDK 秒是实际 SDK 循环测量，不是把模型调用次数乘以估计时间。

- **S01-R1：** 自建连续椅壳、五辐底座、380 个叶片网格、独立地板板条；读图后焦距从 31 调到 43。主要物体可辨认，桌面颜色/纹理、相机与相对比例不同。
- **S01-R2：** 类似椅壳和板条方法，340 个叶片；没有读自渲染，生成后结束；额外建了一个可见前景桌面，门几乎侧向不可见。
- **S01-R3：** 同类曲面椅壳、180 个叶片；修改相机位置、目标和焦距后重渲染并复读图；前景覆盖有所改善，材质与布局仍有差异。
- **S02-R1：** 箱体家具、几何瓷砖缝、两盏带点光源落地灯、手工门轴变换；一次生成后结束，相机在房间之外形成明显外围黑区。
- **S02-R2：** 门板和装饰挂在 Empty 门轴下；增加另一个床状结构解释右前景白色物体；一次生成后结束。与 GT 的语义差异在该截断区域存在单图歧义，未直接计错。
- **S02-R3：** 使用分离的柜体背/侧/层板及门轴层级，读图后把相机拉近；床/门遮挡和材质仍未恢复。
- **S03-R1：** 真实 Noise/ColorRamp 材质、各向异性坐标映射、FONT 时钟和自建叶片；读图后调整相机。
- **S03-R2：** 以细杆几何生成台面纹路，叶片加厚；读图后联合改相机及面积光能量，实际重渲染并复读。
- **S03-R3：** 几何纹路、径向叶片及椭球花苞；一次模型请求超时，经 SDK 同配置重试后继续读图、改相机和重渲染。不能把这段服务等待归为模型建模能力问题。

方法生命周期另外保存在 `analysis/method_lifecycle.json`：区分可见文本中的主张、写入文件的事件、实际执行的程序版本和最终保留的代码/场景。没有可见计划就不补写隐藏推理；例如只声明 random.seed 却没有其他随机调用，不被标成已执行的随机建模。

六次有两次真实场景保存/渲染，三次只有一次。共保留 15 次建场景保存事件。事后打开的 39 份文件状态还包含最终文件副本、`.blend1` 备份和独立再生成，**不是 39 个独立轨迹状态**。没有保存的中间建模过程不可获取。

## 6. 九个同任务配对的相似度

策略标签有实际代码/执行/最终场景证据，集合 Jaccard 不使用代码字符串相似度。序列指标为语义操作序列的 `1 - Levenshtein distance / max_length`，分别报告成功代码中的构建顺序与 SDK 的编辑—执行—看图循环。最终状态指标是语义部件库存 Jaccard，不是坐标误差或完整三维形状距离。

| 同题配对 | 策略 Jaccard | 构建序列 | 工具循环序列 | 最终语义部件状态 |
|---|---:|---:|---:|---:|
| S01-R1 / S01-R2 | 0.905 | 0.692 | 0.333 | 0.923 |
| S01-R1 / S01-R3 | 1.000 | 0.833 | 0.857 | 0.958 |
| S01-R2 / S01-R3 | 0.905 | 0.769 | 0.286 | 0.885 |
| S02-R1 / S02-R2 | 0.867 | 0.833 | 1.000 | 0.870 |
| S02-R1 / S02-R3 | 0.722 | 0.833 | 0.400 | 0.800 |
| S02-R2 / S02-R3 | 0.824 | 0.833 | 0.400 | 0.769 |
| S03-R1 / S03-R2 | 0.652 | 0.600 | 0.714 | 0.857 |
| S03-R1 / S03-R3 | 0.714 | 0.600 | 0.833 | 0.889 |
| S03-R2 / S03-R3 | 0.810 | 0.800 | 0.857 | 0.963 |

源数据：[pairwise_metrics.csv](analysis/pairwise_metrics.csv)、[annotations.json](analysis/annotations.json)。每个标签及操作都有代码行、工具 ID 或场景对象证据。Unknown 明确保留；没有把隐藏思考、未保存状态或未经网格检测的接触当成已知。

办公室 R1/R3 的标签集合虽为 1.000，构建顺序、相机、地板板数、叶片数和图像仍不同。高值只说明本次标签粒度下采用了相同类别的方法。常见箱体、材质、相机和渲染本来就受任务要求约束；不能把所有共同操作都解释为探索不足。

**不计算中间状态轨迹的数值相似度。** 每次只有一到两次整场景保存，数量不齐，且没有可靠的语义状态时间对齐。也没有强行对任意尺度、坐标系的学生场景计算 GT 三维坐标误差。九个配对来自三个任务，不是九个独立任务样本；没有显著性检验或显著性结论。

## 7. 质量、重复缺陷与互补知识

视觉上，九次都恢复了主要场景类型及多种物体，但构图、可见尺寸、遮挡、纹理和局部光照仍有差距。恢复度不是“脚本执行成功”的同义词。辅助 SSIM 仅描述像素外观，受白墙面积、视角和光照影响，不能作为唯一质量标准或冒充人类评分。

实际修订也不是指标单调改善：S01-R1 的参考-渲染辅助 SSIM 从 0.564 变为 0.525，S01-R3 从 0.588 变为 0.556，S02-R3 则从 0.578 变为 0.673。真实前后图保留在 `revision_comparison.png`。控制器没有根据事后分数挑选或恢复“最佳图”，这些数值也不等于人类质量判断。

结构上，实际状态明确显示：办公室三次椅子与地板的正垂直间隙为 **0.015 / 0.0095 / 0.027**；卧室三次床体与地板/地毯的间隙为 **0.0425 / 0.0825 / 0.119**。单位是各学生场景的 Blender 坐标单位，不是 GT 对齐后的米制误差。几何及源码未见补齐间隙的支撑；没有进行动力学仿真。证据见 [support_separation.json](analysis/support_separation.json)。没有用包围盒重叠推断接触或穿插。

办公室三次都缺少参考桌面的暗色木纹；卧室三次地毯均为常量颜色；厨房三次的台面外观和局部日照仍与参考不同。六次自查后的修订集中在相机，另有 S03-R2 光照；没有观察到几何或材质修订。重复缺陷频数、共享缺陷列表见 `pairwise_metrics.json`；这是一位自动化助手的事后观察，不是人类标注。

也有重复的正确细节：办公室门参考为两列四行八块面板，三次都生成八块；厨房三次均有六个灶圈和两个紫色旋钮。重复不应天然等同错误。

互补方法包括厨房的节点噪声材质与几何纹路、时钟文字、叶片厚度与椭球花苞；卧室的手工铰链坐标和父对象门轴。方法不同仍可能都只达到相近的粗恢复水平，是否感知质量等价仍需后续人类评价。

不能把 GT 隐藏部分直接计错。例如卧室右前景 GT 是第二书架，但 RGB 主要露出截断背板，学生用床端板或白色家具解释它存在可辨识性限制，本次没有强行当成确认缺陷。

## 8. 下一阶段值得教师主动探索的问题

完整案例及事实/假设边界在 [CASES_ZH.md](analysis/CASES_ZH.md)：

1. 支撑/接触自查能否纠正椅子和床体的重复悬空？与轮子、底座或床座结构引导分别比较。
2. 相机和门轴/遮挡联合探索，是否优于只改焦距或距离？S02 的层级改进本身没有保证视角恢复。
3. 对材质表面变化，节点纹理和几何纹路各有何收益？学生是否把材料名字当成实际实现？
4. 自渲染观察的诊断是否能扩展到几何与材质，而非主要停留在相机？比较教师干预时必须控制额外调用量和时间。
5. 如何保留已有互补细节而不把单个样本答案固化成“经验”？先做独立测试，再讨论学习和迁移。

本次没有真的注入上述 Hint，没有替学生修改重建，也没有合并学生代码。没有足够证据证明某次学生“明确知道正确方法但完全未执行”或“已证明不会修复”，这两类没有虚构案例补齐。

## 9. 人工评价材料

[离线评价页面](analysis/human_review/index.html) 提供参考图与三次结果、恢复度选择、缺陷描述、改进优先级和结果比较。所有评分为空，页面不自动评分、不上传内容；人类填写后可自行下载 JSON。本次没有人工标注，也没有人类得分。

[最终对照图](analysis/human_review/comparison.png)、`revision_comparison.png`、固定区域裁剪、门部件细节及每次两个额外视角均由真实图像/场景生成。额外视角是事后评价产物，未提供给学生，未覆盖最终交付，不作为 GT 不可见部分必须一致的要求。

## 10. 接入问题、修复与真实限制

- 最初原生 CLI 环境诊断因用户更新要求而作废，独立保留；未算入正式九次。
- SDK 首次预检的 LiteLLM callback 相对路径问题已修复；一次非持久终端中断也保留了真实部分调用，随后采用拥有进程生命周期的持久终端。
- 首次两个正式启动在约一分钟内发现 SDK 默认自动记忆说明，立即停止并保留数据；没有旧 Memory，但不符合显式禁用要求。显式关闭后，实际请求核验无该说明，正式九次统一从新会话开始。
- S03-R3 的前端 240 秒请求超时后，SDK 重试并完成。原 Bridge 未及时终止这个仍运行的 CLI 后端请求，导致一条正式请求没有返回 Token 用量。**九次全部结束后**，已在当前源码加入 235 秒后端超时和最多五秒终止等待，22 项回归与取消测试通过，另一次真实图像/SDK 预检也通过。此修复没有部署到九次正式运行，不会把两种实现混作一组；正式源码快照单独保留。
- S03-R3 的一次后端 stderr 还出现 `collab spawn failed` 诊断。原生工具关闭，事件流没有成功的原生工具执行；未见学生工具绕开 SDK。该诊断仍如实保留，不能把包装后的 CLI 行为宣称与原生 API 完全等价。

其他限制：只研究三个场景各三次；标签粒度和单一自动化分析者会影响重合度，没有人工复核/标注者一致性验证。单图在遮挡、背面、尺度和语义上存在不可辨识性。SDK 会做 JPEG 预处理；会话临时标识、后端缓存和服务延迟不完全可控。未进行全场景网格接触/碰撞求解，也没有足够中间状态计算轨迹级形状距离。CLI 的结构化响应包装、图像附件排序和消息转换与未来原生 API 请求分布并不完全相同；未来换 API 应重新预检，但可以保留上层 SDK、工具、Harness 和记录接口。

完整工程记录：[ENGINEERING_LOG.md](ENGINEERING_LOG.md)。以上限制不改变本次实际交付和测量，但限制了可作出的研究结论。

## 11. 实际调用、Token、时间与资源

正式九次共 **40 次 Bridge 请求**，39 次返回可记录用量；已报告 **910754 输入 + 29871 输出 = 940625 Token**。输入中的 **476800 cached input** 和输出中的 **1973 reasoning output** 都是子集，不能再次相加。一条超时/被终止的正式请求没有完整用量，所以 940625 是已观测总量的下界，不是伪造的精确账单。

正式 SDK 时间相加约 **29.08 分钟**；两路并行的正式批次墙钟 **18.84 分钟**。截止报告生成，从最初准备开始约 **77.4 分钟**，低于建议六小时；原生/SDK 预检、被保存中断的启动与事后评价也在这个墙钟范围内。

| 记录范围 | Bridge 请求 | 有用量记录 | 已报告输入 | 已报告输出 | 缺失用量请求 |
|---|---:|---:|---:|---:|---:|
| 正式九次 | 40 | 39 | 910754 | 29871 | 1 |
| 显式 Memory 修复前的中断启动 | 3 | 1 | 27313 | 119 | 2 |
| SDK 工程预检（含事后修复检查） | 20 | 19 | 178126 | 2240 | 1 |

另有一次被替换的原生 CLI 诊断任务，报告输入 21052、输出 388；这是一项原生任务，其内部模型往返次数不与 Bridge 请求单位混算。把上述已观测用量合计，得到 **1137245 输入 + 32618 输出 = 1169863 Token** 的下界，另有四条 Bridge 请求用量未知。没有把取消请求估成零消耗。

没有使用 Ofox API，本次没有 Ofox 余额扣费记录可报告。Codex CLI 使用现有登录额度；实际美元账单不可从该执行器核验。SDK 的 default_model 别名费用估算不是 Codex 实际扣费，不能拿来声称美元成本。当前控制器对话 Token、服务商后端计算资源也不在执行器可观测范围内。

每次正式学生的进程树抽样 RSS 峰值约 0.94–1.21 GiB，求和可能重复计算共享页；CPU 亲和性、主机负载、逐次进程树资源采样、子进程 OS 计时均保留。两路使用相同八核数及优先级，没有占用 GPU，没有更改共享服务器已有任务或全局环境。独立再生成/额外视角评价使用另一个八核 CPU 集合且 nice 15。

精确逐请求用量及范围说明见 [usage_summary.json](analysis/usage_summary.json)，资源原始记录见各运行 `resources.jsonl` 和 `host_resources.jsonl`。

## 12. 文件与复查入口

- 工程说明：[README.md](../../README.md)。
- 冻结条件：[experiment_01.json](../../configs/experiment_01.json)、[scenes.json](../../configs/scenes.json)、[PROTOCOL.md](PROTOCOL.md)。
- 每次 `runs/Sxx-Rn/` 下：`workspace/` 为学生原始交付，`capture/` 为真实被动记录，`bridge/` 与 `proxy/` 为请求/响应与图片关联，`analysis/` 为事后结果。原始交付没有被评价过程改写。
- 标签、配对、缺陷、案例、图片和用量在实验 `analysis/` 下；人工评价表全部为空。
- 本地大文件和科学证据的索引见 `file_index.json`、`sync_manifest.json`。后端 home、会话密钥、临时运行文件和登录凭据不纳入后续同步清单；未在本次任务自动上传到 GitHub。

本次实现了可复查的自然轨迹实验，尚未证明教师引导、能力学习或跨任务迁移有效，因此没有宣称已经完成 RSI。
