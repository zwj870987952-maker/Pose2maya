# Pose2maya 第一轮审计修复交接

> 日期：2026-11-02，Asia/Shanghai  
> 项目：`E:\GitHub\Pose2maya`  
> 审计工作区分支：`codex/pose-retarget-refactor`  
> HEAD：`74dcc17f2e46856b707fc80b7ff3098e0f357bd3`  
> 注意：实施代码大多尚未提交，审计对象包含修改文件和未跟踪的新模块；HEAD 本身不代表本轮实施快照。

## 1. 接收任务的 agent 先读这里

用户要求修复第一轮代码审计发现的问题，修完交回原审计 agent 再审。

- 原始功能范围和架构依据：[HANDOFF.md](/E:/GitHub/Pose2maya/HANDOFF.md)。
- 上一轮自述材料：[IMPLEMENTATION_REPORT.md](/E:/GitHub/Pose2maya/IMPLEMENTATION_REPORT.md)。其中“S0–S6 全部完成”等结论没有通过审计，不能作为已验证事实沿用。
- 本文件给出本轮具体缺陷、复现条件、修复顺序和验收门槛，问题编号 `AUD-01` 至 `AUD-18` 在修复和回交时保持不变。
- 本次整理者只新增这份文档，不修改代码。用户将本文件交给执行 agent 后，执行者按任务进行代码修复和验证，不必为普通内部实现选择反复确认。
- 执行前重读适用的 AGENTS.md，检查工作区，保留现有修改。不要 reset/clean 掉尚未提交的新模块和样本。
- 保留已完成的分层、串行队列、轻量核心等基础，修正实际行为；不要用重命名、删测试、放宽断言或只改报告代替修复。
- **先修测试隔离，再运行 Maya 集成测试。** 当前集成测试会复用并删除正式控制器名称，不能在工作场景直接执行。
- 本轮仍聚焦单图、人形、首次配置后应用到原绑定控制器。视频防滑、手指精修、完整网页绑定编辑器和运行时编译不应挤占本轮修复。

文中行号是本次整理时的定位提示，修复后会变化，以函数名和实际代码为准。

## 2. 审计基线与证据边界

审计在普通 Python 环境运行：

```powershell
Set-Location -LiteralPath 'E:\GitHub\Pose2maya'
python -B -m unittest discover -s tests -v
```

输出：`Ran 24 tests ... OK (skipped=3)`，即 **21 项通过、3 项因没有 Maya 环境跳过**。不能写为“24 项真实场景测试全绿”。审计未加载 GPU 权重，也未操作当前 Maya 场景。

另外执行了不写项目文件的合成数据/模拟对象复现，结果如下：

| 观察 | 审计结果 | 证据类型 |
| --- | --- | --- |
| 模型常见 float32 数据经过标准化后 JSON 序列化 | `TypeError: Object of type float32 is not JSON serializable` | 真实数据类型的合成输入 |
| MHR 参考旋转 | 127 项全部是单位四元数；参考重建左脚踝约 `[92.23, 89.79, 0.53] cm` | 当前定义与代码计算 |
| 原生旋转/相机位置的两骨换基样例 | 标准化位置与旋转重建相差 20 cm | 已知真值的合成输入 |
| 仅左上臂旋转 90° 的 FK 输入 | 肩控制器 0°，肘控制器 90° | 隔离映射复现 |
| 注册 45° A/T Pose 校准 | FK 输出完全不变 | 当前计算接口 |
| profile 中修改 control_offsets | 主流程输出完全不变 | 当前计算接口 |
| 末端控制器注册 90° 旋转偏移 | IK Goal 中保留偏移，最终控制器旋转却被覆盖成单位旋转 | 当前计算接口 |
| 连续预览两次再取消 | 只恢复第一次预览，不是原状态 | 内存 FakeCmds，无真实 Maya |
| 提交中途失败且此前没有预览 | 已写通道保留修改，没有回滚 | 内存 FakeCmds，无真实 Maya |
| 预览后提交，再撤销一次 | 恢复到预览状态 | 内存 FakeCmds，无真实 Maya |
| 网页收到现有 runner 结果结构 | `Cannot read properties of undefined (reading 'skeleton')`，下载 href 为 undefined | Node 执行原展示函数，DOM 替身 |
| 客户端提交自定义图片 | 只发送 basename 作为 preset_id，没有图片内容 | 替换 HTTP 请求函数捕获载荷 |
| 第 1 帧提交，第 10 帧收到结果 | 写入第 10 帧 | 替换 HTTP/时间查询/应用对象 |
| 有效 v2 数据经当前公共 reader 再读 | 0 个世界位置，127 个单位旋转 | 当前 reader |
| 非 XYZ 旋转顺序往返 | 五种顺序误差约 13°–35° | 当前纯数学函数 |
| 单位四元数与自身做 0.5 SLERP | 范数为 1.41421356 | 当前纯数学函数 |
| 全部 part_mask 关闭 | 仍输出 RootX_M | 当前计算接口 |
| left_arm 权重设为 0 | 结果与未设权重相同 | 当前计算接口 |
| 三种 root_motion_mode | 输出相同 | 当前计算接口 |
| NaN 局部四元数/零范数参考四元数 | 现有 validate 返回空错误列表 | 当前验证接口 |

这些复现不等于已完成 Maya/GPU 联调。修复者需保留该区分，不能把 FakeCmds 当作真实绑定验收。

## 3. 修复顺序与依赖

| 顺序 | 问题编号 | 工作 | 阶段门槛 |
| --- | --- | --- | --- |
| F0 | AUD-13、AUD-18 | 隔离破坏性测试；更正验收状态，建立逐项修复记录 | 测试不接触已有角色；测试/报告能区分通过、跳过和待验 |
| F1 | AUD-12、AUD-17、AUD-01 | 修数学、数据校验和序列化 | 全部旋转顺序、SLERP、非法输入、真实 NumPy 类型通过 |
| F2 | AUD-02、AUD-03、AUD-11 | 真实参考骨架、坐标语义、legacy/v2 统一读取 | 已知真值及真实 MHR 前向重建一致，v2 往返无信息丢失 |
| F3 | AUD-14、AUD-04 | 角色采集/保存、参考姿态校准、正确 FK 链 | 源校准 Pose 精确映射到目标校准 Pose；隔离上臂旋转不会驱动肘替代肩 |
| F4 | AUD-05、AUD-06、AUD-07 | 目标几何参与 IK，控制器空间/偏移，末端朝向 | 真实目标链长/关节锚点有效；父变换、局部轴和末端旋转验证通过 |
| F5 | AUD-08、AUD-17 | 事务、动画连接、必要通道预检与真实修改报告 | 连续预览、取消、异常、提交与一次撤销可靠；失败不留下半成品 |
| F6 | AUD-15、AUD-16 | 配置开关、部位掩码、根策略和人工接触 | 每项配置行为可观察；接触与可达性一致，冲突能诊断 |
| F7 | AUD-09、AUD-10 | 前后端接口、新图片上传、任务目标/帧保护 | 新图片可从网页及 Maya 完整走通；等待期间切换状态不会误写 |
| F8 | AUD-18 及全部 | 三类真实绑定回归、GPU 流程、文档与回交 | 每个 AUD 有证据；未实测事项保留待验，不再全阶段笼统标绿 |

可以在后续阶段提前写测试，但不要跳过前置正确性就声称下游通过。第一可用里程碑仍是“离线 Pose → 一个真实绑定 → 可校准、预览、取消和打帧”。

## 4. 问题清单：位置、复现、修复与验收

### AUD-01 / P1：真实推理数据不能序列化为 v2 JSON

**位置：**`E:\GitHub\Pose2maya\pose_core\mhr_adapter.py:264–266`，以及 `E:\GitHub\Pose2maya\pipeline\export_standards.py:82`。

**复现：**将 float32 的 `pred_joint_coords`、`pred_global_rots`、`pred_cam_t` 交给 `standardize_mhr_raw`，再对返回字典执行 `json.dumps`，抛出 float32 无法序列化。坐标转换也可能保留 NumPy 标量，不只是 camera 列表。

**修复要求：**在明确的标准化/序列化边界递归转换成 JSON 可表示的 Python 类型，并检查非有限数。检查 bbox、camera、关键点和其他可选字段，不依赖改变模型全局 dtype 规避。

**验收：**float16/float32/float64 与 Python list 输入均可标准化、保存、读回，值/形状一致；NaN/Inf 按契约拒绝而非写入无效 JSON。真实推理任务不得在 v2 导出阶段失败。

### AUD-02 / P1：源参考骨架由单位旋转伪造

**位置：**`E:\GitHub\Pose2maya\pose_core\mhr_adapter.py:63`，`get_authoritative_mhr_skeleton_def`；`E:\GitHub\Pose2maya\mhr_skeleton_def.json`；`E:\GitHub\Pose2maya\dcc_skeleton_builder.py`。

**复现：**读取定义，打印 `rest_rotations` 和 `rest_world_positions[4]`。当前所有参考旋转为 identity，左脚踝重建近似 `[92.23, 89.79, 0.53]`，骨段沿错误局部轴累加。

**修复要求：**从真实 MHR 资产确定零参数/参考状态、完整局部旋转/预旋转与平移，提供可复现的提取或验证工具及来源说明。统一静态定义来源。构建 Maya 预览骨架时正确表达这些变换；若选择新的 jointOrient，必须补齐 Pose 到该轴向的转换，不能直接写源局部旋转。

**验收：**MHR 参考状态与通用 FK 重建的位置和全局朝向有数值比对；目标预览参考骨架形态正确。应用 Pose 不修改参考平移、骨长和 jointOrient；core 模式折叠中间骨骼时正确合并变换。

**资产边界：**缺少 MHR 资产时先完成有真值的合成测试，但不得把 AUD-02 或原 S0 标为真实验证完成。禁止再次用全 identity 或随意 aim 值充作权威参考旋转。

### AUD-03 / P1：位置与旋转换基语义不一致，旧欧拉角仍按轴角读取

**位置：**`E:\GitHub\Pose2maya\pose_core\mhr_adapter.py:156–165、213–250`；`E:\GitHub\Pose2maya\sam_3d_body\models\heads\mhr_head.py:295、336–365`；`E:\GitHub\Pose2maya\pipeline\export_standards.py:131`。

**复现：**模型将关节位置翻转 Y/Z 后输出，而 `joint_global_rots` 保持原生 MHR 旋转。adapter 却把两者都当相机基底处理。用原生 Z 轴 90° 旋转、长度 10 cm 的两骨真值输入，标准化位置在 +Y 10 cm，当前旋转重建在 -Y 10 cm，残差 20 cm。旧字段 `global_rot_axis_angle` 仍被按 Rodrigues 读取，但其历史来源是 `global_rot_euler`。

**修复要求：**沿实际数据流分别定义原始位置、全局旋转、局部旋转和 reference 的基底；记录数学推导，不把证明通用 `P R P^-1` 恒等式当成证明实际输入基底正确。对本项目已知旧欧拉字段按真实编码和顺序迁移，未知格式显式诊断；不要凭三元组大小猜轴角。

**验收：**已知单轴/组合旋转、左右、前后及整体旋转样例的位置/旋转前向重建一致；真实 MHR pose 对照通过。旧/新格式转换后是相同姿态，无根旋转重复应用或遗漏；相机平移不驱动角色根运动。

### AUD-04 / P1：FK 链映射错位，参考姿态校准未参与求解

**位置：**`E:\GitHub\Pose2maya\retarget\ops\fk_chain_op.py:41–90`；`E:\GitHub\Pose2maya\retarget\calibration.py:113`；源链定义位于 `E:\GitHub\Pose2maya\pose_core\mhr_adapter.py`。

**复现：**隔离合成输入中除 MHR 索引 75 的左上臂设为 X 轴 90° 外，旋转均为 identity；AS5 全 FK 输出 `FKShoulder_L=0°`、`FKElbow_L=90°`。源 arm 链包含 chest，而目标 FK controls 从 clavicle 开始，当前索引分块混淆了锚点与可驱动关节。调用 `calibrate_a_pose_to_t_pose('left_arm', 45)` 前后结果完全相同。

**修复要求：**区分链锚点、旋转采样点、可驱动关节和末端。使用源相对校准姿态的旋转增量，映射到目标参考轴与控制器关系；不同关节数按明确的链长参数分配，避免父级旋转重复计算。不再直接拷贝源局部角或按整数索引拼块。

**验收：**源校准 Pose → 目标校准 Pose；独立上臂/前臂/胸部旋转驱动正确部位；A/T Pose、不同轴向和不同脊柱节数通过。校准值变化应可观察，目标参考变换和骨长保持不变。以上隔离合成样例仅用于定位映射，不能反过来替代 AUD-02 的真实参考数据。

### AUD-05 / P1：IK 未使用目标真实链长和锚点，可达性诊断无效

**位置：**`E:\GitHub\Pose2maya\retarget\ops\ik_goals_op.py:60–83`；`E:\GitHub\Pose2maya\retarget\calibration.py:35`；`E:\GitHub\Pose2maya\maya_scripts\rig_inspector.py`。

**复现：**目标长度取 `源长度 × 髋高比`，正常路径的目标髋高固定为 92.4；落点以源肩/髋的绝对位置为起点。当前 `max(0, 源首尾距离−源两段长度和)` 对有效三角形几乎恒为 0，无法检测目标够不够得到。换不同目标骨段比例，没有相应的目标几何参与。

**修复要求：**采集并保存目标参考几何，使用每侧独立上/下段长度、已求解的目标链锚点和骨盆/躯干姿态生成 Goals。伸展率是可选策略，髋高比只用于其适用的骨盆位移。处理最长/最短距离、骨盆补偿与约束冲突；残差针对目标期望与实际求解结果计算。

**验收：**相同源 Pose 在长臂、短臂、左右不对称比例上得到不同且正确的 Goals；覆盖 `|L1−L2|` 和 `L1+L2` 两个可达边界。不可达时有非零残差和明确策略；保持目标骨长，移动/旋转目标实例时结果随实例正确变换。

### AUD-06 / P1：世界目标直接当本地通道写入，控制器偏移不完整

**位置：**`E:\GitHub\Pose2maya\maya_scripts\rig_adapter.py:70–110`；`E:\GitHub\Pose2maya\retarget\calibration.py:62–100`；`E:\GitHub\Pose2maya\dcc_skeleton_builder.py` 的 `apply_pose`。

**复现：**生成的 `target_pos` 标作世界位置，但 WritePlan 原样写本地 tx/ty/tz。最小例：控制器父节点平移 X=100，期望世界 X=50 时，本地应为 -50，当前计划仍写 +50。参考 Pose 的骨盆位移增量约为 0，也可能被直接写到原本 ty=90 的控制器。校准位置偏移目前是固定世界向量，关节旋转后偏移不会随之转动。

**修复要求：**完整定义每个目标 transform 的空间语义。按目标实例与当前控制空间，把骨架/Goal 的完整变换转换为可写控制器局部通道；处理控制器到关节的完整相对变换，而非简单加世界偏移。覆盖 jointOrient、rotateAxis、rotateOrder、offsetParentMatrix、枢轴及场景单位。暂不支持的变换组合必须预检阻断并说明，不静默错误写入。

**验收：**父平移/旋转、控制器离关节的偏移、非零 jointOrient、不同 rotateOrder、空间切换有真值验证；中性输入保留目标校准姿态。旋转关节时控制器偏移方向跟随，目标场景位置不被清零。对负/非均匀缩放明确区分实测支持和可检测但未支持。

### AUD-07 / P1：末端使用局部旋转，且覆盖控制器校准结果

**位置：**`E:\GitHub\Pose2maya\retarget\ops\ik_goals_op.py:87`；`E:\GitHub\Pose2maya\retarget\ops\end_effector_op.py:39–51`。

**复现：**给 IKArm_L 注册 90° 控制器旋转偏移，IK Goal 中的 target_rot 为 90°，后续 EndEffectorOp 又把最终控制器旋转覆盖成单位旋转。另一个样例是只转肩、腕局部旋转为 0，手掌的世界朝向仍应跟随肩；当前仅取腕局部值无法表达。

**修复要求：**由源完整姿态与参考校准得到正确末端全局朝向，经目标骨架及控制器空间适配一次性求出写入值。定义各 Op 对旋转的所有权，不能后续用未校准局部值覆盖最终控制器目标；同步更新诊断 Goals 和实际写入结果。

**验收：**肩/髋旋转、腕/踝独立扭转、非零控制器偏移分别测试位置和旋转。最终控制器、最终关节朝向和诊断 Goal 一致；修正末端朝向不破坏接触位置。

### AUD-08 / P1：预览、取消、异常回滚及单次撤销不可靠

**位置：**`E:\GitHub\Pose2maya\maya_scripts\pose_session.py:30–175`，重点是预览时第 46 行清空备份，以及 commit 异常时第 171 行只调用 cancel。

**复现方法：**使用内存 FakeCmds 或隔离 Maya 测试，初值 `a.tx=1`：

| 步骤 | 当前结果 | 正确结果 |
| --- | --- | --- |
| preview 到 10 → 再 preview 到 20 → cancel | 10 | 1 |
| 直接 commit，a 写到 10 后注入 b 写入异常 | 报 failed，但 a 留在 10 | 所有工具修改回到提交前状态 |
| preview 到 10 → commit → 一次 undo | 10 | 回到用户操作前的 1，并恢复模式/动画修改 |

**修复要求：**建立明确的会话状态机和初始快照；重复预览不覆写原始基准。提交失败独立回滚，不依赖存在预览；恢复结果可检查。处理已有 animCurve、关键帧值/连接和 auto-key，不能只缓存瞬时标量。规划预览覆盖与最终 undo 的关系，避免预览污染撤销基线。恢复时间、选择和临时对象/层；关闭窗口或切目标时有明确清理。

**验收：**上述三例、切时间后取消、同通道已有关键帧、锁定/受驱动通道、中途异常、预览后换目标、auto-key 开启等均有测试。失败/取消不留半成品；提交只对真实修改属性及必要模式属性打帧；一次撤销覆盖整个用户应用动作，且不清空既有 undo 队列。必须增加真实 Maya 集成证据，不能只用 FakeCmds 宣称完成。

### AUD-09 / P1：异步 API 结果与网页展示协议不匹配

**位置：**`E:\GitHub\Pose2maya\webui\app.py:171–183`；`E:\GitHub\Pose2maya\webui\templates\index.html:401、414–454`；`E:\GitHub\Pose2maya\sam3d_cli.py` 的结果字典。

**复现：**前端调用 `displayResults(pollData.result)`，但 runner result 只有本地 `skeleton_json`、`raw_npz` 等路径。接口把 skeleton 放在外层；旧展示函数还需要 json_url、npz_url、multiview_url 和耗时。以实际 runner 字段执行原展示函数会抛读取 undefined.skeleton，下载 href 也是 undefined。

**修复要求：**统一并文档化任务结果 DTO，提供适当的数据和可访问 URL；不将本地路径当浏览器 URL。让前端支持预览/导出未生成的情况。检查非 2xx 轮询、未知任务和错误状态，避免无限轮询。状态切换和结果发布应一致，不能看到 succeeded 却没有可用 result。

**验收：**Flask 测试客户端与前端契约测试使用一致 DTO；无权重时可用 fake runner 返回完整合成 Pose 验证。实际网页完成骨架渲染、JSON 预览、文件下载；可选输出未生成时按钮状态正确，无 undefined/404/控制台错误。真实图片流程单独实测。

### AUD-10 / P1：Maya 客户端不上传新图片，异步应用缺少状态保护

**位置：**`E:\GitHub\Pose2maya\maya_scripts\service_client.py:55–65、112–116`；`E:\GitHub\Pose2maya\pose_retarget_ui.py`。

**复现：**捕获 URL 请求，输入任意本地 `my_custom_photo.jpg`，请求只包含 `preset_id=my_custom_photo.jpg`，并未读取文件。服务端会去内置预设目录寻找。用替换 HTTP/时间查询/retargeter 的模拟：第 1 帧提交、完成时第 10 帧，实际写入第 10 帧；start_frame 没有作为保护条件。

**修复要求：**使用图片上传协议传递真实文件内容，不把本地路径/文件名冒充预设。明确图片格式、原图 bbox 语义、错误和超时。任务绑定角色实例、配置和指定帧；应用前校验场景/角色/配置是否变化，按明确策略中止或准备原目标预览，不无条件写当前帧。异步完成走相同的角色配置与预览/提交流程，不旁路硬编码入口。补齐 Maya 图片选择/裁切入口。

**验收：**服务预设目录不存在的图片仍可成功推理；覆盖中文/空格路径和支持的大小写扩展名。等待时切帧、切角色、重命名、删除目标、加载另一场景或改配置，都不会误写。网络在后台，所有 Maya 查询/写入在主线程；完成后先显示正确目标的可审查结果。

### AUD-11 / P1：v2 文件导出了，但应用入口仍当 legacy 读取

**位置：**`E:\GitHub\Pose2maya\pose_retarget_ui.py:122`；`E:\GitHub\Pose2maya\pose_retargeter.py` 的 `retarget_pose`；`E:\GitHub\Pose2maya\dcc_skeleton_builder.py` 的 `apply_pose`；`E:\GitHub\Pose2maya\pose_core\mhr_adapter.py:97–193`。

**复现：**把有效 `PoseSample.to_dict()` 传给 `load_legacy_skeleton_json`，得到 0 个世界位置和 127 个补齐的 identity 旋转。当前入口没有根据 schema_version 分派，有可能成功写出零旋转而不报错。

**修复要求：**建立统一读取/分派入口，明确支持的 v2 与已知 legacy 格式；校验版本、skeleton_id、字段和数量。只有已知缺省策略才能补数据，不能用 127 个 identity 掩盖解析失败。v2 文件、v2 dict、已构造 PoseSample、legacy 文件/dict 统一经过相同验证；服务/API 也使用权威 v2。

**验收：**同一姿态经所有支持入口得到等价结果；保存再读取保留旋转、根部、位置、bbox、相机。未知版本/损坏内容在任何场景写入前失败；纯四元数合法 Pose 可根据定义重建必需位置，不依赖偶然存在诊断字段。

### AUD-12 / P1：欧拉角顺序和 SLERP 数学错误

**位置：**`E:\GitHub\Pose2maya\pose_core\math3d.py:196–224、324–370`。

**复现：**对 `[20,-35,50]` 做 `euler_to_q → q_to_euler_deg → euler_to_q`。XYZ 为 0°，yzx/zxy/xzy/yxz/zyx 当前误差约 18.94°/35.12°/20.05°/13.36°/33.27°。SLERP 使用三维 `v_dot`，漏掉 w；identity 与自身插值 0.5 的范数为 sqrt(2)。

**修复要求：**实现六种实际支持的旋转顺序，写清内/外禀及与 Maya 的对应关系，不用 XYZ 回退冒充其他顺序。SLERP 使用四维点积、单位化、最短路径和数值边界处理。

**验收：**六顺序、多组确定性及随机角、近万向节锁、q 与 -q、相同/近似四元数通过。比对独立参考实现或 Maya，而不只用同一套正反函数互证。插值始终输出单位四元数，端点与插值角符合预期；对异常输入有明确策略。

### AUD-13 / P1：Maya 测试会修改并删除现有正式控制器

**位置：**`E:\GitHub\Pose2maya\tests\test_maya_integration.py:65–74、107–109`。

**复现/代码证据：**测试只在 RootX_M、IKArm_L 等不存在时创建；存在就直接修改；清理无条件删除这些名称。若工作场景已有 AS5 同名节点，就会被修改和删除。**不要为了复现直接在用户工作场景运行。** 可以用 FakeCmds 验证“已存在节点进入删除清单”的分支，真实验证在独立会话进行。

**修复要求：**使用明确隔离的测试 namespace 或独立 mayapy/临时场景，仅清理本测试拥有的节点；tearDown/finally 处理失败路径。不得在当前场景 `file(new=True, force=True)` 以实现隔离，除非用户明确选择可丢弃的独立测试会话。

**验收：**预先放置同名哨兵节点并记录数值/连接，测试前后完全一致；失败注入后临时节点清理，哨兵仍在。测试名称和说明准确区分 transform fixture 与真实控制器绑定，不把空 transform 模拟称为完整 AS5 验收。

### AUD-14 / P1：首次角色映射、校准和保存闭环没有落地

**位置：**`E:\GitHub\Pose2maya\pose_retarget_ui.py:76–90、190–310`；`E:\GitHub\Pose2maya\maya_scripts\rig_inspector.py`；`E:\GitHub\Pose2maya\retarget\calibration.py`；`E:\GitHub\Pose2maya\retarget\profiles.py`。

**复现：**UI 只能选三个内置 Python 预设，没有自定义配置载入、映射编辑、参考姿态采集/编辑或保存。calibrator 默认每次新建；RigProfile.control_offsets 没被注册到它；改变该字段主路径结果不变。只存在校准函数不等于用户流程已接通。

**修复要求：**实现选角色根/实例 → 映射候选 → 人工修正 → 源目标校准 Pose/控制器关系采集 → 保存/加载 → 实际求解的完整流程。profile 包含实际目标参考几何、轴向和能力，namespace 在实例绑定时解析；检测歧义。预设 JSON 与 Python 构造器不能成为两个互不相干的权威源。

**验收：**至少一个非内置命名的绑定通过保存配置、重启/重新加载后得到相同结果；更改校准参数能改变对应部位；首次配置后不改源码即可重复应用图片/Pose。配置包含哪些场景依赖要明确记录。

### AUD-15 / P2：权重、部位掩码、根运动策略及当前 Pose 状态存在空转

**位置：**`E:\GitHub\Pose2maya\pose_core\schema.py:195–217`；`E:\GitHub\Pose2maya\retarget\engine.py:81–89`；`E:\GitHub\Pose2maya\retarget\ops\pelvis_op.py:57–67`；`E:\GitHub\Pose2maya\pose_retarget_ui.py:179–181`。

**复现：**left_arm 权重为 0 与默认输出相同；全部 part_mask 关闭仍输出 RootX_M；三个 root_motion_mode 分支给出相同目标。Preview 按钮固定预览样例 1，不是当前载入的 Pose。UE5/HIK 纯 FK 预设若保留 UI 默认 IK，四肢可能被跳过而仍显示成功。

**修复要求：**把配置应用到引擎和实际链能力；禁用部位/零权重的写入和模式切换遵守清楚的语义，不能直接把整条链归零。区分根位置/朝向/骨盆策略；明确骨盆部位开关。UI 保存当前输入/配置/预览状态，预览与提交同一数据。Op 返回失败/依赖缺失要进入诊断，而非忽略。

**验收：**0/0.5/1 权重行为明确；全部关闭时无写入；单臂应用不会无提示修改骨盆和另一侧模式。根运动模式在含平移/旋转的样例上体现区别。纯 FK profile 默认有效，非法 IK 选择明确阻断/转换并提示；自定义 Pose 的预览、取消、提交一致。

### AUD-16 / P2：人工接地只实现了向上防穿地

**位置：**`E:\GitHub\Pose2maya\retarget\ops\ground_contact_op.py:22–42`；`E:\GitHub\Pose2maya\retarget\engine.py:49`；相关 profile/UI。

**复现：**一只脚悬空但选接地，当前 `delta_y > 0` 才执行，脚不会落地；只有全局 bool，不能选择单脚。该 Op 在末端/Pole 计算后直接抬骨盆和两脚，未同步诊断 Goals 或重新检查目标可达性。

**修复要求：**定义人工左脚/右脚/双脚接触目标、高度、权重和优先级，正确区分踝/脚底/控制器偏移。接触目标参与 IK 前的约束准备，必要时有限调整骨盆并重新求解，统一实际输出与诊断。冲突显式报告，不靠隐式 stretch 满足。

**验收：**单脚、双脚、悬空、穿地、不同脚底偏移、不可同时满足的接触条件均验证；检查实际关节/脚底落点与残差。未选择接地的脚不强制贴地。不要把单图接触修正称为已实现视频防滑。

### AUD-17 / P1：结构校验和 Maya 必要通道预检不足

**位置：**`E:\GitHub\Pose2maya\pose_core\schema.py:36–72、112–121`；`E:\GitHub\Pose2maya\retarget\engine.py`；`E:\GitHub\Pose2maya\maya_scripts\rig_adapter.py:57–119`。

**复现：**PoseSample 的 127 个局部四元数含 NaN，validate 仍返回 []；零范数参考旋转也返回 []；主求解路径没有统一执行验证。Maya 预检仅以“至少有一个节点/通道”判断可写，必要 switch 缺失和锁定通道常被警告/跳过，之后仍可能报完整成功。

**修复要求：**在输入、配置、计算和应用边界验证形状、版本、ID、有限性、范数、拓扑及链合法性；不要自动补 identity 隐藏损坏。Maya 预检区分必要/可选节点与属性，检查连接/动画/约束、类型、写入能力、目标实例与实际变化；离线模式不能冒充已写场景。对部分成功有真实报告，并与事务策略一致。

**验收：**NaN/Inf、零四元数、错误长度、非法父索引/循环、错 schema、错 skeleton_id 在写入前失败；必要模式属性缺失、必要通道锁定、歧义节点阻断且零场景修改。可选项缺失明确 partial；零实际修改不报“成功应用 N 通道”。恢复失败不得被吞掉。

### AUD-18 / P1：实施报告和验收状态高于实际证据

**位置：**`E:\GitHub\Pose2maya\IMPLEMENTATION_REPORT.md:63–69、148–175`；`E:\GitHub\Pose2maya\tests\test_maya_integration.py:37–58、63–109`；`E:\GitHub\Pose2maya\README.md`；`E:\GitHub\Pose2maya\HANDOFF.md` 的阶段状态。

**复现/证据：**报告将 S0–S6 全标完成，但真实 GPU 图片流程仍待验；三个配置文件替代了三个真实绑定验收。现有 Maya 事务测试只建少量 transform 与一个 switch 属性，没有真实层级/IK/约束。骨长测试只量 root→pelvis，注释写“跳舞”，实际 apply 仍使用站姿 SAMPLE_JSON，且没有断言 jointOrient 恒定。

**修复要求：**保留上一轮报告作为历史，但加明确更正说明；按实际证据更新阶段状态和 README。补足独立核心数值测试、真实 Maya 绑定与 GPU 完整流程；每一类报告对应真实测试覆盖。性能数据记录脚本/环境/样本，不沿用没有证据的泛化保证。

**验收：**三个不同人形绑定包含真实控制器、层级和求值，并覆盖不同命名/局部轴/比例；纯骨架数学 fixture 单独统计，不能算成三类绑定中的替代证据。全部骨段/参考变换、实际末端旋转/位置、模式、动画及撤销检查有结果。任何外部资产或环境缺口保留待验，不能把“代码有入口”标为整个阶段完成。

## 5. 可直接用于建立回归测试的最小输入

以下代码是文档中的复现材料，整理者没有把它写入源码或测试文件。执行者可在隔离测试中使用并扩展；修后函数名若调整，请更新测试入口并记录。所有示例从项目根目录的普通 Python 执行，不需要打开当前 Maya 场景。

### 5.1 AUD-01：NumPy 类型序列化

```python
import json
import numpy as np
from pose_core.mhr_adapter import standardize_mhr_raw

raw = {
    'pred_joint_coords': np.zeros((127, 3), dtype=np.float32),
    'pred_global_rots': np.tile(np.eye(3, dtype=np.float32), (127, 1, 1)),
    'pred_cam_t': np.array([0, 1, 2], dtype=np.float32),
    'focal_length': np.float32(1000),
}
pose, payload = standardize_mhr_raw(raw)
json.dumps(payload, allow_nan=False)  # 修前 TypeError；修后成功且值可往返
```

### 5.2 AUD-03：位置与原生旋转的两骨真值

```python
import math
from pose_core.schema import SkeletonDefinition
from pose_core.math3d import q_identity, q_from_axis_angle, q_to_mat3, fk_reconstruct, v_dist
from pose_core.mhr_adapter import standardize_mhr_raw

definition = SkeletonDefinition(
    num_joints=2, parent_indices=[-1, 0], joint_names=['root', 'child'],
    rest_translations=[[0, 0, 0], [10, 0, 0]],
    rest_rotations=[q_identity(), q_identity()],
)
native_q = q_from_axis_angle([0, 0, 1], math.pi / 2)
native_r = q_to_mat3(native_q)
raw = {
    # 原生 child 在 +Y 10 cm；模型把 Y/Z 翻转并输出为相机米制位置
    'pred_joint_coords': [[0, 0, 0], [0, -0.1, 0]],
    # 旋转仍保持原生语义，与模型当前数据流一致
    'pred_global_rots': [native_r, native_r],
    'pred_cam_t': [0, 0, 2],
}
pose, _ = standardize_mhr_raw(raw, skeleton_def=definition)
positions, _ = fk_reconstruct(
    definition.parent_indices, definition.rest_translations, pose.local_rotations,
)
print(v_dist(positions[1], pose.world_positions[1]))  # 修前 20；修后应近 0
```

### 5.3 AUD-12：六种旋转顺序及 SLERP

```python
import math
from pose_core.math3d import (
    euler_to_q, q_to_euler_deg, q_angle_between,
    q_identity, q_slerp, q_norm,
)
for order in ['xyz', 'yzx', 'zxy', 'xzy', 'yxz', 'zyx']:
    q = euler_to_q([20, -35, 50], order)
    restored = euler_to_q(q_to_euler_deg(q, order), order)
    print(order, math.degrees(q_angle_between(q, restored)))
print(q_norm(q_slerp(q_identity(), q_identity(), 0.5)))
# 修后：全部角度残差近 0，SLERP 范数近 1。
# 仍需与独立实现/Maya 比对，不能只靠自身往返互证。
```

### 5.4 AUD-11：v2 读取丢数据

```python
from pose_core.mhr_adapter import load_legacy_skeleton_json
pose = load_legacy_skeleton_json('data/sample_poses/01_human_standard_skeleton.json')
read_again = load_legacy_skeleton_json(pose.to_dict())
print(len(read_again.world_positions))  # 修前 0
# 修复应使用统一分派 reader，并验证旋转、根部、bbox、相机均等价。
```

## 6. 回交材料与状态记录

执行 agent 请新增 `E:\GitHub\Pose2maya\REPAIR_REPORT.md`，保留本文件的问题编号，记录本轮与上一轮的区别。不要为了报告擅自提交或改动用户无关文件。

每个 AUD 必须有一行或一个小节，至少包含：

- 状态：**已修并验证 / 已修待真实环境验证 / 部分修复 / 未修**。不是所有问题都能只靠普通 Python 关闭。
- 实际修改位置、方案及与本交接要求的差异。
- 修前失败复现与修后结果，测试命令、退出码、数量和阈值。
- 证据分类：纯数值、mock、API 契约、真实 Maya、真实 GPU；明确跳过与未测项。
- Maya 版本、场景/角色标识、控制器映射、单位和关键变换条件；GPU 环境与图片标识。
- 截图、数值报告或日志位置及可复现步骤。不要将未经授权的角色文件或大权重提交到仓库。

同时提供：

1. 修复前后分支/提交及工作区状态，包括未跟踪文件；如未提交，说明如何获取完整 diff。
2. 修正后的 schema、参考数据来源和 legacy/v2 迁移策略。
3. 三个真实绑定验收矩阵；用 transform fixture 验证的项目单列。
4. 预览/取消/异常回滚/一次撤销及已有关键帧的独立证据。
5. 新图片从 Maya 与网页各走一次完整流程的结果，或具体待验原因。
6. 性能、兼容和已知局限；更新 README 和原报告中不准确的承诺。

本文件状态初始均为未修，不因模块存在或旧测试通过而自动关闭：

| ID | 初始状态 | 关闭至少需要 |
| --- | --- | --- |
| AUD-01 | 未修 | 实际 NumPy 类型 JSON 往返及导出路径测试 |
| AUD-02 | 未修 | 真实 MHR 参考变换提取/重建证据 |
| AUD-03 | 未修 | 合成真值及真实 MHR 坐标一致性 |
| AUD-04 | 未修 | 正确链映射、校准及异构链测试 |
| AUD-05 | 未修 | 真实目标几何、可达边界和残差 |
| AUD-06 | 未修 | 真实 Maya 控制器空间/偏移/局部轴测试 |
| AUD-07 | 未修 | 末端完整朝向与校准不被覆盖 |
| AUD-08 | 未修 | 故障注入与真实 Maya 事务/动画连接测试 |
| AUD-09 | 未修 | API/前端契约及实际页面展示下载 |
| AUD-10 | 未修 | 自定义图片上传和角色/帧/场景保护 |
| AUD-11 | 未修 | 所有入口 legacy/v2 等价及非法输入拒绝 |
| AUD-12 | 未修 | 六顺序独立参考比对、SLERP 单位化和边界 |
| AUD-13 | 未修 | 哨兵不受影响与失败清理 |
| AUD-14 | 未修 | 自定义角色首次配置保存/重载后可重复使用 |
| AUD-15 | 未修 | 权重/掩码/根策略/UI 当前数据行为测试 |
| AUD-16 | 未修 | 单脚/双脚接触、可达性和实际脚底验证 |
| AUD-17 | 未修 | 非法数据及必要通道失败时零场景修改 |
| AUD-18 | 未修 | 报告纠正及真实验证矩阵，待验项如实保留 |

## 7. 给执行 agent 的启动指令

> 请读取 `E:\GitHub\Pose2maya\HANDOFF.md`、`E:\GitHub\Pose2maya\IMPLEMENTATION_REPORT.md` 和 `E:\GitHub\Pose2maya\REPAIR_HANDOFF.md`，按本轮审计的 AUD-01–AUD-18 修复现有实现。先隔离可能删除正式控制器的测试，再按 F0–F8 推进。保留现有工作区，新增能复现问题的回归测试，优先完成数据/数学正确性、真实角色校准、FK/IK 与 Maya 事务，再联调图片入口。不要用空 transform 测试或三个预设文件代替真实绑定验收。完成后提供 `E:\GitHub\Pose2maya\REPAIR_REPORT.md`，逐项列出修复位置、修前/修后证据和真实环境待验项，交回原审计 agent 复审。
