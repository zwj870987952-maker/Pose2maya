import os
import sys
import argparse
import glob
import json
import cv2
import numpy as np
import torch

# Add repo root to path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(REPO_ROOT)

from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
from pipeline.export_standards import export_standard_skeleton_and_raw
from pipeline.visualizer import render_multiview_skeleton, generate_interactive_html
from pipeline.fbx_exporter import export_skeleton_json_to_fbx

DEFAULT_CKPT = os.path.join(REPO_ROOT, "checkpoints", "sam-3d-body-dinov3", "model.ckpt")
if not os.path.exists(DEFAULT_CKPT):
    fallback_ckpt = r"D:\sam-3d-body\checkpoints\sam-3d-body-dinov3\model.ckpt"
    if os.path.exists(fallback_ckpt):
        DEFAULT_CKPT = fallback_ckpt

DEFAULT_MHR = os.path.join(REPO_ROOT, "checkpoints", "sam-3d-body-dinov3", "assets", "mhr_model.pt")
if not os.path.exists(DEFAULT_MHR):
    fallback_mhr = r"D:\sam-3d-body\checkpoints\sam-3d-body-dinov3\assets\mhr_model.pt"
    if os.path.exists(fallback_mhr):
        DEFAULT_MHR = fallback_mhr

DEFAULT_SKEL_DEF = os.path.join(REPO_ROOT, "mhr_skeleton_def.json")
if not os.path.exists(DEFAULT_SKEL_DEF):
    fallback_skel = r"D:\sam-3d-body\mhr_skeleton_def.json"
    if os.path.exists(fallback_skel):
        DEFAULT_SKEL_DEF = fallback_skel

class SAM3DStandaloneRunner:
    def __init__(self, checkpoint_path=DEFAULT_CKPT, mhr_path=DEFAULT_MHR, skeleton_def_path=DEFAULT_SKEL_DEF, device=None):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        print(f"[SAM3D] Initializing on device: {self.device}")
        print(f"[SAM3D] Loading checkpoint: {checkpoint_path}")
        print(f"[SAM3D] Loading MHR: {mhr_path}")

        self.model, self.model_cfg = load_sam_3d_body(checkpoint_path, device=self.device, mhr_path=mhr_path)
        self.estimator = SAM3DBodyEstimator(
            sam_3d_body_model=self.model,
            model_cfg=self.model_cfg,
            human_detector=None,
            human_segmentor=None,
            fov_estimator=None
        )

        self.skeleton_def = None
        if os.path.exists(skeleton_def_path):
            with open(skeleton_def_path, "r", encoding="utf-8") as f:
                self.skeleton_def = json.load(f)
            print(f"[SAM3D] Loaded skeleton definition ({self.skeleton_def.get('num_joints', 0)} joints)")

    def process_image(self, image_path, output_dir, bbox=None):
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        print(f"\n==========================================")
        print(f"[SAM3D] Processing: {image_path}")

        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")
        h, w = img.shape[:2]

        if bbox is None:
            # Full image bounding box with 5% margin padding
            boxes = np.array([[0, 0, w, h]], dtype=np.float32)
        else:
            boxes = np.array([bbox], dtype=np.float32)

        # Run Core Model Inference
        outputs = self.estimator.process_one_image(image_path, bboxes=boxes)
        if not outputs:
            print(f"[SAM3D] Warning: No person detected in {image_path}")
            return None

        p0 = outputs[0]

        # 1. Export Standard Skeleton JSON & Raw NPZ
        raw_npz_path, json_path = export_standard_skeleton_and_raw(
            output_dict=p0,
            image_path=image_path,
            output_dir=output_dir,
            base_name=base_name,
            skeleton_def=self.skeleton_def
        )
        print(f"[SAM3D] Exported Raw NPZ: {raw_npz_path}")
        print(f"[SAM3D] Exported Standard JSON: {json_path}")

        # 2. Render 4-View Skeleton Image
        parent_indices = self.skeleton_def.get("parent_indices", []) if self.skeleton_def else []
        joint_coords = p0["pred_joint_coords"]
        keypoints_2d = p0.get("pred_keypoints_2d")
        multiview_img_path = os.path.join(output_dir, f"{base_name}_multiview.png")
        render_multiview_skeleton(
            image_bgr=img,
            joint_coords=joint_coords,
            parent_indices=parent_indices,
            keypoints_2d=keypoints_2d,
            output_path=multiview_img_path
        )
        print(f"[SAM3D] Rendered Multiview Skeleton: {multiview_img_path}")

        # 3. Generate Standalone Interactive 3D Web Viewer
        joint_names = self.skeleton_def.get("model_joints_subset", []) if self.skeleton_def else []
        html_viewer_path = os.path.join(output_dir, f"{base_name}_3d_viewer.html")
        generate_interactive_html(
            joint_coords=joint_coords,
            parent_indices=parent_indices,
            joint_names=joint_names,
            output_html_path=html_viewer_path,
            title=f"SAM 3D Skeleton - {base_name}"
        )
        print(f"[SAM3D] Generated Interactive 3D HTML Viewer: {html_viewer_path}")

        # 4. Export Standard FBX / BVH / GLB Skeletons
        fbx_path = os.path.join(output_dir, f"{base_name}_skeleton.fbx")
        export_res = export_skeleton_json_to_fbx(json_path, fbx_path)
        if isinstance(export_res, dict):
            fbx_res = export_res.get("fbx")
            bvh_res = export_res.get("bvh")
            glb_res = export_res.get("glb")
        else:
            fbx_res = export_res
            bvh_res = None
            glb_res = None

        if fbx_res:
            print(f"[SAM3D] Exported Standard FBX: {fbx_res}")
        if bvh_res:
            print(f"[SAM3D] Exported Standard BVH: {bvh_res}")
        if glb_res:
            print(f"[SAM3D] Exported Standard GLB: {glb_res}")

        return {
            "image": image_path,
            "raw_npz": raw_npz_path,
            "skeleton_json": json_path,
            "skeleton_fbx": fbx_res,
            "skeleton_bvh": bvh_res,
            "skeleton_glb": glb_res,
            "multiview_png": multiview_img_path,
            "html_viewer": html_viewer_path
        }

def main():
    parser = argparse.ArgumentParser(description="SAM 3D Body + DINOv3 Standalone Pipeline (Phase 1)")
    parser.add_argument("--image", type=str, default="", help="Path to single image")
    parser.add_argument("--folder", type=str, default="", help="Path to folder of images")
    parser.add_argument("--output_dir", type=str, default=os.path.join(REPO_ROOT, "outputs"), help="Directory for output files")
    parser.add_argument("--device", type=str, default="cuda", help="Inference device (cuda/cpu)")
    parser.add_argument("--ckpt", type=str, default=DEFAULT_CKPT, help="Path to model checkpoint")
    parser.add_argument("--mhr", type=str, default=DEFAULT_MHR, help="Path to MHR asset")

    args = parser.parse_args()

    runner = SAM3DStandaloneRunner(
        checkpoint_path=args.ckpt,
        mhr_path=args.mhr,
        device=args.device
    )

    targets = []
    if args.image:
        targets.append(args.image)
    elif args.folder:
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp"]:
            targets.extend(glob.glob(os.path.join(args.folder, ext)))
    else:
        # Default test sample
        default_sample = os.path.join(REPO_ROOT, "notebook", "images", "dancing.jpg")
        if os.path.exists(default_sample):
            targets.append(default_sample)

    print(f"[SAM3D] Found {len(targets)} image(s) to process.")
    results = []
    for img_p in targets:
        res = runner.process_image(img_p, args.output_dir)
        if res:
            results.append(res)

    print("\n==========================================")
    print(f"[SAM3D] All done! Successfully processed {len(results)} images.")
    print(f"[SAM3D] Outputs saved in: {args.output_dir}")

if __name__ == "__main__":
    main()
