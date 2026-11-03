# Pose2maya: 单图 3D 人体姿态推断与 Maya 绑定控制器重定向

[English Summary](#english-summary) | [中文说明](#中文文档)

---

## 中文文档

### 1. 项目定位与架构
**Pose2maya** 致力于通过单张人物图片恢复高精度的 3D 人体姿态（基于 Meta **SAM 3D Body** / DINOv3 与 **MHR 127 关节体系**），经过角色映射与参考姿态校准后，应用到 **Autodesk Maya** 中不同的人形绑定角色，并保留动画师可以继续自由编辑的控制器关键帧。

项目采用模块化分层架构，**核心数学与重定向模块完全解耦**，不依赖 Maya、PyTorch 或 Flask：

```text
图片 / 裁切框 (BBox)             已有 JSON (离线/历史姿态)
       ↓                                ↓
独立 SAM 3D 推理服务               legacy JSON 适配器
       └──────────────┬─────────────────┘
                      ↓
           PoseSample v2 + 完整源骨架定义
                      ↓
    通用重定向核心 (pose_core / retarget)
      - RigProfile (AS5 / UE5 / HumanIK / 自定义)
      - RetargetProfile (Op 栈：骨盆/FK/IK/极向量/接触)
                      ↓
           目标控制器通道与 IK Goals
                      ↓
     Maya 适配层 (maya_scripts)
      - 预检 (WritePlan) → 临时预览 → 取消恢复或单步撤销提交
```

---

### 2. 核心模块与职责划分

| 模块目录 | 核心职责 | 环境依赖 |
| :--- | :--- | :--- |
| `pose_core/` | 3D 数学约定 (厘米制、$Y$-up、$Z$-前向)、四元数、前向运动学、v2 数据契约与旧 JSON 适配 | 仅 Python 标准库 + NumPy (无 PyTorch/Maya 依赖) |
| `retarget/` | 角色绑定配置 (RigProfile)、重定向预设、参考姿态校准与模块化 Op 栈求解引擎 | 仅 Python 标准库 + NumPy |
| `retarget/ops/` | 骨盆位移缩放、FK 链旋转分配、IK Goals 伸展率计算、极向量弯曲平面求解、地面接触 | 纯数据运算 |
| `maya_scripts/` | Maya 视口 DAG 场景探测、WritePlan 预检、临时覆盖预览、取消恢复与单 Undo 块事务提交 | Autodesk Maya (cmds / mel) |
| `services/` | 串行任务队列、线程安全单 GPU 互斥锁、BBox 裁切参数支持、按需资产导出 | 独立 Python 深度学习服务端 |
| `webui/` | 任务式异步推理 API (`/api/jobs`) 与 Three.js 姿态预览操作台 | Flask + Three.js |

---

### 3. 支持的角色绑定类型 (Rig Profiles)

系统内置预设角色配置文件（位于 `profiles/` 目录下），并支持动画师自定义扩展：

1. **Advanced Skeleton 5 (`advanced_skeleton_5.json`)**：
   - 支持骨盆控制器 `RootX_M`、脊柱 FK 控制器 `FKSpine1_M` / `FKChest_M`。
   - 支持手臂与腿部 FK/IK 双分支及无缝模式切换属性 (`FKIKArm_L.FKIKBlend` 等)。
   - 极向量控制器 `PoleArm_L`、`PoleLeg_L` 基于解剖弯曲平面驱动，避免伸直时翻转。
2. **UE5 官方骨架规范 (`pure_joints_ue5.json`)**：
   - 适用于纯变形骨骼（Deformation Skeleton）层级（`root`, `pelvis`, `thigh_l`, `upperarm_l` 等）。
3. **Maya HumanIK / Mixamo 规范 (`pure_joints_humanik.json`)**：
   - 适用于 HumanIK 纯关节层级（`Hips`, `Spine`, `LeftUpLeg`, `LeftArm` 等）。

---

### 4. 快速使用指南

#### 工作流 A：离线 JSON 姿态应用至 Maya 角色（无需 GPU/PyTorch）
在 Maya 内部 Script Editor (Python) 中执行：
```python
import sys
# 将项目根目录添加至 Python 路径
sys.path.insert(0, r"E:\GitHub\Pose2maya")

import maya.cmds as cmds
from pose_retarget_ui import create_ui

# 弹出通用姿态重定向面板 (v2.0)
create_ui()
```
面板功能：
- **选择绑定配置**：支持 AS5 控制器、UE5 纯骨架或 HumanIK。
- **选择驱动模式**：自由勾选优先使用 IK 控制器或纯 FK 旋转。
- **部位开关 (Part Mask)**：可按需单独重定向脊柱、单侧手臂或腿部。
- **临时预览 (Preview)**：将姿态写入视口供观察，不破坏已有关键帧。
- **取消恢复 (Cancel)**：一键撤销预览，恢复到操作前状态。
- **提交应用 (Commit)**：仅为实际修改通道设置关键帧，支持一次 `Ctrl+Z` 完整撤销。

#### 工作流 B：单张图片端到端推断并应用
1. **启动独立推理服务**：
   ```powershell
   python start_webui.py
   ```
   服务将监听并在 `http://127.0.0.1:7860` 启动异步推理任务队列。
2. **在 Maya 中发起异步图片推断**：
   ```python
   from maya_scripts.service_client import InferenceServiceClient

   client = InferenceServiceClient("http://127.0.0.1:7860")
   # 异步提交并在完成后自动应用到当前角色的当前帧 (Maya 界面全程不卡死)
   client.submit_and_apply_async(
       image_path="02_human_dancing.jpg",
       target_namespace="",
       use_ik=True,
       auto_key=True
   )
   ```

---

### 5. 自动化测试与验证

项目包含严密的单元测试与集成测试，覆盖坐标基底、前向运动学、Op 栈计算、任务队列与 Maya 事务：

```powershell
# 运行全部测试集
python -m unittest discover tests
```

测试集清单：
- `tests/test_math3d.py`：四元数、矩阵转换、坐标基底转换 $R_{maya} = P R_{cam} P$ 等价性、前向运动学。
- `tests/test_schema.py`：v2 契约数据校验、父节点循环检测、四元数范数约束。
- `tests/test_profiles.py`：角色配置读写、命名空间解析、控制器标定偏移。
- `tests/test_retarget_engine.py`：OpStack 执行、FK 链、IK Goals、极向量共线退化兜底、部位掩码。
- `tests/test_service.py`：推理服务串行任务队列、状态流转、并发任务隔离。

---

### 6. 当前边界与局限说明

- **当前版本范围**：聚焦单张图片、单人全身主要骨骼与手脚朝向的稳定姿态重定向；
- **后续扩展计划**：手指精细抓握、面部表情微调、多人自动裁切、视频连续防滑状态机将在后续版本迭代，不在当前首版承诺范围内。

---

## English Summary

**Pose2maya** is an end-to-end pipeline that recovers 3D human pose from a single 2D image (powered by Meta **SAM 3D Body / DINOv3** and **MHR 127**) and retargets it onto customizable humanoid rigs in **Autodesk Maya**, preserving artist-editable animation curves.

### Architecture
- **`pose_core/`**: Pure Python/NumPy 3D math (quaternions, coordinate conversion, FK) and v2 data contracts.
- **`retarget/`**: Operation Stack (Pelvis, FK, IK Goals, Pole Vector, Ground Contact) and Rig Profiles.
- **`maya_scripts/`**: Viewport scene inspector, WritePlan pre-flight checks, preview overlay, cancel/restore, and atomic single-chunk undo transactions.
- **`services/`**: Asynchronous queued inference service with GPU state isolation.
