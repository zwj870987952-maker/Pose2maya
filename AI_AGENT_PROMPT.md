# Pose2maya - AI Agent 资产与依赖安装提示词 (Prompt for AI Agent)

> ⚠️ **【首要原则与环境隔离警告】**  
> **Pose2maya 是独立的系统级 Python 深度学习算法服务，不是 Maya 内部插件！**  
> • 所有的依赖安装（PyTorch CUDA、pip 依赖）与模型资产下载（`download_models.py`）**必须在操作系统常规 Python (3.10~3.12) 或虚拟环境 (venv) 中运行**。  
> • **绝对严禁使用 Maya 内置的 `mayapy.exe` 执行安装或下载！**  
> • **绝对严禁通过 Maya 端口、Maya Script Editor 或 Maya MCP 插件去调度下载！**  
> • Maya 的唯一作用是最终接收与查看导出的 FBX 骨架文件，不参与任何算法安装。

---

## 📋 推荐：标准分步安装指令 (Standard Installation Prompt)

直接复制以下整段提示词发送给 AI Agent（如 Claude Code, Cursor, Windsurf, Devin 等）：

```markdown
请帮我把 Pose2maya 项目的所有运行依赖与模型权重资产完整安装并配置就绪：

【环境约束】：
- 本项目是系统级独立的深度学习服务端，必须在操作系统常规 Python 终端下执行。
- 严禁使用 Maya 内部解释器 (mayapy) 或通过 Maya 插件通道执行安装下载！
- 本次任务仅完成环境安装与资产下载，暂不需要启动 WebUI 服务。

【执行步骤】：
1. 克隆代码库：
   git clone https://github.com/zwj870987952-maker/Pose2maya.git
   cd Pose2maya

2. 在系统终端安装 Python 依赖（使用系统常规 Python，非 mayapy）：
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

3. 下载并就绪核心模型资产（主模型权重与 MHR 骨骼几何资产）：
   python download_models.py
   # 确保以下核心权重文件已下载完整：
   # - checkpoints/sam-3d-body-dinov3/model.ckpt (~2.01GB)
   # - checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt (~696MB)

4. 验证模型资产完整性：
   检查上述权重文件大小，并在系统终端运行单图测试验证模型载入正常：
   python sam3d_cli.py --image test_benchmark/01_human_standard.jpg

5. 安装与验证完成，向我汇报就绪状态。
```

---

## 🎯 备选：一句话极简指令 (One-Sentence Prompt)

```text
请帮我拉取 https://github.com/zwj870987952-maker/Pose2maya.git，并在系统常规的独立 Python/venv 环境中自主安装好所有依赖与模型资产（包含 PyTorch CUDA、requirements.txt 以及运行 download_models.py 下载 model.ckpt 和 mhr_model.pt 权重），验证所有资产就绪后通知我。注意：这是独立的深度学习后台，严禁通过 Maya 或 mayapy 去执行安装与下载，且不需要运行 WebUI 启动脚本。
```
