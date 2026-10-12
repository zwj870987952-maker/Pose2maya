# Pose2maya - AI Agent 自动化部署提示词 (Prompt for AI Agent)

如果您希望使用 AI Agent（如 Claude Code, Cursor, Windsurf, Devin, Antigravity 等）帮您全自动安装与配置本项目的所有环境与模型资产，可以直接复制以下提示词给 AI Agent。

---

## 🎯 一句话极简指令 (One-Sentence Prompt)

```text
请帮我拉取 https://github.com/zwj870987952-maker/Pose2maya.git，并在根目录下运行 python start_webui.py（或双击 start_webui.bat）。脚本自带全自动自检，请协助监督并确保其自动完成依赖安装、大模型权重下载（download_models.py）并成功打开 Web 界面。
```

---

## 📋 标准自动化安装指令 (Standard Installation Prompt)

```markdown
请帮我把 Pose2maya 项目的所有环境依赖与核心模型资产完整安装就绪：

1. 克隆并进入项目目录：
   git clone https://github.com/zwj870987952-maker/Pose2maya.git
   cd Pose2maya

2. 安装深度学习环境与核心依赖（推荐国内清华镜像源加速）：
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

3. 自动下载并补齐大模型资产（包含主权重与 127 关节 MHR 资产）：
   python download_models.py
   # 验证两份关键资产是否就绪：
   # - checkpoints/sam-3d-body-dinov3/model.ckpt (~2.0GB)
   # - checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt (~696MB)

4. 运行单图烟测验证流水线完整性：
   python sam3d_cli.py --image test_benchmark/01_human_standard.jpg

5. 全部就绪后启动 WebUI 工作台：
   python start_webui.py
```
