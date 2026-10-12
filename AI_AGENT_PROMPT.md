# Pose2maya - AI Agent 资产与依赖安装提示词 (Prompt for AI Agent)

如果您希望使用 AI Agent（如 Claude Code, Cursor, Windsurf, Devin, Antigravity 等）帮您全自动安装与配置本项目的所有环境依赖与核心模型资产（**仅负责安装配置，不启动服务**），可以直接复制以下提示词给 AI Agent。

---

## 🎯 一句话极简安装指令 (One-Sentence Prompt)

```text
请帮我拉取 https://github.com/zwj870987952-maker/Pose2maya.git，并在环境中自主安装好所有 Python 依赖与大模型资产（包含 PyTorch CUDA、requirements.txt 以及运行 download_models.py 下载 model.ckpt 和 mhr_model.pt 权重），验证所有资产完整就绪后通知我，不需要运行启动脚本。
```

---

## 📋 标准安装指令 (Standard Installation Prompt)

```markdown
请帮我把 Pose2maya 项目的所有运行依赖与模型权重资产完整安装并配置就绪（仅完成安装与资产下载，无需启动 WebUI）：

1. 克隆代码库：
   git clone https://github.com/zwj870987952-maker/Pose2maya.git
   cd Pose2maya

2. 安装 Python 环境与核心依赖：
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

3. 下载并就绪核心模型资产（主模型权重与 MHR 骨骼几何资产）：
   python download_models.py
   # 确保以下核心权重文件已下载完整：
   # - checkpoints/sam-3d-body-dinov3/model.ckpt (~2.01GB)
   # - checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt (~696MB)

4. 验证模型资产完整性：
   检查上述权重文件大小，并运行单图测试验证模型与管线已能正常加载：
   python sam3d_cli.py --image test_benchmark/01_human_standard.jpg

5. 安装与验证完成，向我汇报就绪状态。
```
