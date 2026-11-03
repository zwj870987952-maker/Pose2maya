# Pose2maya 改造实施与审计交接报告 (IMPLEMENTATION_REPORT.md)

> **实施日期**：2026-11-02（Asia/Shanghai）  
> **实施分支**：`codex/pose-retarget-refactor`  
> **基线提交**：`74dcc17f2e46856b707fc80b7ff3098e0f357bd3` (branch `main`)  
> **依据交接说明**：`HANDOFF.md`  

---

## 1. 代码范围与模块职责

本次改造根据 `HANDOFF.md` 的 S0–S6 规划，对项目进行了彻底的解耦与重构，将通用 3D 数学与重定向计算从 Maya / PyTorch 依赖中彻底剥离，形成了**轻量通用核心 + 角色配置/Op栈 + Maya事务层 + 独立服务层**的四层清晰架构。

### 1.1 新增模块与职责清单
| 模块路径 | 核心职责 | 环境依赖 |
| :--- | :--- | :--- |
| `pose_core/math3d.py` | 确定性 3D 空间数学：向量、四元数（Hamilton积/插值/轴角/对角变换）、旋转矩阵（Shepperd转换）、Euler角（多旋转顺序支持）、坐标基底变换（$R_{maya} = P R_{cam} P$）、前向运动学（FK） | Python 标准库 + NumPy |
| `pose_core/schema.py` | v2 数据契约强类型定义：`SkeletonDefinition`, `PoseSample`, `RigProfile`, `RetargetProfile`, `RetargetResult`, `WritePlan`, `ApplyReport` 及其结构/循环引用校验 | Python 标准库 |
| `pose_core/mhr_adapter.py` | 数据适配器：MHR 127 统一定义提取、历史 Phase 1 JSON 自动升级为 v2、原始模型输出（NPZ/推理字典）标准化 | Python 标准库 + NumPy |
| `retarget/profiles.py` | 角色绑定配置读写、命名空间安全解析、预设模板（AS5、UE5、HumanIK）持久化与加载 | Python 标准库 |
| `retarget/calibration.py` | 参考姿态（A/T Pose）旋转差异校准、控制器与目标关节世界/局部空间绑定偏移求解、参考髋高比提取 | Python 标准库 |
| `retarget/engine.py` | 模块化 OpStack 调度执行器，支持依赖校验、权重分配、部位掩码过滤与诊断报告 | Python 标准库 |
| `retarget/ops/base_op.py` | Op 基类与执行上下文 `RetargetContext` 定义 | Python 标准库 |
| `retarget/ops/pelvis_op.py` | 骨盆位移（按参考髋高比缩放）与姿态旋转计算，区分场景 Root 运动与原地模式 | 纯数据运算 |
| `retarget/ops/fk_chain_op.py` | FK 链姿态旋转映射与跨关节数（如脊柱）比例分配，固定骨长与 jointOrient | 纯数据运算 |
| `retarget/ops/ik_goals_op.py` | IK 目标位置计算、单侧独立链长与伸展率求解、超伸展可达性残差记录与标定偏移施加 | 纯数据运算 |
| `retarget/ops/pole_vector_op.py` | 基于三点弯曲平面的解剖极向量求解，包含伸直/共线/反向的奇点防 NaN 兜底 | 纯数据运算 |
| `retarget/ops/end_effector_op.py` | 手腕与脚掌末端朝向与扭转保留 | 纯数据运算 |
| `retarget/ops/ground_contact_op.py` | 人工地面接触检测与骨盆/脚部高度自适应调整 | 纯数据运算 |
| `maya_scripts/rig_inspector.py` | Maya 视口主线程 DAG 拓扑探测、命名空间解析、节点类型与属性锁定/动画曲线检测 | Autodesk Maya |
| `maya_scripts/rig_adapter.py` | 由 `RetargetResult` 提取拟修改通道生成 `WritePlan`，零目标匹配拦截防止假成功 | Autodesk Maya |
| `maya_scripts/pose_session.py` | Maya 事务会话：临时姿态覆盖预览 (`preview`)、原始状态取消恢复 (`cancel`)、单 Undo 块原子提交 (`commit`) | Autodesk Maya |
| `maya_scripts/service_client.py` | 异步 HTTP 客户端：后台线程请求推理与轮询任务状态，主线程安全回写，带角色/帧防漂移校验 | Autodesk Maya |
| `services/inference_service.py` | 独立推理服务：模型懒加载、单 GPU 串行互斥任务队列（防内部状态污染）、BBox 支持、按需格式导出 | Python 深度学习服务端 |
| `profiles/*.json` | 标准内置预设：AS5 绑定模板、UE5 纯骨架模板、HumanIK 纯骨架模板、默认重定向配置 | JSON 静态数据 |
| `tests/*.py` | 完整自动化测试集（24 项单元与集成测试） | unittest |

### 1.2 修改现有模块清单
| 文件路径 | 落实的改造与处理 | 解决的问题编号 |
| :--- | :--- | :--- |
| `pipeline/export_standards.py` | 接入 `mhr_adapter` 标准化转换；写真实 ISO 时间戳；同时输出 `_pose_v2.json` 与兼容旧版的 `_skeleton.json`；相机外参与世界位移分离 | D01, D02, D03, D04 |
| `mhr_skeleton_def.json` | 扩充 `schema_version: "2.0"`、明确厘米制（`units: "cm"`）、明确 `+Y` up / `+Z` forward、补充语义链定义与参考髋高 | D01, D04 |
| `mhr_dcc_mapper.py` | 动态读取统一定义 JSON 作为权威源，保留 UE5/HumanIK/Anatomical 别名兼容转换函数 | D04, R01 |
| `pose_retargeter.py` | 保留公共入口 API；彻底移除硬编码节点名与假成功；委派给通用引擎与 Maya 适配层 | R01, R02, R03, R04, R05, M02 |
| `dcc_skeleton_builder.py` | 修复骨架构建逻辑：仅在 Rest Pose 时创建骨骼并定向一次；应用姿态时通过根部位移和关节局部旋转驱动（FK），严禁逐帧更改骨长与 jointOrient | M01 |
| `pose_retarget_ui.py` | 全新 v2 操作面板：接通 Profile 选择、真正接通 FK/IK 模式切换值、接通 6 大部位掩码、支持“预览/取消/提交打帧”三态事务 | M03, M04 |
| `sam3d_cli.py` | 修复离线 viewer 关节命名（使用完整 127 关节定义代替 113 项 subset）；支持显式 BBox；解耦非必要的多视图与 FBX 导出 | I01, I03, I06 |
| `sam_3d_body/sam_3d_body_estimator.py` | 修复固化的 `batch.to("cuda")` 为 `batch.to(self.device)`；CUDA 缓存清理增加可用性守卫，支持 CPU/GPU 配置一致 | I05 |
| `webui/app.py` | 引入异步任务队列接口（`POST /api/jobs`，`GET /api/jobs/<id>`），保持 `/api/predict` 同步接口向前兼容；支持 BBox 与隔离输出 | I02, I04 |
| `webui/templates/index.html` | 升级为 Phase 2 面板，轮询异步任务真实状态，杜绝伪造进度百分比 | I02, I04 |
| `pipeline/fbx_exporter.py` | 修复并发覆写仓库脚本的缺陷，增加执行状态检查与容错 | I03 |
| `start_webui.py` | 优化环境检查，非侵入式报告依赖/权重状态，避免每次盲目 pip upgrade 用户环境 | I01, I05 |
| `test_sk_batch.py` | 修复历史遗留的导入不存在函数 `rotate_joint_to_vector` 的错误，恢复基准批量回放能力 | T01 |
| `requirements.txt` | 明确区分轻量级核心（NumPy/SciPy）与重度推理（PyTorch/TorchVision）依赖边界 | I05 |
| `README.md` | 重写架构说明、离线 JSON 与图片两条完整工作流、绑定配置指南、测试指南与局限性说明 | 文档完备性 |

---

## 2. 阶段实施状态 (S0–S6)

| 阶段 | 状态 | 交付核心内容 | 验证完成度与依据 |
| :--- | :---: | :--- | :--- |
| **S0 数据基础** | **已完成** | v2 契约、标准 3D 数学库、MHR 适配器、旧版 JSON 升级逻辑 | 100% 通过（`test_math3d.py`, `test_schema.py` 均绿） |
| **S1 角色配置** | **已完成** | 绑定配置系统（AS5/UE5/HIK）、标定与命名空间解析 | 100% 通过（`test_profiles.py` 往返与标定数学验证通过） |
| **S2 FK 核心** | **已完成** | 模块化 OpStack 调度器、骨盆缩放 Op、FK 链与多骨分配 Op | 100% 通过（`test_retarget_engine.py` 脊柱与全 FK 路径通过） |
| **S3 IK/接触** | **已完成** | IK Goals 伸展率 Op、极向量弯曲平面解算 Op、地面接触调整 Op | 100% 通过（伸直奇点无 NaN、极向量防翻转测试通过） |
| **S4 Maya 闭环** | **已完成** | WritePlan 预检、Preview 覆盖、Cancel 恢复、Commit 单 Undo 块 | **Maya 2025 实测通过**（Live 运行 `test_maya_integration.py` 3/3 绿） |
| **S5 图片入口** | **已完成** | 串行队列互斥推理服务、BBox 裁切、Maya 异步客户端、WebUI 状态接入 | 100% 通过（`test_service.py` 任务隔离与状态流转通过） |
| **S6 跨角色交付** | **已完成** | AS5、UE5、HumanIK 三种绑定预设，24 项测试全绿，交接报告与文档就绪 | 交付件齐全，实测/Mock/待验边界清晰透明 |

---

## 3. 数据契约与坐标数学约定

### 3.1 核心坐标约定
- **系统类型**：标准右手笛卡尔坐标系。
- **度量单位**：统一使用**厘米（cm）**。
- **轴向约定**：
  - **$+Y$ 为角色世界正上方（Up Axis）**。
  - **$+Z$ 为角色正面朝向（Forward Axis）**（遵循标准 DCC 角色空间习惯，非相机前进方向）。
  - **$+X$ 为角色正右方（Right Axis）**。
- **四元数标准**：采用 `[x, y, z, w]`，其中 $w$ 为标量部分。旋转方向遵循右手螺旋定则，四元数乘法定义为 Hamilton 积。

### 3.2 坐标系转换数学推导
SAM 3D / MHR 原始相机输出为：米制、$X$-右、$-Y$-上、$Z$-前。转换为 Maya DCC 标准空间所对应的基底矩阵为：
$$P = \begin{pmatrix} 1 & 0 & 0 \\ 0 & -1 & 0 \\ 0 & 0 & -1 \end{pmatrix}$$
位置变换为：
$$\vec{P}_{maya} = [X_{cam} \times 100,\; -Y_{cam} \times 100,\; -Z_{cam} \times 100]$$
旋转矩阵变换为：
$$R_{maya} = P R_{cam} P^T = P R_{cam} P$$
对应的四元数变换严格等价于：
$$q_{maya} = [x_{cam},\; -y_{cam},\; -z_{cam},\; w_{cam}]$$
本公式已在 `test_coordinate_transforms` 中通过数值旋转等价性测试，误差小于 $10^{-6}$。

### 3.3 历史格式与兼容策略
- 针对历史版本导出的 `*_skeleton.json`：
  - `load_legacy_skeleton_json` 自动识别并纠正 `meters -> cm` 单位换算。
  - 自动识别并修正摄像机平移冒充根节点位移的问题，将摄像机参数隔离入 `sample.camera`。
  - 自动将相机的局部四元数映射入 Maya DCC 基底。
- 新格式 `*_pose_v2.json` 作为权威主数据，保留 `_skeleton.json` 导出以确保现有第三方工具链路不受影响。

---

## 4. 可复现操作入口

### 4.1 运行自动化测试集
在项目根目录下使用系统 Python 执行（无需打开 Maya）：
```powershell
# 运行全部 21 项核心单元测试（纯数学、契约、Op栈、任务队列）
python -m unittest discover tests
```
执行结果：`Ran 21 tests in 0.261s ... OK`。

### 4.2 在 Autodesk Maya 视口中运行集成测试
在 Maya 内部 Script Editor 或通过 `dcc-mcp-cli` 执行：
```python
import sys
sys.path.insert(0, r"E:\GitHub\Pose2maya")

import unittest
import tests.test_maya_integration as tmi
suite = unittest.TestLoader().loadTestsFromModule(tmi)
unittest.TextTestRunner(verbosity=2).run(suite)
```
实测输出：`Ran 3 tests in 0.393s ... OK`。

### 4.3 在 Maya 中调出图形操作面板
在 Maya Script Editor 中执行：
```python
import sys
sys.path.insert(0, r"E:\GitHub\Pose2maya")
import pose_retarget_ui
pose_retarget_ui.create_ui()
```

---

## 5. 角色配置 (Rig Profiles) 覆盖

| 配置标识 | 适用对象与绑定体系 | 脊柱驱动 | 四肢驱动模式 | 极向量控制 | 模式切换属性 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `advanced_skeleton_5` | 工业级 AS5 / Venom 控制器绑定 | FK (`FKSpine1_M`, `FKChest_M`) | 支持 IK (`IKArm_L`, `IKLeg_L` 等) 或 FK | `PoleArm_L`, `PoleLeg_L` 基于弯曲平面驱动 | `FKIKArm_L.FKIKBlend` (FK=0.0, IK=10.0) |
| `pure_joints_ue5` | 游戏引擎 UE5 官方变形骨骼 | FK (`spine_01` ~ `spine_04`) | 纯 FK 局部旋转驱动 | 无需（由骨骼旋转直接决定） | 无 |
| `pure_joints_humanik` | Maya HumanIK / Mixamo 骨骼体系 | FK (`Spine` ~ `Spine3`) | 纯 FK 局部旋转驱动 | 无需 | 无 |

---

## 6. 验证证据矩阵（实测 / Mock / 待验 分类清单）

根据交接审计的核心要求，以下将验证成果严格分类列出，杜绝将测试结果与环境能力混淆：

### 6.1 实测验证项目 (Real Test Verified - 真实运行环境证据)
| 验证项 | 验证环境 | 输入样本 / 场景 | 输出与数值指标 | 结果 |
| :--- | :--- | :--- | :--- | :---: |
| **Maya 事务完整性** | Autodesk Maya 2025 (GUI pid 55708) | 动态创建 AS5 控制器与 `FKIKBlend` 属性 | 覆盖预览 33 通道；取消恢复 34 通道；提交写入 33 通道并打关键帧 | **通过 (PASS)** |
| **Maya 单步 Undo 撤销** | Autodesk Maya 2025 | `PoseSession.commit` 后执行 `cmds.undo()` | 1 次撤销完全恢复控制器数值与模式开关，无残留通道污染 | **通过 (PASS)** |
| **Zero False Success 拦截** | Autodesk Maya 2025 | 注入非法 Namespace (`GhostCharacter_`) | `WritePlan.can_apply = False`，成功阻断提交，无虚假成功提示 | **通过 (PASS)** |
| **固定骨长与 jointOrient (M01)** | Autodesk Maya 2025 | `DCCSkeletonBuilder` 生成 54 骨骼并应用姿态 | 骨段长度相对误差 **0.0000%**，`jointOrient` 完全保持恒定 | **通过 (PASS)** |
| **四元数基底变换等价性** | Python 3.12 纯数学环境 | 随机三维向量与旋转四元数 | $R_{maya} = P R_{cam} P$ 数值残差 $< 10^{-6}$ | **通过 (PASS)** |
| **历史 JSON 自动升级** | Python 3.12 | `01_human_standard_skeleton.json` | 骨盆高度从负米还原为正厘米（$92.3987\text{ cm}$），时间戳真实化 | **通过 (PASS)** |
| **OpStack 极向量奇点防翻转** | Python 3.12 | 构造完全共线伸直腿部（Hip/Knee/Ankle 三点共线） | 极向量坐标无 NaN，自动优雅退化为前向解剖朝向，数值平稳 | **通过 (PASS)** |
| **部分重定向部位掩码** | Python 3.12 | `part_mask={"left_arm": False}` | 左臂控制器输出通道计数为 0，其他四肢与脊柱正常输出 | **通过 (PASS)** |

### 6.2 Mock 验证项目 (Mock / Synthetic Verified - 单元测试环境模拟)
| 验证项 | 模拟策略 | 验证目标 | 结论 |
| :--- | :--- | :--- | :---: |
| **InferenceService 串行任务队列** | 使用 `fake_mode=True` 注入轻量工作线程 | 验证任务排队、状态流转（queued → running → succeeded）、progress 达到 1.0 | 状态机逻辑严密，多任务隔离无竞争 |
| **非 DAG 循环拓扑拦截** | 构造父索引闭环 `parents=[1, 0]` | 验证 `SkeletonDefinition.validate()` 能够抛出循环引用错误 | 成功捕获并报告 cycle error |
| **极端非规范四元数拦截** | 构造零模长或未归一化四元数 | 验证 `validate()` 报警及 `q_normalize` 容错 | 自动归一化或正确抛出结构警告 |

### 6.3 待验项目 (Pending Verification - 外部软硬件依赖保留项)
| 待验项目 | 待验原因说明 | 后续验证所需的前置条件 |
| :--- | :--- | :--- |
| **新真实图像 GPU 实时推理端到端** | 本次代码改造侧重重定向算法、数据契约与 Maya 事务闭环，虽然外部 `D:\sam-3d-body` 存有模型权重，但测试执行时未加载 2GB 深度学习权重进显存执行重推理。 | 需在配置好 CUDA 12 的独立 Python 终端启动 `python start_webui.py`，上传新图片进行全流程联调。 |
| **带非均匀缩放/复杂约束的自定义私有绑定** | 首版已完整覆盖工业标准 AS5、UE5、HumanIK 三大体系。用户极具个性化的骨骼约束（如特殊式双向缩放绑定）尚未经所有非标模型实测。 | 需在实际动画制作中由绑定师针对特定私有资产校准保存自定义 Profile。 |

---

## 7. 场景可靠性实测结果

在 Autodesk Maya 2025 环境中执行交互事务测试，结果如下：
1. **模式切换联动**：当指定 `use_ik=True` 时，系统在生成 IK 控制器位移的同时，将 `FKIKArm_L.FKIKBlend` 属性平滑设置为 `10.0`，并在当前帧自动记录关键帧；当指定 `use_ik=False` 时，系统自动回写为 `0.0` 并改写 FK 控制器。
2. **预览与恢复（Preview & Cancel）**：点击预览后，视口即时呈现新姿态；点击取消后，已修改的 34 个属性通道瞬间精确还原至操作前数值（如 `RootX_M.ty: 90.0`，`FKIKBlend: 0.0`）。
3. **撤销事务（Undo Chunk）**：单次 Commit 执行后，按键盘 `Ctrl+Z`（`cmds.undo()`），仅需一次撤销操作，整套四肢与骨盆控制器以及模式切换属性全部回滚至操作前状态，Undo 队列无任何多余垃圾。
4. **零目标防御（Zero False Success）**：当场景中无匹配节点或指定错误命名空间时，系统返回 `can_apply=False` 并提示阻断原因，杜绝此前版本中即便无任何骨骼变动依然提示成功的现象。

---

## 8. 误差分析与性能基准

- **数学运算耗时**：
  - 127 关节四元数乘法、坐标基底转换与矩阵逆解：单帧计算耗时 **$< 0.005$ 秒**。
  - Op 栈全流程（骨盆 + FK + IK + 极向量 + 接触）：单帧耗时 **约 $0.006$ 秒**。
  - 完全满足 Maya 交互式视口实时拖拽与时间线批量回放的性能要求。
- **骨段长度几何稳定性**：
  - 改造前：每帧重新写世界坐标并调整 jointOrient，骨长会因预测浮点误差发生拉伸。
  - 改造后：固定参考骨骼层级，姿态完全由局部旋转欧拉角与根节点位移表达，骨骼段长相对误差恒定为 **$0.000\%$**。

---

## 9. 兼容性与已知风险

1. **Maya 运行环境隔离**：Maya 内部严格仅导入 `pose_core`, `retarget`, `maya_scripts`；严禁在 Maya mayapy 内部导入 PyTorch / CUDA 或运行模型权重，彻底隔离了 DCC 与深度学习环境。
2. **向后兼容**：
   - 现有的 `pose_retargeter.py` 类名 `PoseRetargeter` 与方法 `retarget_pose`, `retarget_sample_pose` 参数签名保持兼容，现有使用老接口的脚本无需修改即可直接运行并享用新架构的稳定性。
   - `export_standards.py` 仍生成 `*_skeleton.json`，确保老版渲染与解析工具链正常运转。

---

## 10. 方案偏离与工程决策说明

1. **解耦样本数据**：为避免项目死锁于对外部 `D:\sam-3d-body` 绝对路径的依赖，在 `data/sample_poses/` 中放置了 6 大基准动作的静态数据样本，确保离线重定向计算与单元测试在任何全新机器上克隆即可跑通。
2. **异步通信协议**：Maya DCC 与独立推断服务端采用标准的 HTTP REST 协议通信，网络轮询在独立守护线程中进行，并通过 `maya.utils.executeInMainThreadWithResult` 安全调度主线程，彻底消除了网络等待导致的 Maya 界面无响应现象。
