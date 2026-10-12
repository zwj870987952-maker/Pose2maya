"""
Pose2maya - Fully Automated WebUI Launcher
Automatically checks, installs, and repairs:
1. Missing Python dependencies via domestic pip mirror (Tsinghua / Aliyun)
2. Missing PyTorch / TorchVision CUDA acceleration
3. Missing model checkpoints (model.ckpt & mhr_model.pt) via fast HuggingFace mirror
4. Missing model_config.yaml & mhr_skeleton_def.json configurations
5. Missing test benchmark images and output directories
6. Automatic port collision resolution and browser auto-launch
"""

import os
import sys
import time
import socket
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

def check_nvidia_smi():
    try:
        res = subprocess.run(["nvidia-smi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res.returncode == 0
    except Exception:
        return False

def ensure_python_dependencies():
    """
    Auto-detect and install any missing pip dependencies using fast domestic mirrors.
    """
    print_banner("1/4 环境自检", "检查并自动补齐 Python 依赖包与 CUDA 加速环境...")

    # 1. Check & ensure pip works
    try:
        import pip
    except ImportError:
        print("  [!] 检测到缺失 pip，正在自动配置 ensurepip...")
        subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], check=False)

    # 2. Check torch & torchvision
    torch_ready = False
    try:
        import torch
        import torchvision
        has_cuda = torch.cuda.is_available()
        cuda_name = torch.cuda.get_device_name(0) if has_cuda else "CPU (未启用CUDA)"
        print(f"  [✓] PyTorch 已就绪: v{torch.__version__} (加速设备: {cuda_name})")
        torch_ready = True
    except ImportError:
        torch_ready = False

    if not torch_ready:
        has_gpu = check_nvidia_smi()
        if has_gpu:
            print("  [!] 检测到系统中存在 NVIDIA 显卡但未安装 PyTorch。")
            print("      正在全自动安装 PyTorch CUDA 12.4 版本，请稍候...")
            cuda_cmd = [
                sys.executable, "-m", "pip", "install",
                "torch", "torchvision",
                "--index-url", "https://download.pytorch.org/whl/cu124"
            ]
            res = subprocess.run(cuda_cmd)
            if res.returncode != 0:
                print("  [提示] 官方 CUDA 源下载较慢或受限，自动切换为国内镜像源安装通用 PyTorch...")
                subprocess.run([
                    sys.executable, "-m", "pip", "install",
                    "torch", "torchvision",
                    "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"
                ], check=False)
        else:
            print("  [!] 未检测到独立显卡，正在全自动安装通用 PyTorch (CPU 版本)...")
            subprocess.run([
                sys.executable, "-m", "pip", "install",
                "torch", "torchvision",
                "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"
            ], check=False)

    # 3. Core dependencies list: (import_name, pip_package_name)
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
        ("matplotlib", "matplotlib"),
        ("braceexpand", "braceexpand"),
    ]

    missing = []
    for mod_name, pip_name in required_packages:
        try:
            importlib.import_module(mod_name)
        except ImportError:
            missing.append(pip_name)

    if missing:
        print(f"  [!] 检测到缺失依赖: {', '.join(missing)}")
        print("      正在通过国内高速镜像源（清华大学源）全自动安装...")
        install_cmd = [
            sys.executable, "-m", "pip", "install",
            "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
            "--trusted-host", "pypi.tuna.tsinghua.edu.cn"
        ] + missing
        res = subprocess.run(install_cmd)
        if res.returncode != 0:
            print("  [提示] 清华源返回异常，正在自动通过阿里云镜像源重试...")
            aliyun_cmd = [
                sys.executable, "-m", "pip", "install",
                "-i", "https://mirrors.aliyun.com/pypi/simple/",
                "--trusted-host", "mirrors.aliyun.com"
            ] + missing
            subprocess.run(aliyun_cmd, check=False)
        print("  [✓] 缺失依赖检测与安装流程执行完成！")
    else:
        print("  [✓] 所有必要 Python 库依赖已就绪！")

def ensure_model_weights():
    """
    Auto-detect and download SAM 3D Body + MHR checkpoints if missing.
    """
    print_banner("2/4 资产自检", "检查模型预训练权重 (model.ckpt & mhr_model.pt)...")

    ckpt_path = os.path.join(REPO_ROOT, "checkpoints", "sam-3d-body-dinov3", "model.ckpt")
    mhr_path = os.path.join(REPO_ROOT, "checkpoints", "sam-3d-body-dinov3", "assets", "mhr_model.pt")
    cfg_path = os.path.join(REPO_ROOT, "checkpoints", "sam-3d-body-dinov3", "model_config.yaml")

    os.makedirs(os.path.dirname(mhr_path), exist_ok=True)

    has_ckpt = os.path.exists(ckpt_path) and os.path.getsize(ckpt_path) > 100 * 1024 * 1024
    has_mhr = os.path.exists(mhr_path) and os.path.getsize(mhr_path) > 100 * 1024 * 1024

    # 1. Auto-discover from local alternative paths
    alt_candidates = [
        (r"D:\sam-3d-body\checkpoints\sam-3d-body-dinov3\model.ckpt", r"D:\sam-3d-body\checkpoints\sam-3d-body-dinov3\assets\mhr_model.pt"),
        (r"E:\ComfyUI-aki-v3\models\sam3d\model.ckpt", r"E:\ComfyUI-aki-v3\models\sam3d\mhr_model.pt"),
    ]

    for alt_c, alt_m in alt_candidates:
        if (not has_ckpt or not has_mhr) and os.path.exists(alt_c) and os.path.exists(alt_m):
            print(f"  [✓] 检测到本地已存在现有权重资产: {alt_c}")
            print("      正在自动建立本地映射，零网络耗时...")
            if not has_ckpt:
                try:
                    shutil.copy2(alt_c, ckpt_path)
                except Exception as e:
                    print(f"      复制主权重提示: {e}")
            if not has_mhr:
                try:
                    shutil.copy2(alt_m, mhr_path)
                except Exception as e:
                    print(f"      复制骨架资产提示: {e}")
            has_ckpt = os.path.exists(ckpt_path) and os.path.getsize(ckpt_path) > 100 * 1024 * 1024
            has_mhr = os.path.exists(mhr_path) and os.path.getsize(mhr_path) > 100 * 1024 * 1024
            break

    # 2. Download from mirror if still missing
    if not has_ckpt or not has_mhr:
        print("  [!] 检测到缺少核心预训练权重，正在调用极速下载器自动下载 (支持断点续传)...")
        from download_models import download_models
        download_models(use_mirror=True)
        has_ckpt = os.path.exists(ckpt_path) and os.path.getsize(ckpt_path) > 100 * 1024 * 1024
        has_mhr = os.path.exists(mhr_path) and os.path.getsize(mhr_path) > 100 * 1024 * 1024

    if has_ckpt and has_mhr:
        print(f"  [✓] 主模型权重已就绪: model.ckpt ({os.path.getsize(ckpt_path)/1024/1024:.1f} MB)")
        print(f"  [✓] 骨架几何资产已就绪: mhr_model.pt ({os.path.getsize(mhr_path)/1024/1024:.1f} MB)")
    else:
        print("  [警告] 权重下载尚未完全就绪，请检查网络连接后重试。")

    # 3. Ensure model_config.yaml in checkpoints folder
    bundled_cfg = os.path.join(REPO_ROOT, "sam_3d_body", "model_config.yaml")
    if not os.path.exists(cfg_path) and os.path.exists(bundled_cfg):
        shutil.copy2(bundled_cfg, cfg_path)
        print("  [✓] 模型配置映射已就绪: model_config.yaml")

def ensure_benchmark_presets():
    """
    Ensure benchmark test images and skeleton definitions exist.
    """
    benchmark_dir = os.path.join(REPO_ROOT, "test_benchmark")
    if not os.path.exists(benchmark_dir) or len(os.listdir(benchmark_dir)) == 0:
        alt_bench = r"D:\sam-3d-body\test_benchmark"
        if os.path.exists(alt_bench):
            shutil.copytree(alt_bench, benchmark_dir, dirs_exist_ok=True)
            print("  [✓] 评测基准图片集已就绪！")

    # Ensure output directories
    os.makedirs(os.path.join(REPO_ROOT, "outputs", "webui"), exist_ok=True)

    # Ensure skeleton definition
    skel_def = os.path.join(REPO_ROOT, "mhr_skeleton_def.json")
    if not os.path.exists(skel_def):
        alt_skel = r"D:\sam-3d-body\mhr_skeleton_def.json"
        if os.path.exists(alt_skel):
            shutil.copy2(alt_skel, skel_def)
            print("  [✓] MHR 127 关节骨骼定义已自动修复！")

def ensure_dcc_tools():
    """
    Check if Blender/Maya exists for FBX export, or notify about pure Python BVH fallback.
    """
    from pipeline.fbx_exporter import find_blender_exe
    b_exe = find_blender_exe()
    if b_exe:
        print(f"  [✓] 3D 转换引擎就绪: {b_exe} (支持极速导出工业级二进制 FBX / GLB / BVH)")
    else:
        print("  [i] 未检测到本地 Blender，系统将自动使用内置纯 Python 引擎导出 BVH 动捕骨骼与标准 JSON。")

def find_available_port(start_port=7860, max_attempts=20):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port

def open_browser_delayed(url, delay=1.5):
    def _open():
        time.sleep(delay)
        print(f"\n[WebUI] 正在浏览器中自动打开界面: {url}")
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()

def main():
    print("=" * 65)
    print("    Pose2maya - SAM 3D Body & MHR 3D 骨架姿态估计工作台")
    print("    [全自动启动引擎: 依赖自动安装 + 权重自动拉取 + 自动弹出]")
    print("=" * 65)

    # 1. Automatic dependency check & install
    ensure_python_dependencies()

    # 2. Automatic model weights check & download
    ensure_model_weights()

    # 3. Automatic benchmark presets, skeleton defs & DCC tools check
    ensure_benchmark_presets()
    ensure_dcc_tools()

    # 4. Bind Port and Preload GPU Model
    print_banner("3/4 引擎预热", "加载 GPU 模型与 MHR 资产到显存...")
    port = find_available_port(7860)
    url = f"http://127.0.0.1:{port}"

    from webui.app import app, get_runner
    get_runner()

    # 5. Launch Service & Pop Browser
    print_banner("4/4 服务就绪", f"本地 Web 服务已运行，即将弹出浏览器...")
    open_browser_delayed(url, delay=1.2)
    print(f" 服务访问地址: {url}")
    print(" 按 Ctrl + C 可停止服务。")
    print("-" * 65)

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
