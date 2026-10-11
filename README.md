# Pose2maya: SAM 3D Body (DINOv3) & MHR to Maya/UE5 Pipeline

[English](#english-summary) | [中文说明](#中文文档)

---

## 中文文档

### 1. 项目简介
**Pose2maya** 是一套将单张二维人物图像快速推断为高精度 3D 人体骨架姿态，并无缝对接至 **Autodesk Maya** 角色绑定体系与 **Unreal Engine 5 (UE5)** 动画重定向的工业级工程流水线。

核心骨干基于 Meta **SAM 3D Body** (DINOv3 视觉骨干网) 与 **MHR** (Momentum Human Rig 127 关节体系)。

---

### 2. 核心功能与亮点

- 🖥️ **交互式 WebUI 工作台**：
  - 基于 Flask + Three.js 构建的暗黑现代操作台。
  - 支持实时 360° 3D 骨架旋转、平移、缩放，各关节悬浮信息与多视角对比。
  - 内置 6 类评测预设（标准站姿、街舞腾空、3D机甲、二次元插画、强透视镜头、交叉遮挡）。
- 📦 **全格式资产导出**：
  - **FBX 骨架**：工业级二进制 FBX，骨骼严格对齐世界坐标系（$Y$-up，$+Z$ 朝向，厘米制），左右肢体与 2D 原图完全一致，直接兼容 Maya 2023-2025 与 UE5。
  - **BVH 动捕格式**：通用纯文本骨骼层次与动作文件，支持纯 Python 零依赖降级导出。
  - **GLB 开放标准**：glTF 2.0 骨架模型，开箱即用支持引擎与 Web 前端。
  - **JSON 拓扑结构**：含 127 关节世界三维坐标、局部四元数旋转矩阵、相机参数与拓扑父子索引。
  - **NPZ 原始张量**：保留模型输出的未压缩张量数据。
- 🏷️ **权威 127 关节命名体系**：
  - 全面支持 **Unreal Engine 5 (UE5)** 规范命名（`root`, `pelvis`, `spine_01`, `thigh_l`, `upperarm_r`, `hand_l` 等）。
  - 支持 **Maya HumanIK** 规范命名（`Hips`, `Spine`, `LeftUpLeg`, `RightArm` 等）。
- 🎬 **Maya 内部脚本与重定向求解**：
  - [`dcc_skeleton_builder.py`](dcc_skeleton_builder.py)：在 Maya 场景中以原生 joint 节点直接构建标准骨骼链。
  - [`pose_retargeter.py`](pose_retargeter.py)：将推断出的 3D 姿态数学求解并约束驱动到自定义角色控制器（Rig）。

---

### 3. 项目结构

```text
Pose2maya/
├── pipeline/                   # 资产格式导出与转换引擎
│   ├── fbx_exporter.py         # FBX / BVH / GLB 多格式导出器
│   ├── export_standards.py     # 标准 JSON 与 NPZ 构建器
│   ├── visualizer.py           # 4 联屏多视角图与离线 3D HTML 查看器
│   └── blender_dcc_worker.py   # 后台极速生成 DCC 资产的专用工作器
├── sam_3d_body/                # SAM 3D Body 模型核心实现
├── webui/                      # WebUI 前后端
│   ├── app.py                  # Flask 后端服务
│   └── templates/index.html    # Three.js 交互式视口前端页面
├── maya_scripts/               # Maya 端内部脚本
│   └── mhr_importer.py         # Maya 视口读取 JSON 构建骨骼脚本
├── dcc_skeleton_builder.py     # Maya 原生标准骨骼构建器 (支持 UE5 / HumanIK 模式)
├── mhr_dcc_mapper.py           # 127 关节命名与父子层级权威映射表
├── pose_retargeter.py          # Maya 角色控制器重定向求解器
├── pose_retarget_ui.py         # Maya 重定向图形面板
├── mhr_skeleton_def.json       # 127 关节拓扑结构与标准 Rest Offsets 定义
├── start_webui.py              # WebUI 启动脚本 (自动分配端口并调用浏览器)
├── start_webui.bat             # Windows 桌面一键启动脚本
├── sam3d_cli.py                # 命令行 CLI 批量姿态推断工具
└── requirements.txt            # Python 依赖清单
```

---

### 4. 快速使用

#### 启动 WebUI 界面
直接双击运行 [`start_webui.bat`](start_webui.bat)，或在终端执行：
```powershell
python start_webui.py
```
浏览器将自动弹出 `http://127.0.0.1:7860` 工作台。上传图片后点击「开始 3D 姿态推断」，即可在视口交互并一键下载 FBX、BVH、GLB、JSON。

#### 命令行批量执行
```powershell
python sam3d_cli.py --image "test.jpg" --output_dir "outputs/my_test"
```

#### Maya 视口内直接导入并生成骨架
在 Maya Script Editor 中运行：
```python
import sys
sys.path.append(r"C:\Users\zwj87\Documents\Pose2maya")
from dcc_skeleton_builder import DCCSkeletonBuilder

# 初始化构建器 (支持 'ue5' 或 'humanik' 命名体系，'core' 为 54 核心骨模式)
builder = DCCSkeletonBuilder(naming_style="ue5", mode="core", prefix="UE5_")
builder.build_skeleton(r"outputs/my_test/test_skeleton.json")
```

---

## English Summary

**Pose2maya** recovers full 3D human pose estimations from a single 2D RGB image using **SAM 3D Body (DINOv3)** and Meta's **MHR (Momentum Human Rig 127-joint)** system, and delivers production-ready skeletal assets (**FBX, BVH, GLB, JSON**) fully aligned with **Autodesk Maya** and **Unreal Engine 5**.

### Key Highlights
- **WebGL 3D Studio**: Browser-based interactive viewport with 360° orbit inspection and benchmark presets.
- **True Multi-Format Export**:
  - **FBX**: High-performance binary FBX with $Y$-up, $+Z$ forward axis orientation, eliminating mirror disparity.
  - **BVH**: MoCap open text standard with pure-Python zero-dependency fallback.
  - **GLB**: Modern Khronos glTF standard.
  - **JSON / NPZ**: Normalized topology with translation, local quaternions, and raw tensors.
- **Standardized Naming**: 100% matched with UE5 Mannequin (`SK_Mannequin`) and Maya HumanIK schemas.
- **In-DCC Solvers**: Built-in Maya joint chain builder and FK/IK controller retargeting engine.
