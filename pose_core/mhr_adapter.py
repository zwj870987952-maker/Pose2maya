"""
pose_core.mhr_adapter
=====================
Data adapter for MHR (Meta Human Rig) 127-joint skeleton model and Legacy Phase 1 JSONs.
Provides authoritative skeleton definitions and conversions to normalized PoseSample v2.

Coordinate Standards:
  - World space: Centimeters (cm), Y-up, +Z forward.
  - Camera frame: Meters (m), X-right, Y-down, Z-forward.
  - Basis conversion:
      P = diag(1, -1, -1)
      p_maya = [x_cam * 100, -y_cam * 100, -z_cam * 100]
  - MHR Native Rotations:
      MHR estimator produces joint_global_rots in native humanoid Y-up space.
      Local rotations: R_local[i] = R_parent^T @ R_i.
      Legacy root_transform.global_rot_axis_angle is Euler ZYX in radians.
"""

import os
import json
import math
from typing import Dict, Any, List, Optional, Tuple, Union, Sequence
from datetime import datetime

from .schema import SkeletonDefinition, PoseSample, to_json_compatible
from .math3d import (
    q_identity, q_normalize, q_norm, q_inverse, q_multiply, mat3_to_q, mat3_multiply, mat3_transpose,
    cam_pos_to_maya, euler_to_q, fk_reconstruct
)

DEF_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "mhr_skeleton_def.json"
)


# -----------------------------------------------------------------------------
# 1. Authoritative MHR 127 Skeleton Definition
# -----------------------------------------------------------------------------

def get_authoritative_mhr_skeleton_def() -> SkeletonDefinition:
    """
    Returns the authoritative, validated SkeletonDefinition for MHR 127.
    Loads geometry and topological hierarchy from mhr_skeleton_def.json.
    """
    if not os.path.exists(DEF_JSON_PATH):
        raise FileNotFoundError(f"Authoritative skeleton definition not found at: {DEF_JSON_PATH}")

    with open(DEF_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    parent_indices = data.get("parent_indices", [])
    raw_offsets = data.get("rest_offsets", [])
    joint_names = data.get("joint_names", [f"mhr_joint_{i:03d}" for i in range(len(parent_indices))])
    num_joints = len(parent_indices)

    # Standardize rest offsets: ensure cm
    rest_translations = []
    for offset in raw_offsets:
        rest_translations.append([float(offset[0]), float(offset[1]), float(offset[2])])

    # Load authoritative rest rotations
    raw_rest_rots = data.get("rest_rotations")
    if raw_rest_rots and len(raw_rest_rots) == num_joints:
        rest_rotations = [q_normalize(q) for q in raw_rest_rots]
    else:
        # Fallback identity if not yet populated
        rest_rotations = [q_identity() for _ in range(num_joints)]

    # Standard kinematic chains
    chains = data.get("chains", {
        "spine": [0, 1, 34, 35, 36, 37],
        "neck_head": [37, 110, 113],
        "left_arm": [37, 74, 75, 76, 77],
        "right_arm": [37, 38, 39, 40, 41],
        "left_leg": [1, 2, 3, 4],
        "right_leg": [1, 18, 19, 20]
    })

    skel_def = SkeletonDefinition(
        schema_version="2.0",
        skeleton_id="mhr_127",
        num_joints=num_joints,
        parent_indices=parent_indices,
        joint_names=joint_names,
        rest_translations=rest_translations,
        rest_rotations=rest_rotations,
        reference_hip_height=float(data.get("reference_hip_height", 92.3987)),
        chains=chains,
        units="cm",
        up_axis="+Y",
        forward_axis="+Z"
    )

    raw_world_pos = data.get("rest_world_positions")
    if raw_world_pos and len(raw_world_pos) == num_joints:
        skel_def.rest_world_positions = raw_world_pos
    else:
        skel_def.compute_rest_world_positions()

    errors = skel_def.validate()
    if errors:
        raise ValueError(f"Authoritative skeleton definition has validation errors: {errors}")

    return skel_def


# -----------------------------------------------------------------------------
# 2. Unified Pose Reader (v2 and Legacy Dispatcher)
# -----------------------------------------------------------------------------

def load_pose_sample(
    source: Union[str, Dict[str, Any], PoseSample],
    skeleton_def: Optional[SkeletonDefinition] = None
) -> PoseSample:
    """
    Unified entry point for loading human pose data:
      - PoseSample instance: validated and returned.
      - v2 JSON file or dictionary: validated and returned.
      - Legacy Phase 1 *_skeleton.json: converted to v2, validated, and returned.
    Ensures zero data loss (world positions, local rotations, root transform, camera).
    """
    if isinstance(source, PoseSample):
        errors = source.validate()
        if errors:
            raise ValueError(f"PoseSample validation failed: {errors}")
        if not source.world_positions and skeleton_def:
            source.world_positions, _ = fk_reconstruct(
                skeleton_def.parent_indices,
                skeleton_def.rest_translations,
                source.local_rotations,
                root_translation=source.root_translation,
                root_rotation=source.root_rotation
            )
        return source

    if isinstance(source, str):
        if not os.path.exists(source):
            raise FileNotFoundError(f"Pose file not found: {source}")
        with open(source, "r", encoding="utf-8") as f:
            data = json.load(f)
        src_path = os.path.abspath(source)
    elif isinstance(source, dict):
        data = source
        src_path = None
    else:
        raise TypeError(f"Unsupported pose source type: {type(source)}")

    if not isinstance(data, dict):
        raise ValueError("Invalid pose JSON content (must be a dictionary).")

    # Check schema version
    schema_version = str(data.get("schema_version", ""))
    if schema_version == "2.0":
        # Direct v2 format
        sample = PoseSample.from_dict(data)
        if src_path and not sample.source_image:
            sample.source_image = src_path
        errors = sample.validate()
        if errors:
            raise ValueError(f"PoseSample v2 validation failed: {errors}")
        if not sample.world_positions and skeleton_def:
            sample.world_positions, _ = fk_reconstruct(
                skeleton_def.parent_indices,
                skeleton_def.rest_translations,
                sample.local_rotations,
                root_translation=sample.root_translation,
                root_rotation=sample.root_rotation
            )
        return sample

    elif "skeleton" in data:
        # Legacy Phase 1 format
        return _parse_legacy_skeleton_dict(data, src_path, skeleton_def)
    else:
        raise ValueError(
            f"Unrecognized pose format (neither schema_version '2.0' nor legacy 'skeleton' key found): {list(data.keys())}"
        )


def load_legacy_skeleton_json(json_path_or_dict: Union[str, Dict[str, Any]]) -> PoseSample:
    """
    Backward-compatible wrapper delegating to load_pose_sample.
    """
    return load_pose_sample(json_path_or_dict)


def _parse_legacy_skeleton_dict(
    data: Dict[str, Any],
    src_path: Optional[str] = None,
    skeleton_def: Optional[SkeletonDefinition] = None
) -> PoseSample:
    """
    Parses legacy Phase 1 format dictionary to PoseSample v2.
    """
    if skeleton_def is None:
        skeleton_def = get_authoritative_mhr_skeleton_def()

    metadata = data.get("metadata", {})
    skel_data = data.get("skeleton", {})
    raw_positions = skel_data.get("world_positions", [])
    raw_quats = skel_data.get("local_quaternions_xyzw", [])
    cam_data = data.get("camera", {})

    # 1. Convert World Positions: meters (camera frame) -> centimeters (Maya frame)
    world_positions = []
    is_cam_frame = "camera_frame" in metadata.get("coordinate_system", "camera_frame")
    for pos in raw_positions:
        if is_cam_frame:
            world_positions.append(cam_pos_to_maya(pos))
        else:
            world_positions.append([float(pos[0]), float(pos[1]), float(pos[2])])

    # 2. Camera parameters
    camera = {
        "focal_length": float(cam_data.get("focal_length", 1000.0)),
        "pred_cam_t": [float(x) for x in cam_data.get("pred_cam_t", [0.0, 0.0, 2.5])]
    }

    # 3. Root motion & Root Rotation (AUD-03)
    root_t_raw = data.get("root_transform", {}).get("translation")
    if root_t_raw and len(root_t_raw) == 3 and root_t_raw != cam_data.get("pred_cam_t"):
        root_translation = cam_pos_to_maya(root_t_raw) if is_cam_frame else [float(x) for x in root_t_raw]
    else:
        root_translation = [0.0, 0.0, 0.0]

    root_rot_raw = data.get("root_transform", {}).get("global_rot_axis_angle")
    if root_rot_raw and len(root_rot_raw) == 3:
        # Legacy pipeline exported global_rot_euler in radians with ZYX order
        euler_deg = [math.degrees(float(x)) for x in root_rot_raw]
        root_rotation = euler_to_q(euler_deg, order="zyx")
    elif raw_quats:
        root_rotation = q_normalize(raw_quats[0])
    else:
        root_rotation = q_identity()

    # 4. Local Quaternions:
    local_rotations = []
    for i, q in enumerate(raw_quats):
        qn = q_normalize(q)
        if q_norm(qn) < 1e-4:
            raise ValueError(f"Joint {i} in legacy skeleton has near-zero quaternion norm: {q}")
        if i == 0:
            # Joint 0 local rotation is decomposed relative to root_rotation so FK synthesizes once
            q_rel = q_multiply(q_inverse(root_rotation), qn)
            local_rotations.append(q_normalize(q_rel))
        else:
            local_rotations.append(qn)

    # Pad or fill if missing
    expected_n = skeleton_def.num_joints
    while len(local_rotations) < expected_n:
        local_rotations.append(q_identity())

    # If world_positions were missing in legacy file, reconstruct via FK (AUD-11)
    if not world_positions and local_rotations:
        world_positions, _ = fk_reconstruct(
            skeleton_def.parent_indices,
            skeleton_def.rest_translations,
            local_rotations,
            root_translation=root_translation,
            root_rotation=root_rotation
        )

    # 2D Keypoints
    kp70 = data.get("keypoints_70", {})
    kp2d = kp70.get("pred_keypoints_2d")

    ts = metadata.get("timestamp")
    if not ts or ts == "2026-10-11":
        ts = datetime.now().isoformat()

    sample = PoseSample(
        schema_version="2.0",
        skeleton_id="mhr_127",
        source_image=metadata.get("source_image", src_path),
        timestamp=ts,
        bbox=None,
        root_translation=root_translation,
        root_rotation=root_rotation,
        local_rotations=local_rotations,
        world_positions=world_positions,
        camera=camera,
        keypoints_2d=kp2d,
        confidence=None
    )

    errors = sample.validate(expected_joints=expected_n)
    if errors:
        raise ValueError(f"Legacy skeleton conversion produced invalid PoseSample: {errors}")

    return sample


# -----------------------------------------------------------------------------
# 3. Raw Model Output Standardizer (From SAM 3D inference or NPZ)
# -----------------------------------------------------------------------------

def standardize_mhr_raw(
    output_dict: Dict[str, Any],
    image_path: str = "",
    bbox: Optional[Sequence[float]] = None,
    skeleton_def: Optional[SkeletonDefinition] = None
) -> Tuple[PoseSample, Dict[str, Any]]:
    """
    Takes raw output dictionary from SAM 3D Body estimator or NPZ and returns:
    1. Validated PoseSample v2
    2. Dict representation for JSON export (with NumPy serialization safety)

    Coordinate transform:
      - pred_joint_coords: OpenCV camera frame (meters) -> Maya frame (cm) via cam_pos_to_maya.
      - pred_global_rots: Native MHR skeleton space -> local relative rotations R_local = R_p^T @ R_curr.
    """
    if skeleton_def is None:
        skeleton_def = get_authoritative_mhr_skeleton_def()

    joint_coords = output_dict.get("pred_joint_coords")  # (127, 3) in meters, camera frame
    global_rots = output_dict.get("pred_global_rots")      # (127, 3, 3) in native skeleton frame
    cam_t = output_dict.get("pred_cam_t")                  # (3,)
    focal_length = float(output_dict.get("focal_length", 1000.0))
    keypoints_2d = output_dict.get("pred_keypoints_2d")    # (70, 2)

    parent_indices = skeleton_def.parent_indices
    num_joints = skeleton_def.num_joints

    # Convert coordinates: meters (cam) -> centimeters (Maya)
    world_positions = []
    if joint_coords is not None:
        for p in joint_coords:
            world_positions.append(cam_pos_to_maya([float(p[0]), float(p[1]), float(p[2])]))

    # Root rotation (AUD-03)
    global_rot_raw = output_dict.get("global_rot")
    if global_rot_raw is not None and len(global_rot_raw) == 3:
        euler_deg = [math.degrees(float(x)) for x in global_rot_raw]
        root_rot = euler_to_q(euler_deg, order="zyx")
    elif global_rots is not None and len(global_rots) > 0:
        r0 = [[float(global_rots[0][r][c]) for c in range(3)] for r in range(3)]
        root_rot = mat3_to_q(r0)
    else:
        root_rot = q_identity()

    # Convert rotations:
    # R_local[i] = R_parent^T @ R_i
    # Note: global_rots from MHR is in native skeleton space, matching Maya's Y-up orientation.
    local_quats = []
    if global_rots is not None:
        for i in range(num_joints):
            p_idx = parent_indices[i] if i < len(parent_indices) else -1
            r_curr = [[float(global_rots[i][r][c]) for c in range(3)] for r in range(3)]
            if p_idx < 0:
                q_curr = mat3_to_q(r_curr)
                # Joint 0 local rotation relative to root_rot so FK reconstructs once
                q_local = q_multiply(q_inverse(root_rot), q_curr)
                local_quats.append(q_normalize(q_local))
            else:
                r_parent = [[float(global_rots[p_idx][r][c]) for c in range(3)] for r in range(3)]
                r_local = mat3_multiply(mat3_transpose(r_parent), r_curr)
                q = mat3_to_q(r_local)
                local_quats.append(q_normalize(q))
    else:
        local_quats = [q_identity() for _ in range(num_joints)]

    # If world positions missing, reconstruct via FK
    if not world_positions and local_quats:
        world_positions, _ = fk_reconstruct(
            skeleton_def.parent_indices,
            skeleton_def.rest_translations,
            local_quats,
            root_translation=[0.0, 0.0, 0.0],
            root_rotation=root_rot
        )

    # Camera parameters
    camera = {
        "focal_length": focal_length,
        "pred_cam_t": [float(x) for x in cam_t] if cam_t is not None else [0.0, 0.0, 2.5]
    }

    # Format 2D keypoints
    kp2d_list = None
    if keypoints_2d is not None:
        if hasattr(keypoints_2d, "tolist"):
            kp2d_list = keypoints_2d.tolist()
        else:
            kp2d_list = [[float(pt[0]), float(pt[1])] for pt in keypoints_2d]

    sample = PoseSample(
        schema_version="2.0",
        skeleton_id=skeleton_def.skeleton_id,
        source_image=os.path.abspath(image_path) if image_path else None,
        timestamp=datetime.now().isoformat(),
        bbox=[float(x) for x in bbox] if bbox is not None else None,
        root_translation=[0.0, 0.0, 0.0],
        root_rotation=root_rot,
        local_rotations=local_quats,
        world_positions=world_positions,
        camera=camera,
        keypoints_2d=kp2d_list,
        confidence=None
    )

    errors = sample.validate(expected_joints=num_joints)
    if errors:
        raise ValueError(f"standardize_mhr_raw produced invalid PoseSample: {errors}")

    return sample, sample.to_dict()
