import os
import sys
import time
import json
import glob
import uuid
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory, send_file

# Add repo root to path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(REPO_ROOT)

from sam3d_cli import SAM3DStandaloneRunner, DEFAULT_CKPT, DEFAULT_MHR, DEFAULT_SKEL_DEF

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB max upload
app.config['TEMPLATES_AUTO_RELOAD'] = True

BENCHMARK_DIR = os.path.join(REPO_ROOT, "test_benchmark")
OUTPUTS_DIR = os.path.join(REPO_ROOT, "outputs")
WEBUI_OUTPUTS_DIR = os.path.join(OUTPUTS_DIR, "webui")
os.makedirs(WEBUI_OUTPUTS_DIR, exist_ok=True)

# Global runner instance
runner = None

def get_runner():
    global runner
    if runner is None:
        print("[WebUI] Initializing SAM 3D Body Runner on GPU...")
        runner = SAM3DStandaloneRunner(
            checkpoint_path=DEFAULT_CKPT,
            mhr_path=DEFAULT_MHR,
            skeleton_def_path=DEFAULT_SKEL_DEF,
            device="cuda"
        )
        print("[WebUI] Runner initialized successfully!")
    return runner

PRESET_LIST = [
    {
        "id": "01_human_standard.jpg",
        "title": "1. 真人标准站姿",
        "tag": "真人写实",
        "desc": "标准全身直立站姿，用于验证黄金基准与自然脊柱S曲度"
    },
    {
        "id": "02_human_dancing.jpg",
        "title": "2. 真人高难度动作",
        "tag": "街舞腾空",
        "desc": "单腿腾空后仰街舞动作，验证肢体大范围展开与空间深度"
    },
    {
        "id": "03_game_3d_ironman.jpg",
        "title": "3. 3D 游戏角色",
        "tag": "3D机甲模型",
        "desc": "视口带控制器线框的机甲模型，验证对网格与线条干扰的鲁棒性"
    },
    {
        "id": "04_anime_illustration.jpg",
        "title": "4. 二次元插画",
        "tag": "赛璐珞二次元",
        "desc": "日系二次元非写实头身比插画，测试二次元域姿态与抬腿推断"
    },
    {
        "id": "05_strong_perspective.jpg",
        "title": "5. 强透视冲镜头",
        "tag": "广角俯冲",
        "desc": "3D虚拟人持械极速冲向镜头，检验极端近大远小与俯冲姿态"
    },
    {
        "id": "06_limb_occlusion.png",
        "title": "6. 肢体交叉遮挡",
        "tag": "摔倒重叠",
        "desc": "橄榄球摔地肢体严重贴地重叠，检验复杂自遮挡与朝天蹬腿"
    }
]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def get_status():
    import torch
    cuda_avail = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda_avail else "CPU"
    vram_total_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3) if cuda_avail else 0
    return jsonify({
        "cuda_available": cuda_avail,
        "device_name": device_name,
        "vram_total_gb": round(vram_total_gb, 1),
        "torch_version": torch.__version__,
        "model_loaded": runner is not None
    })

@app.route("/api/presets")
def get_presets():
    return jsonify(PRESET_LIST)

@app.route("/presets/<filename>")
def serve_preset(filename):
    return send_from_directory(BENCHMARK_DIR, filename)

@app.route("/outputs/<path:filepath>")
def serve_output(filepath):
    return send_from_directory(OUTPUTS_DIR, filepath)

@app.route("/api/predict", methods=["POST"])
def predict():
    try:
        t0 = time.time()
        active_runner = get_runner()

        preset_id = request.form.get("preset_id", "").strip()
        uploaded_file = request.files.get("file")

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
        run_dir = os.path.join(WEBUI_OUTPUTS_DIR, run_id)
        os.makedirs(run_dir, exist_ok=True)

        if preset_id:
            src_path = os.path.join(BENCHMARK_DIR, preset_id)
            if not os.path.exists(src_path):
                return jsonify({"error": f"预设图片不存在: {preset_id}"}), 400
            ext = os.path.splitext(preset_id)[1]
            img_path = os.path.join(run_dir, f"input{ext}")
            shutil.copy2(src_path, img_path)
            orig_name = preset_id
        elif uploaded_file and uploaded_file.filename:
            orig_name = uploaded_file.filename
            ext = os.path.splitext(orig_name)[1]
            if not ext:
                ext = ".jpg"
            img_path = os.path.join(run_dir, f"input{ext}")
            uploaded_file.save(img_path)
        else:
            return jsonify({"error": "请上传图片或选择预设样本"}), 400

        # Run inference
        result = active_runner.process_image(img_path, output_dir=run_dir)
        if result is None:
            return jsonify({"error": "模型未检测到人体姿态，请更换清晰的人体图像"}), 422

        elapsed = round(time.time() - t0, 2)
        base_name = os.path.splitext(os.path.basename(img_path))[0]

        # Read JSON content to return for client-side Three.js
        with open(result["skeleton_json"], "r", encoding="utf-8") as f:
            skeleton_data = json.load(f)

        rel_run_dir = os.path.relpath(run_dir, OUTPUTS_DIR).replace("\\", "/")

        return jsonify({
            "success": True,
            "run_id": run_id,
            "orig_name": orig_name,
            "latency_seconds": elapsed,
            "multiview_url": f"/outputs/{rel_run_dir}/{base_name}_multiview.png",
            "json_url": f"/outputs/{rel_run_dir}/{base_name}_skeleton.json",
            "npz_url": f"/outputs/{rel_run_dir}/{base_name}_raw_mhr.npz",
            "fbx_url": f"/outputs/{rel_run_dir}/{base_name}_skeleton.fbx" if result.get("skeleton_fbx") else None,
            "bvh_url": f"/outputs/{rel_run_dir}/{base_name}_skeleton.bvh" if result.get("skeleton_bvh") else None,
            "glb_url": f"/outputs/{rel_run_dir}/{base_name}_skeleton.glb" if result.get("skeleton_glb") else None,
            "html_url": f"/outputs/{rel_run_dir}/{base_name}_3d_viewer.html",
            "skeleton": skeleton_data
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/history")
def get_history():
    runs = []
    if os.path.exists(WEBUI_OUTPUTS_DIR):
        dirs = sorted(os.listdir(WEBUI_OUTPUTS_DIR), reverse=True)[:20]
        for d in dirs:
            dir_path = os.path.join(WEBUI_OUTPUTS_DIR, d)
            if not os.path.isdir(dir_path):
                continue
            mv_files = glob.glob(os.path.join(dir_path, "*_multiview.png"))
            json_files = glob.glob(os.path.join(dir_path, "*_skeleton.json"))
            if mv_files and json_files:
                base = os.path.splitext(os.path.basename(mv_files[0]))[0].replace("_multiview", "")
                rel_dir = os.path.relpath(dir_path, OUTPUTS_DIR).replace("\\", "/")
                runs.append({
                    "run_id": d,
                    "title": base,
                    "multiview_url": f"/outputs/{rel_dir}/{base}_multiview.png",
                    "json_url": f"/outputs/{rel_dir}/{base}_skeleton.json",
                    "html_url": f"/outputs/{rel_dir}/{base}_3d_viewer.html"
                })
    return jsonify(runs)

if __name__ == "__main__":
    # Preload runner
    get_runner()
    app.run(host="0.0.0.0", port=7860, debug=False)
