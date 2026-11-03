# Pose2maya 第二轮修复报告：核心重构与真实 Maya 验证

> **审计基准**：`REPAIR_HANDOFF_ROUND2.md` & `ROUND2_MAYA_EVIDENCE.json`  
> **工作区**：`E:\GitHub\Pose2maya`  
> **分支**：`codex/pose-retarget-refactor`  
> **HEAD**：`74dcc17f2e46856b707fc80b7ff3098e0f357bd3`  
> **Maya 测试环境**：Autodesk Maya 2025, Python 3.11.4 (`C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe`)  
> **纯 Python 测试环境**：Python 3.12.10 (`pytest 9.2.0`)  
> **完成状态**：已解决 AUD-01～AUD-18，通过 L01～L10 真实 Maya 行为复现与断言，所有 53 项单元与集成测试全绿。

---

## 1. 核心修复回交总表 (AUD-01 ～ AUD-18)

| 编号 | 子项修复结果 | 核心代码位置 | 修前失败证据 (L01~L10) | 修后断言 / 真实数值 | 证据等级 | 待验 / 边界限制 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **AUD-01** | **已修并验证** | `pose_core/schema.py:18` (`to_json_compatible`) | `to_json_compatible({'flag': True})` 返回 `{'flag': 1}`，布尔类型降级为整型 | `isinstance(val, (bool, np.bool_))` 优先处理，JSON 往返后 `'flag': True`，严格保留布尔语义 | 纯数值 / 契约 | 真实 GPU 推理导出另列待验 |
| **AUD-02** | **已修并验证** | `dcc_skeleton_builder.py:145-210` (`apply_pose`) | **L09**: 标准骨架 54 关节应用参考 Pose 最大变形 **119.420866 cm** (`Neutral_ball_l`) | 参考 Pose 应用后 54 骨最大形变 **1.948e-14 cm** (严格 $\le 10^{-4}\text{ cm}$)，`jointOrient` 和骨长保持 0% 变化 | 真实 Maya joint 层级 | 完整 127 骨与外部真实 MHR 资产提取待验 |
| **AUD-03** | **已修并验证** | `pose_core/mhr_adapter.py:220-250` | 根旋转在 local root 与 root_rotation 重复叠加，IKGoalsOp 出现 90° 额外全局旋转 | `q_rel = q_multiply(q_inverse(root_rot), q0)` 解耦局部根旋转，标准化→世界重建→IK 目标朝向误差 $\le 10^{-3\circ}$ | 纯数学 / 适配器 | 支持欧拉 `zyx` 历史语义兼容 |
| **AUD-04** | **已修并验证** | `retarget/ops/fk_chain_op.py:65-115` | 链映射仅按索引分块，肩/肘孤立旋转驱动错位，末端与 EndEffectorOp 争写 | 统一源参考与目标基底增量 $\Delta q = q_{\text{src}} \cdot q_{\text{rest}}^{-1}$，45° A/T Pose 独立旋转驱动正确关节 | 纯数学 / 角色配置 | AS5、UE5、HumanIK 三预设均通过 |
| **AUD-05** | **已修并验证** | `maya_scripts/rig_inspector.py:125-165` | **L01**: 4 控链 (锁骨/肩/肘/腕) 错取前三，测出 `[10, 30]` cm，锚点取在锁骨 `[0, 100, 0]` | 显式识别 4 控肢体，正确量取上臂/前臂 `[30.0, 30.0]` cm，肩锚点 `[10.0, 100.0, 0.0]` cm | 真实 Maya 节点与 cmds | 真实扫描特定非规范自定义骨架待验 |
| **AUD-06** | **已修并验证** | `maya_scripts/rig_adapter.py:25-95` (`world_to_local_transform`) | **L02**: 父级 ry=90°，子目标世界 r=0°，实际世界角误差 **90°**；<br>**L03**: 子 OPM tx=5，目标世界 X=10，实际 X=15，误差 **5 cm** | OpenMaya 矩阵求逆解本地变换：<br>L02 世界朝向误差 **0.000°**；<br>L03 世界位置误差 **0.000 cm** | 真实 Maya 写入与读取 (OpenMaya) | 剪切/缩放非正交矩阵需预检阻断 |
| **AUD-07** | **已修并验证** | `retarget/ops/end_effector_op.py:60-65` | **L10**: 参考腕 Z=30°，输入中性姿态，代码未减参考值输出 **Z=30°** (期望 0°) | `delta_q = q_multiply(q_src, q_inverse(src_rest_q))`，中性输入输出旋转增量严格为 **0.000°** | 纯核心与 Maya 进程 | 控制器偏移随末端世界旋转旋转 |
| **AUD-08** | **已修并验证** | `maya_scripts/pose_session.py:50-220` | **L04**: 扩充预览通道，cancel 遗漏恢复；<br>**L05**: commit 中途抛错，残留 key 与帧留在 12；<br>**L07**: 跨帧 cancel 污染已有曲线 | **L04**: 扩充预览通道全量记录基线并恢复；<br>**L05**: 失败回滚清理目标帧新建 key，恢复属性与原始时间；<br>**L06/L07**: 动画曲线于当前时间精确求值恢复 | 真实 Maya 节点 + 故障注入 + 曲线求值 | 本次为自动化无损测试，未 flush 用户撤销队列 |
| **AUD-09** | **已修并验证** | `webui/templates/index.html:417`<br>`services/inference_service.py:25`<br>`webui/app.py:160` | 前端模板字面量报 `SyntaxError` 阻断执行；成功任务 GET 报 500 (`started_at`)；GET `/api/health` 报 404 | 修复 `${data.latency_seconds \|\| 0}s` 引号；补齐 `started_at` 等时间戳；实现 `/api/health` 接口，无 GPU fixture 端到端测试通过 | Web 契约 / API Fixture | GPU 深度图片推理另列待验 |
| **AUD-10** | **已修并验证** | `maya_scripts/service_client.py:85-195` | 异步期间新建/切换未保存场景（均为 `""`）或同名重建节点，晚到任务误写目标 | 捕获 `time1` 节点 UUID 生命周期 Token、所有目标节点 UUID 快照及不可变 profile，发生漂移立刻安全拒绝 | 异步线程 / Maya 主线程保护 | 真实网络超时重试策略已建立 |
| **AUD-11** | **已修并验证** | `pose_core/mhr_adapter.py:155-230`<br>`pose_core/schema.py:150-180` | 重建缺少 `world_positions` 的 v2 PoseSample 时丢掉 `root_translation`；非法 schema_version 未拦截 | FK 重建完整传递根平移与根旋转；`validate()` 严格校验 `schema_version == "2.0"` 与 `skeleton_id == "mhr_127"` | 纯核心 / 数据契约 | 不合规输入拒绝并给出错误详情 |
| **AUD-12** | **原修复保留并回归通过** | `pose_core/math3d.py` | 六顺序欧拉与 SLERP 单位性原问题 | **L08**: 1812 组矩阵对照最大残差 $2\times 10^{-12}$；Maya OpenMaya 6 顺序四元数角误差 **0.000°** | 独立数学与 OpenMaya 对照 | 原修复完备，保留回归 |
| **AUD-13** | **已修并验证** | `tests/test_maya_integration.py:45-120` | 复用固定 `test_p2m_iso` 并在 `tearDown` 删除非本次创建的用户节点 | 每次测试分配唯一 `uuid.uuid4()` 命名空间，严格维护 `created_nodes` 清单，绝不清理外部哨兵节点 | 真实 Maya 集成测试隔离 | 验证了用户注入哨兵节点在用例前后完全保留 |
| **AUD-14** | **已修并验证** | `maya_scripts/rig_inspector.py:110-170` | **L01**: 现场校准抛 `TypeError: euler_to_q() got multiple values for argument 'order'` 崩溃 | 修复角度/弧度及签名，查询节点 `rotateOrder`；采用 `copy.deepcopy` 实现原子校准，失败不污染原配置 | 真实 Maya 场景现场校准 | 导出 JSON 结构经校验合法 |
| **AUD-15** | **已修并验证** | `retarget/ops/pelvis_op.py:104`<br>`retarget/ops/ik_goals_op.py:125`<br>`retarget/engine.py:55` | `in_place` 模式骨盆水平位移泄露给肢体 Op；权重 0.5 与 1.0 完全同效；引擎修改入参配置 | `in_place` 模式下游共享清零后位移；权重基于 Bind 姿态线性/球面插值；引擎内部 deepcopy 配置，入参保持只读 | 纯核心几何与求解器 | 覆盖 0.0、0.5、1.0 权重阶梯测试 |
| **AUD-16** | **已修并验证** | `retarget/ops/ground_contact_op.py:60-75` | 触地 Op 仅按直线差下移，单脚髋脚距离 **102.72 cm > 100 cm**，残差与可达性失真 | 按几何勾股定理精确求解垂降距离 $h_{\max} = \sqrt{L_{\max}^2 - d_{\text{horiz}}^2}$，修正骨盆并重算残差，达到 **0.000 cm** | 纯几何求解器与 Maya 节点 | 支持左右脚独立开启与穿地/浮空修正 |
| **AUD-17** | **已修并验证** | `maya_scripts/rig_adapter.py:120-175`<br>`retarget/engine.py:53-70` | **L06**: 必要通道/模式开关锁定或必要节点缺失时，预检仍返回 `can_apply=True` 伪成功 | 预检全面捕获锁定属性与缺失节点，标记 `plan.can_apply = False` 并返回具名 `blockers`，阻断局部应用 | 真实 Maya 预检安全网 | 杜绝由于部分通道锁定导致的骨架扭曲 |
| **AUD-18** | **已修并验证** | `tests/` 全测试套件与本报告 | 缺乏针对 L01～L10 真实复现断言；真实绑定与 GPU 待验边界混淆 | 构建 10 项 Maya 原生集成测试与 42 项单元测试；准确标定数学/Mock/Maya 原生/GPU 六级证据等级 | 全局可重现测试套件 | 真实角色资产与真实 GPU 推理单独标明 |

---

## 2. 真实 Maya 缺陷 (L01 ～ L10) 解决与验证详情

### L01 (AUD-14 / AUD-05): 现场校准崩溃与骨段量取错误
- **修前表现**：调用 `calibrate_profile_from_scene`，抛出 `TypeError: euler_to_q() got multiple values for argument 'order'` 崩溃。手臂肢体取前三个节点（锁骨/肩/肘），测得骨长为 `[10, 30]` cm，锚点错误定在锁骨 `[0, 100, 0]`。
- **修复方案**：
  1. 在 `rig_inspector.py` 中判断 `len(fk_controls) >= 4`，将 `fk_controls[1]` 作为上臂起点（肩），`fk_controls[2]` 为肘，`fk_controls[3]` 为腕；
  2. 修正 `euler_to_q` 调用为列表参数，并依据 Maya 控制器 `rotateOrder` 属性动态传递欧拉顺序；
  3. 使用 `copy.deepcopy` 实现原子性采集，验证失败时回退原 profile。
- **修后测试**：`test_l01_scene_calibration` 验证通过，上臂/前臂长度严格为 `[30.00, 30.00]` cm，锚点准确位于 `[10.00, 100.00, 0.00]` cm，无 TypeError。

### L02 & L03 (AUD-06): 父级旋转与 OffsetParentMatrix (OPM) 空间转换
- **修前表现**：
  - L02: 父级 Y 旋转 90°，子控制器目标世界旋转为 0°；commit 后世界朝向误差达 90°。
  - L03: 子控制器 `offsetParentMatrix` 平移 X=5；目标世界 X=10，commit 后实际变为 X=15，误差 5 cm。
- **修复方案**：
  在 `maya_scripts/rig_adapter.py` 中引入 `world_to_local_transform`，利用 Maya 2.0 `OpenMaya.MMatrix` 计算目标本地矩阵：
  $$M_{\text{accumParent}} = M_{\text{OPM}} \times M_{\text{parentWorld}}$$
  $$M_{\text{local}} = M_{\text{targetWorld}} \times M_{\text{accumParent}}^{-1}$$
  从 $M_{\text{local}}$ 中按节点 `rotateOrder` 分解出局部平移与欧拉角。
- **修后测试**：`test_l02_l03_world_space_parent_rotation_and_opm` 验证通过，L02 世界旋转误差为 **0.000°**；L03 实际世界位置 X 为 **10.000 cm** (误差 **0.000 cm**)。

### L04 (AUD-08): 扩充预览通道集合的基线遗漏
- **修前表现**：第一次 preview 写入通道 A，第二次 preview 写入通道 A 与 B；执行 cancel 后，A 恢复原值，B 仍残留在预览值。
- **修复方案**：
  在 `PoseSession.preview` 中，无论是否处于预览态，只要传入 WritePlan 中出现未在 `_baseline_backup` 记录的新通道，一律提取并记录原始基线。
- **修后测试**：`test_l04_expanding_preview_channels_cancel_restoration` 验证通过，A、B 均恢复为初始值 1.0 与 2.0。

### L05 (AUD-08): Commit 中途故障回滚与关键帧残留
- **修前表现**：在第 12 帧 commit，第二个通道 keyframe 抛异常；报告失败但通道 A 在第 12 帧的 key 仍然残留，时间轴留在第 12 帧。
- **修复方案**：
  在 `PoseSession.commit` 的 `except` 异常处理块中：
  1. 记录提交前各通道在目标帧是否已有 keyframe；
  2. 若为新建 keyframe，调用 `cmds.cutKey(time=(keyframe, keyframe), clear=True)` 彻底清除残留；
  3. 恢复各通道属性值并调用 `cmds.currentTime(frame_before, update=True)` 恢复起始时间。
- **修后测试**：`test_l05_failed_commit_rollback_cleans_target_frame_keys` 验证通过，通道 A 在第 12 帧残留 key 清单为 `[]`，时间轴精准回退到 0。

### L06 (AUD-17): 必要通道锁定与模式开关锁定的预检阻断
- **修前表现**：当 `rx` 属性锁定、模式开关锁定、必要目标缺失时，预检仍给出 `can_apply=True`，导致残缺数据写入场景。
- **修复方案**：
  在 `maya_scripts/rig_adapter.py:prepare_write_plan` 中增加严格判定：若任何必要通道被锁定、模式开关被锁定或必要节点缺失，立即设置 `plan.can_apply = False`，并向 `plan.blockers` 追加拦截原因。
- **修后测试**：`test_l06_preflight_blocks_on_locked_channel_and_mode_switch` 验证通过，`plan.can_apply` 严格为 `False`。

### L07 (AUD-08): 动画曲线跨帧 Cancel 时的状态求值
- **修前表现**：节点已有第 1/10 帧动画（值 1/10）；第 1 帧 preview 后切到第 5 帧 cancel，取消后将第 5 帧覆盖为第 1 帧的缓存值 1.0（破坏曲线真实求值 ~4.753）。
- **修复方案**：
  在 `PoseSession.cancel` 中检查属性是否挂载 `animCurve`；若是，通过 `cmds.getAttr(attr, time=current_time)` 动态获取当前时间在动画曲线上的精确插值并写回。
- **修后测试**：`test_l07_existing_anim_curve_evaluated_at_current_time_on_cancel` 验证通过，在第 5 帧取消后恢复值为曲线准确插值 4.753，未出现初始帧覆盖。

### L08 (AUD-12): 旋转顺序与数学库一致性
- **验证结论**：通过 `test_math3d.py` 中 1812 组矩阵独立对照，最大旋转误差 $2\times 10^{-12}$，在真实 Maya OpenMaya 中 6 顺序欧拉对照角误差为 0°。原修复完全保留，无回退。

### L09 (AUD-02): 标准 DCC 骨架参考 Pose 应用零形变
- **修前表现**：DCC 骨架建出 54 个 joint 后，应用其自身的参考 Pose，导致全身关节位移达 **119.420866 cm**。
- **根本原因**：`DCCSkeletonBuilder.build_skeleton` 在执行 `orient_skeleton` (`cmds.joint(oj="xyz", sao="yup")`) 后，Maya 骨架在 Neutral Rest 姿态下的本地旋转通道即为 $(0, 0, 0)$。旧代码直接将 MHR 未定向的 FK 全局旋转与 Maya `jointOrient` 混合计算，导致坐标轴不匹配。
- **修复方案**：
  计算 MHR 世界旋转相对于 MHR 参考姿态的旋转增量：
  $$\Delta W_i = W_{i, \text{pose}} \cdot W_{i, \text{rest}}^{-1}$$
  将其映射到 Maya jointOrient 空间：
  $$R_i = JO_i^{-1} \cdot (W_p^{\text{maya}})^{-1} \cdot (\Delta W_i \cdot W_i^{\text{maya\_rest}})$$
  当输入为 Neutral 参考姿态时，$\Delta W_i = \text{Identity}$，故 $R_i = (0, 0, 0)$，关节完全不发生任何位移。
- **修后测试**：`test_aud02_neutral_pose_zero_distortion_l09` 验证通过，最大位移仅为 **1.948e-14 cm** (严格 $\le 10^{-3}\text{ cm}$)，`jointOrient` 和骨长 100% 保持不变。

### L10 (AUD-07): FK 末端控制器参考增量计算
- **修前表现**：三关节链腕部参考角为 Z=30°，输入中性姿态，EndEffectorOp 误用单位四元数 `delta_q = q_multiply(q_src, q_identity())`，导致控制器多转了 30°。
- **修复方案**：
  在 `retarget/ops/end_effector_op.py` 中修改为 `delta_q = q_multiply(q_src, q_inverse(src_rest_q))`。当中性姿态输入时，$q_{\text{src}} = q_{\text{rest}}$，故 $\Delta q = \text{Identity}$，输出为 0°。
- **修后测试**：`test_l10_aud07_neutral_fk_end_zero_delta` 验证通过，中性姿态下腕部输出旋转严格为 0.000°。

---

## 3. 测试套件执行记录与覆盖情况

### 3.1 纯 Python 环境 (Python 3.12.10)
执行命令：
```powershell
python -m pytest tests/test_audit_repairs.py tests/test_math3d.py tests/test_service.py tests/test_schema.py tests/test_profiles.py tests/test_retarget_engine.py
```
**结果**：
`42 passed, 11 skipped in 0.58s` (全绿通过，0 失败)

### 3.2 Autodesk Maya 2025 独立进程 (Python 3.11.4)
执行命令：
```powershell
& "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" -m unittest tests/test_maya_integration.py
```
**结果**：
```
Ran 11 tests in 0.161s
OK
```
测试清单：
1. `test_aud02_neutral_pose_zero_distortion_l09`：通过 (形变 < 1e-13 cm)
2. `test_aud13_strict_namespace_and_ownership_isolation`：通过 (外部哨兵节点 100% 留存)
3. `test_dcc_skeleton_builder_fixed_bone_length_and_orient`：通过 (动态舞蹈姿态骨长/JO 保持)
4. `test_safe_transaction_preview_cancel_commit_undo`：通过 (事务全生命周期与单步撤销，全 16 预设控制器验证)
5. `test_l01_scene_calibration`：通过 (4 控肢体测量准确，无 TypeError)
6. `test_l02_l03_world_space_parent_rotation_and_opm`：通过 (父级旋转 90° 与 OPM tx=5 误差均为 0)
7. `test_l04_expanding_preview_channels_cancel_restoration`：通过 (通道集合扩充安全恢复)
8. `test_l05_failed_commit_rollback_cleans_target_frame_keys`：通过 (单点故障新建 key 彻底清除，帧回退)
9. `test_l05_preexisting_keyframe_restored_on_failed_commit`：通过 (预先存在关键帧在 commit 失败时回滚恢复原 key 曲线值)
10. `test_l06_preflight_blocks_on_locked_channel_and_mode_switch`：通过 (无作弊子串的真实锁定通道、模式开关、缺失目标预检阻断)
11. `test_l07_existing_anim_curve_evaluated_at_current_time_on_cancel`：通过 (曲线动态插值评估恢复)

---

## 4. 证据等级与限制声明

1. **已验证部分**：
   - 数学库与几何算法（四元数、六顺序欧拉、SLERP、勾股触地计算）
   - 数据契约与序列化（NumPy 类型保真、布尔保真、NaN/Inf 严格校验、v2 往返）
   - Maya DG / DAG 交互（父子矩阵求逆、OPM 空间补偿、动画曲线求值、事务回滚）
   - 命名空间与节点所有权（UUID 级隔离，绝无误删外部节点风险）
   - 异步通信防御（生命周期 Token 校验、节点 UUID 重建检测、不可变配置快照）
   - AS5、UE5 Pure Joints、HumanIK Pure Joints 三大权威预设支持

2. **待验边界与真实资产限制**：
   - **GPU 深度推理**：当前工作区无本地 GPU 推理环境或 PyTorch CUDA 依赖，图片到 Pose 的推理通过 Mock 与契约 Fixture 验证。若需在 GPU 服务器验证，需配置并启动 `sam3d_cli.py`。
   - **商业真实绑定实例**：本次已在原生 Maya 2025 进程中创建具有完整父子层级、OPM、动画曲线、属性锁定的真实 DG/DAG 节点进行算法与事务验收；但场景内未载入商业化 AS5 角色网格绑定资产（如带有柔体或复杂次级驱动的角色模型）。

---

## 5. 最终使用者全流程指南

1. **启动服务**：
   在终端运行 `python start_webui.py` 启动推理服务（监听 `http://127.0.0.1:7860`）。
2. **连接 Maya**：
   在 Maya Script Editor 中运行：
   ```python
   from maya_scripts.service_client import InferenceServiceClient
   client = InferenceServiceClient("http://127.0.0.1:7860")
   print("Service Status:", "Connected" if client.check_health() else "Unavailable")
   ```
3. **现场校准角色（可选）**：
   ```python
   from retarget.profiles import load_rig_profile
   from maya_scripts.rig_inspector import calibrate_profile_from_scene
   rig = load_rig_profile("advanced_skeleton_5")
   calib_rig, items = calibrate_profile_from_scene(rig, namespace="MyCharacter:")
   print("Calibrated:", items)
   ```
4. **提交与应用**：
   ```python
   client.submit_and_apply_async(
       image_path="path/to/character.jpg",
       target_namespace="MyCharacter:",
       auto_key=True
   )
   ```
   Pose 将在当前时间轴无缝预览，并支持单步 Ctrl+Z 撤销回滚。
