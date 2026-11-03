import os
import json
from datetime import datetime
import numpy as np

from pose_core.mhr_adapter import standardize_mhr_raw
from pose_core.schema import to_json_compatible
from pose_core.math3d import q_normalize, cam_rot_to_maya_rot, cam_pos_to_maya

def rotmat_to_quaternion(rot_mats):
    """
    Convert (N, 3, 3) rotation matrices to (N, 4) quaternions [x, y, z, w].
    """
    try:
        from scipy.spatial.transform import Rotation as R
        quats = []
        for mat in rot_mats:
            try:
                r = R.from_matrix(mat)
                quats.append(r.as_quat().tolist())
            except Exception:
                quats.append([0.0, 0.0, 0.0, 1.0])
        return quats
    except ImportError:
        # Fallback to pure math3d
        from pose_core.math3d import mat3_to_q
        return [mat3_to_q(m) for m in rot_mats]

def compute_local_rotations(global_rot_mats, parent_indices):
    """
    Compute local relative rotations from global rotation matrices.
    R_local[i] = R_global[parent[i]]^T @ R_global[i]
    """
    n = len(global_rot_mats)
    local_rot_mats = np.zeros_like(global_rot_mats)
    for i in range(n):
        parent_idx = parent_indices[i]
        if parent_idx < 0 or parent_idx >= n:
            local_rot_mats[i] = global_rot_mats[i]
        else:
            r_parent_inv = global_rot_mats[parent_idx].T
            local_rot_mats[i] = np.matmul(r_parent_inv, global_rot_mats[i])
    return local_rot_mats

def export_standard_skeleton_and_raw(
    output_dict,
    image_path,
    output_dir,
    base_name=None,
    skeleton_def=None,
    bbox=None
):
    """
    Saves export files:
    1. <basename>_raw_mhr.npz: Full uncompressed/raw model output
    2. <basename>_skeleton.json: Normalized standard skeleton (legacy Phase 1 compatible)
    3. <basename>_pose_v2.json: Standard PoseSample v2 format
    """
    os.makedirs(output_dir, exist_ok=True)
    if base_name is None:
        base_name = os.path.splitext(os.path.basename(image_path))[0]

    now_iso = datetime.now().isoformat()

    # 1. Save Raw NPZ
    raw_npz_path = os.path.join(output_dir, f"{base_name}_raw_mhr.npz")
    npz_data = {}
    for k, v in output_dict.items():
        if isinstance(v, np.ndarray):
            npz_data[k] = v
        elif isinstance(v, (int, float, bool)):
            npz_data[k] = np.array(v)
    np.savez_compressed(raw_npz_path, **npz_data)

    # 2. Build PoseSample v2 using pose_core.mhr_adapter
    pose_v2_sample, pose_v2_dict = standardize_mhr_raw(
        output_dict=output_dict,
        image_path=image_path,
        bbox=bbox
    )
    v2_json_path = os.path.join(output_dir, f"{base_name}_pose_v2.json")
    with open(v2_json_path, "w", encoding="utf-8") as f:
        json.dump(pose_v2_dict, f, indent=2, ensure_ascii=False)

    # 3. Build Standard Legacy Phase 1 Skeleton JSON for backward compatibility
    joint_coords = output_dict.get("pred_joint_coords") # (127, 3)
    global_rots = output_dict.get("pred_global_rots")   # (127, 3, 3)
    cam_t = output_dict.get("pred_cam_t")               # (3,)
    focal_length = float(output_dict.get("focal_length", 1000.0))
    global_rot = output_dict.get("global_rot")          # (3,)
    body_pose = output_dict.get("body_pose_params")     # (133,)
    hand_pose = output_dict.get("hand_pose_params")     # (108,)
    keypoints_3d = output_dict.get("pred_keypoints_3d") # (70, 3)
    keypoints_2d = output_dict.get("pred_keypoints_2d") # (70, 2)

    parent_indices = []
    rest_offsets = []
    joint_names = []

    if skeleton_def is not None:
        parent_indices = skeleton_def.get("parent_indices", [])
        rest_offsets = skeleton_def.get("rest_offsets", [])
        joint_names = skeleton_def.get("joint_names", [])

    if not parent_indices and joint_coords is not None:
        parent_indices = [-1] + list(range(len(joint_coords) - 1))
    if not joint_names and joint_coords is not None:
        joint_names = [f"mhr_joint_{i:03d}" for i in range(len(joint_coords))]

    local_quats = []
    global_quats = []
    if global_rots is not None:
        local_rots = compute_local_rotations(global_rots, parent_indices)
        local_quats = rotmat_to_quaternion(local_rots)
        global_quats = rotmat_to_quaternion(global_rots)

    legacy_skeleton = {
        "metadata": {
            "source_image": os.path.abspath(image_path) if image_path else "",
            "source_model": "facebook/sam-3d-body-dinov3",
            "coordinate_system": "camera_frame (X-right, Y-down, Z-forward)",
            "units": "meters",
            "timestamp": now_iso,
            "phase": "Phase 2 - Rig Retargeting Engine"
        },
        "camera": {
            "focal_length": focal_length,
            "pred_cam_t": cam_t.tolist() if cam_t is not None else [0.0, 0.0, 2.5]
        },
        "root_transform": {
            "translation": cam_t.tolist() if cam_t is not None else [0.0, 0.0, 2.5],
            "global_rot_axis_angle": global_rot.tolist() if global_rot is not None else [0.0, 0.0, 0.0]
        },
        "skeleton": {
            "num_joints": len(joint_coords) if joint_coords is not None else 0,
            "joint_names": joint_names,
            "parent_indices": parent_indices,
            "rest_offsets": rest_offsets,
            "world_positions": joint_coords.tolist() if joint_coords is not None else [],
            "local_quaternions_xyzw": local_quats,
            "global_quaternions_xyzw": global_quats
        },
        "keypoints_70": {
            "pred_keypoints_3d": keypoints_3d.tolist() if keypoints_3d is not None else [],
            "pred_keypoints_2d": keypoints_2d.tolist() if keypoints_2d is not None else []
        },
        "pose_parameters": {
            "body_pose_params": body_pose.tolist() if body_pose is not None else [],
            "hand_pose_params": hand_pose.tolist() if hand_pose is not None else []
        }
    }

    legacy_json_path = os.path.join(output_dir, f"{base_name}_skeleton.json")
    with open(legacy_json_path, "w", encoding="utf-8") as f:
        json.dump(to_json_compatible(legacy_skeleton), f, indent=2, ensure_ascii=False)

    return raw_npz_path, legacy_json_path
