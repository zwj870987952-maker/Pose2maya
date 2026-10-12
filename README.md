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
├── download_models.py          # 模型权重一键自动下载脚本 (支持大陆高速镜像)
├── download_models.bat         # Windows 桌面一键下载权重脚本
└── requirements.txt            # Python 依赖清单
```

---

### 4. 模型权重下载 (Model Weights Download)

> [!IMPORTANT]
> 由于 GitHub 单文件 100MB 限制，大模型预训练权重未包含在 git 代码库中。**首次运行前请务必准备以下模型权重**：
> 1. **主模型权重 (`model.ckpt`，约 2.01 GB)**
> 2. **MHR 骨骼几何资产 (`mhr_model.pt`，约 696 MB)**

#### 方式一：一键自动下载（推荐）
在项目根目录直接双击运行 [`download_models.bat`](download_models.bat)，或在终端执行：
```powershell
python download_models.py
```
- 默认自动启用中国大陆高速镜像源（`hf-mirror.com`），无需配置网络代理，支持断点续传。
- 如需使用 Meta 官方需授权源，可指定参数：`python download_models.py --official --token 你的HF_TOKEN`。

#### 方式二：手动下载与放置
您也可以从 Hugging Face 手动下载对应文件，并放置在项目对应目录下：
| 权重文件名 | 文件大小 | 本地目标路径 | 下载链接 (免审批镜像 / 官方源) |
| :--- | :---: | :--- | :--- |
| `model.ckpt` | 2.01 GB | `checkpoints/sam-3d-body-dinov3/model.ckpt` | [镜像下载](https://huggingface.co/jetjodh/sam-3d-body-dinov3/blob/main/model.ckpt) · [Meta官方](https://huggingface.co/facebook/sam-3d-body-dinov3/blob/main/model.ckpt) |
| `mhr_model.pt` | 696 MB | `checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt` | [镜像下载](https://huggingface.co/jetjodh/sam-3d-body-dinov3/blob/main/assets/mhr_model.pt) · [Meta官方](https://huggingface.co/facebook/sam-3d-body-dinov3/blob/main/assets/mhr_model.pt) |

---

### 5. 快速使用 (Quick Start)

#### 🚀 方式一：全自动零干预一键启动 (推荐)
在项目根目录**直接双击运行 [`start_webui.bat`](start_webui.bat)** 或在终端运行：
```powershell
python start_webui.py
```
> [!TIP]
> 启动脚本内置**全自动自检与自愈引擎**：
> 1. **环境自检**：自动检测 Python 环境并自动通过国内清华高速镜像安装所有缺失依赖与 PyTorch CUDA 加速环境。
> 2. **资产自检**：自动检查主模型权重 (`model.ckpt`) 与骨架资产 (`mhr_model.pt`)，缺失时自动通过国内高速镜像源后台断点续传下载。
> 3. **配置自愈**：自动补齐 `model_config.yaml` 与 127 关节骨骼定义，规避任何路径异常。
> 4. **自动弹窗**：自动分配空闲端口，完成 GPU 显存预热并自动在浏览器弹出 WebUI。
> **全程无需任何手动操作！**

#### 方式二：手动配置运行
若希望在自定义隔离环境中手动操作：
```powershell
# 1. 安装 PyTorch CUDA 版与项目依赖
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt

# 2. 下载模型权重 (若未下载)
python download_models.py

# 3. 启动 WebUI 工作台
python start_webui.py
```

#### 🤖 方式三：交由 AI Agent 自动安装资产与依赖 (Prompt for AI Agent)
如果您使用 AI Agent（如 Claude Code, Cursor, Windsurf, Devin 等），可直接将以下指令复制给 Agent：

> **一句话安装指令**：  
> `请帮我拉取 https://github.com/zwj870987952-maker/Pose2maya.git，并在系统常规的独立 Python/venv 环境中自主安装好所有依赖与模型资产（包含 PyTorch CUDA、requirements.txt 以及运行 download_models.py 下载 model.ckpt 和 mhr_model.pt 权重），验证所有资产就绪后通知我。注意：这是独立的深度学习后台，严禁通过 Maya 或 mayapy 去执行安装与下载，且不需要运行 WebUI 启动脚本。`

*(更多详细提示词与环境隔离规则请参阅独立文档 [`AI_AGENT_PROMPT.md`](AI_AGENT_PROMPT.md))*

#### 3. 命令行批量执行
```powershell
python sam3d_cli.py --image "test.jpg" --output_dir "outputs/my_test"
```

#### 4. Maya 视口内直接导入并生成骨架
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

### Weights Download
Weights exceed GitHub's 100MB limit and must be acquired before running:
- Run `python download_models.py` (or double-click `download_models.bat`) to automatically fetch `model.ckpt` (2.01 GB) and `mhr_model.pt` (696 MB) from HuggingFace mirror.

### Key Highlights
- **WebGL 3D Studio**: Browser-based interactive viewport with 360° orbit inspection and benchmark presets.
- **True Multi-Format Export**:
  - **FBX**: High-performance binary FBX with $Y$-up, $+Z$ forward axis orientation, eliminating mirror disparity.
  - **BVH**: MoCap open text standard with pure-Python zero-dependency fallback.
  - **GLB**: Modern Khronos glTF standard.
  - **JSON / NPZ**: Normalized topology with translation, local quaternions, and raw tensors.
- **Standardized Naming**: 100% matched with UE5 Mannequin (`SK_Mannequin`) and Maya HumanIK schemas.
- **In-DCC Solvers**: Built-in Maya joint chain builder and FK/IK controller retargeting engine.
