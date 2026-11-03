"""
Pose2maya - WebUI & Inference Service Launcher (Phase 2)
Provides:
1. Environment diagnostics and missing dependency reporting (non-invasive by default)
2. Model weight status checking and discovery
3. Benchmark presets & DCC tools verification
4. Port allocation, background service startup, and browser launch
"""

import os
import sys
import time
import socket
import argparse
import webbrowser
import threading
import subprocess
import importlib
import shutil

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(REPO_ROOT)

# Guard against accidental execution inside Maya DCC
if "mayapy" in sys.executable.lower() or ("autodesk" in sys.executable.lower() and "maya" in sys.executable.lower()):
    print("=" * 70)
    print(" [拦截警告] 检测到您正在尝试通过 Autodesk Maya 内置解释器 (mayapy) 启动 WebUI！")
    print(" Pose2maya 是独立的深度学习运算服务端，依赖 PyTorch (CUDA) 与系统环境。")
    print(" 严禁在 Maya 内部启动服务端！请使用系统常规 Python (如 python start_webui.py) 运行。")
    print("=" * 70)
    sys.exit(1)


def print_banner(step_str, desc_str):
    print(f"\n[{step_str}] {desc_str}")
    print("-" * 65)


def check_python_dependencies(auto_install=False):
    """
    Checks Python dependencies. Reports status without blindly upgrading user environment
    unless --auto-install is explicitly specified.
    """
    print_banner("1/4 环境自检", "检查 Python 依赖包与 CUDA 加速环境...")

    torch_ready = False
    try:
        import torch
        has_cuda = torch.cuda.is_available()
        cuda_name = torch.cuda.get_device_name(0) if has_cuda else "CPU (未启用CUDA)"
        print(f"  [✓] PyTorch 已就绪: v{torch.__version__} (加速设备: {cuda_name})")
        torch_ready = True
    except ImportError:
        print("  [!] 未检测到 PyTorch 运行环境。")

    required_packages = [
        ("flask", "flask"),
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("cv2", "opencv-python"),
        ("timm", "timm"),
        ("roma", "roma"),
        ("trimesh", "trimesh"),
        ("yacs", "yacs"),
        ("omegaconf", "omegaconf"),
        ("hydra", "hydra-core"),
        ("huggingface_hub", "huggingface_hub"),
        ("pytorch_lightning", "pytorch-lightning"),
        ("einops", "einops"),
        ("PIL", "Pillow"),
        ("tqdm", "tqdm"),
        ("yaml", "pyyaml"),
        ("requests", "requests"),
        ("jinja2", "jinja2"),
    ]

    missing = []
    for mod_name, pip_name in required_packages:
        try:
            importlib.import_module(mod_name)
        except ImportError:
            missing.append(pip_name)

    if missing:
        print(f"  [!] 缺失依赖包: {', '.join(missing)}")
        if auto_install:
            print("      正在根据 --auto-install 参数安装缺失依赖...")
            cmd = [sys.executable, "-m", "pip", "install", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"] + missing
            subprocess.run(cmd, check=False)
        else:
            print("      如需自动安装，请运行: pip install -r requirements.txt 或使用 --auto-install 参数")
    else:
        print("  [✓] 所有必要 Python 库依赖已就绪！")


def check_model_weights():
    """Checks SAM 3D Body + MHR checkpoints."""
    print_banner("2/4 资产自检", "检查模型预训练权重 (model.ckpt & mhr_model.pt)...")

    ckpt_path = os.path.join(REPO_ROOT, "checkpoints", "sam-3d-body-dinov3", "model.ckpt")
    mhr_path = os.path.join(REPO_ROOT, "checkpoints", "sam-3d-body-dinov3", "assets", "mhr_model.pt")

    has_ckpt = os.path.exists(ckpt_path) and os.path.getsize(ckpt_path) > 100 * 1024 * 1024
    has_mhr = os.path.exists(mhr_path) and os.path.getsize(mhr_path) > 100 * 1024 * 1024

    if not has_ckpt or not has_mhr:
        # Check fallback
        alt_ckpt = r"D:\sam-3d-body\checkpoints\sam-3d-body-dinov3\model.ckpt"
        alt_mhr = r"D:\sam-3d-body\checkpoints\sam-3d-body-dinov3\assets\mhr_model.pt"
        if os.path.exists(alt_ckpt) and os.path.exists(alt_mhr):
            print(f"  [✓] 成功检测到外部可用模型权重: {alt_ckpt}")
            return True

        print("  [!] 未找到完整模型权重。")
        print("      如需执行新图片 GPU 推理，请运行: python download_models.py")
        return False
    else:
        print(f"  [✓] 模型权重已就绪: {ckpt_path}")
        return True


def find_available_port(start_port=7860, max_attempts=20):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


def open_browser_delayed(url, delay=1.2):
    def _open():
        time.sleep(delay)
        print(f"\n[WebUI] 正在浏览器中打开界面: {url}")
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description="Pose2maya WebUI & Inference Service")
    parser.add_argument("--port", type=int, default=7860, help="WebUI listening port")
    parser.add_argument("--auto-install", action="store_true", help="Automatically install missing dependencies")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    parser.add_argument("--fake", action="store_true", help="Run with fake model for testing")
    args = parser.parse_args()

    print("=" * 65)
    print("    Pose2maya - SAM 3D Body & MHR 3D 骨架姿态估计工作台 (v2.0)")
    print("=" * 65)

    check_python_dependencies(auto_install=args.auto_install)
    check_model_weights()

    port = find_available_port(args.port)
    url = f"http://127.0.0.1:{port}"

    from webui.app import app, service
    if args.fake:
        service.fake_mode = True
        print("[Launcher] Running in FAKE mode for development/testing.")

    print_banner("3/3 服务就绪", f"本地服务已就绪: {url}")
    if not args.no_browser:
        open_browser_delayed(url, delay=1.2)
    print(" 按 Ctrl + C 可停止服务。")
    print("-" * 65)

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
