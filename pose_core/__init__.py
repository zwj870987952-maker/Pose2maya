"""
pose_core
=========
Core mathematical and data contracts for 3D human pose processing and retargeting.
"""

from .math3d import (
    v_add, v_sub, v_scale, v_dot, v_cross, v_length, v_norm, v_dist,
    q_identity, q_norm, q_normalize, q_inverse, q_multiply, q_rotate_vector,
    q_from_axis_angle, q_to_axis_angle, q_from_two_vectors, q_slerp, q_angle_between, q_dot,
    q_to_mat3, mat3_to_q, euler_to_q, q_to_euler_deg,
    cam_pos_to_maya, maya_pos_to_cam, cam_rot_to_maya_rot, maya_rot_to_cam_rot,
    fk_reconstruct
)
from .schema import (
    SkeletonDefinition, PoseSample, RigChain, RigProfile, RetargetProfile,
    RetargetResult, WritePlan, ApplyReport, to_json_compatible
)
from .mhr_adapter import (
    get_authoritative_mhr_skeleton_def,
    load_legacy_skeleton_json,
    load_pose_sample,
    standardize_mhr_raw
)

__all__ = [
    "v_add", "v_sub", "v_scale", "v_dot", "v_cross", "v_length", "v_norm", "v_dist",
    "q_identity", "q_norm", "q_normalize", "q_inverse", "q_multiply", "q_rotate_vector",
    "q_from_axis_angle", "q_to_axis_angle", "q_from_two_vectors", "q_slerp", "q_angle_between", "q_dot",
    "q_to_mat3", "mat3_to_q", "euler_to_q", "q_to_euler_deg",
    "cam_pos_to_maya", "maya_pos_to_cam", "cam_rot_to_maya_rot", "maya_rot_to_cam_rot",
    "fk_reconstruct",
    "SkeletonDefinition", "PoseSample", "RigChain", "RigProfile", "RetargetProfile",
    "RetargetResult", "WritePlan", "ApplyReport", "to_json_compatible",
    "get_authoritative_mhr_skeleton_def",
    "load_legacy_skeleton_json",
    "load_pose_sample",
    "standardize_mhr_raw"
]
