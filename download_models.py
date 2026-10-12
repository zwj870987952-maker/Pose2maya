"""
Pose2maya - Model Weights Auto-Downloader
Downloads the required SAM 3D Body checkpoint and MHR skeletal assets.
Supports standard HuggingFace Hub and domestic mirror (https://hf-mirror.com).
"""

import os
import sys
import argparse

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
CKPT_DIR = os.path.join(REPO_ROOT, "checkpoints", "sam-3d-body-dinov3")
ASSETS_DIR = os.path.join(CKPT_DIR, "assets")

# HuggingFace repositories
PRIMARY_REPO = "jetjodh/sam-3d-body-dinov3"       # Public open mirror (No token/approval required)
OFFICIAL_REPO = "facebook/sam-3d-body-dinov3"     # Official Meta repository (Gated)

def check_existing():
    ckpt_path = os.path.join(CKPT_DIR, "model.ckpt")
    mhr_path = os.path.join(ASSETS_DIR, "mhr_model.pt")

    # Also check existing local installation
    alt_ckpt = r"D:\sam-3d-body\checkpoints\sam-3d-body-dinov3\model.ckpt"
    alt_mhr = r"D:\sam-3d-body\checkpoints\sam-3d-body-dinov3\assets\mhr_model.pt"

    if (not os.path.exists(ckpt_path) or os.path.getsize(ckpt_path) < 100 * 1024 * 1024) and os.path.exists(alt_ckpt):
        print(f"[Downloader] 检测到 D 盘已有现成主权重: {alt_ckpt}")
        print("             正在创建本地快速映射，无需重复从网络下载...")
        try:
            import shutil
            shutil.copy2(alt_ckpt, ckpt_path)
            shutil.copy2(alt_mhr, mhr_path)
        except Exception as e:
            print(f"             复制提示: {e}")

    has_ckpt = os.path.exists(ckpt_path) and os.path.getsize(ckpt_path) > 100 * 1024 * 1024
    has_mhr = os.path.exists(mhr_path) and os.path.getsize(mhr_path) > 100 * 1024 * 1024
    return has_ckpt, has_mhr, ckpt_path, mhr_path

def download_models(use_mirror=True, official=False, token=None):
    os.makedirs(ASSETS_DIR, exist_ok=True)

    if use_mirror and "HF_ENDPOINT" not in os.environ:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        print("[Downloader] 已自动启用中国大陆高速镜像站点: https://hf-mirror.com")

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("[Downloader] 正在安装必要下载依赖 huggingface_hub ...")
        os.system(f'"{sys.executable}" -m pip install huggingface_hub')
        from huggingface_hub import hf_hub_download

    has_ckpt, has_mhr, ckpt_path, mhr_path = check_existing()

    repo_id = OFFICIAL_REPO if official else PRIMARY_REPO
    print("=" * 65)
    print(f"  Pose2maya 模型权重下载工具")
    print(f"  目标源仓库: {repo_id}")
    print(f"  保存目标目录: {CKPT_DIR}")
    print("=" * 65)

    # 1. Download model.ckpt (~2.01 GB)
    if has_ckpt:
        print(f"[✓] 主模型权重已存在: {ckpt_path} (大小: {os.path.getsize(ckpt_path)/1024/1024:.1f} MB)")
    else:
        print("\n[1/2] 正在下载 SAM 3D Body + DINOv3 主模型权重 (model.ckpt, 约 2.01 GB)...")
        print("      请保持网络通畅，支持断点续传...")
        try:
            downloaded = hf_hub_download(
                repo_id=repo_id,
                filename="model.ckpt",
                local_dir=CKPT_DIR,
                token=token
            )
            print(f"[✓] model.ckpt 下载完成: {downloaded}")
        except Exception as e:
            print(f"[✗] model.ckpt 下载失败: {e}")
            if not official:
                print("    提示: 可尝试指定官方源: python download_models.py --official --token 你的HF_TOKEN")
            return False

    # 2. Download mhr_model.pt (~696 MB)
    if has_mhr:
        print(f"[✓] MHR 骨架资产已存在: {mhr_path} (大小: {os.path.getsize(mhr_path)/1024/1024:.1f} MB)")
    else:
        print("\n[2/2] 正在下载 MHR 127 关节骨骼几何资产 (assets/mhr_model.pt, 约 696 MB)...")
        try:
            downloaded = hf_hub_download(
                repo_id=repo_id,
                filename="assets/mhr_model.pt",
                local_dir=CKPT_DIR,
                token=token
            )
            print(f"[✓] assets/mhr_model.pt 下载完成: {downloaded}")
        except Exception as e:
            print(f"[✗] mhr_model.pt 下载失败: {e}")
            return False

    # 3. Download model_config.yaml (if present)
    try:
        hf_hub_download(
            repo_id=repo_id,
            filename="model_config.yaml",
            local_dir=CKPT_DIR,
            token=token
        )
    except Exception:
        pass

    print("\n" + "=" * 65)
    print("  [✓] 所有必要模型权重已就绪！")
    print("  现在您可以运行 start_webui.bat 或 sam3d_cli.py 开始推理！")
    print("=" * 65)
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Pose2maya model checkpoints")
    parser.add_argument("--no-mirror", action="store_true", help="Do not use hf-mirror.com")
    parser.add_argument("--official", action="store_true", help="Download from official facebook/sam-3d-body-dinov3 (requires gated approval)")
    parser.add_argument("--token", type=str, default=None, help="HuggingFace access token if using gated repo")

    args = parser.parse_args()
    download_models(use_mirror=not args.no_mirror, official=args.official, token=args.token)
