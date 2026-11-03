"""
retarget.calibration
===================
Pose and controller calibration between Source Skeleton (MHR 127) and Target Character Rig.
Handles:
  - Source T-Pose <-> Target A-Pose / Rest Pose delta rotations
  - Controller-to-joint spatial and orientation offsets
  - Limb length and pelvic height ratio extraction
  - Bi-directional sync with RigProfile
"""

import math
from typing import Dict, List, Optional, Tuple, Any

from pose_core.math3d import (
    q_identity, q_multiply, q_inverse, q_normalize, q_from_axis_angle,
    q_rotate_vector, v_sub, v_length, v_dist, v_add, v_scale
)
from pose_core.schema import SkeletonDefinition, RigProfile


class RigCalibrator:
    """
    Computes calibration transforms and offsets to ensure:
    1. Neutral source pose maps exactly to neutral target character pose.
    2. Controllers are driven with proper spatial offsets.
    3. Proportion scaling uses reference lengths, not momentary squat lengths.
    """

    def __init__(self, source_def: SkeletonDefinition, rig_profile: RigProfile):
        self.source_def = source_def
        self.rig_profile = rig_profile

        # Cache reference lengths
        self.source_hip_height = float(getattr(source_def, "reference_hip_height", 92.4))
        self.target_hip_height = float(getattr(rig_profile, "target_hip_height", 92.4))

        # Joint rest rotations (quaternions)
        self.joint_calib_rotations: Dict[str, List[float]] = dict(
            getattr(rig_profile, "calibration_rotations", {})
        )

        # Controller offsets (position and rotation)
        self.controller_offsets: Dict[str, Dict[str, Any]] = dict(
            getattr(rig_profile, "control_offsets", {})
        )

        # Target limb lengths and anchors
        self.target_limb_lengths: Dict[str, List[float]] = dict(
            getattr(rig_profile, "target_limb_lengths", {})
        )
        self.target_chain_anchors: Dict[str, List[float]] = dict(
            getattr(rig_profile, "target_chain_anchors", {})
        )

    def set_target_hip_height(self, height_cm: float):
        if height_cm > 1.0:
            self.target_hip_height = float(height_cm)
            self.rig_profile.target_hip_height = float(height_cm)

    def get_hip_height_ratio(self) -> float:
        """Ratio used to scale pelvic displacement from reference pose."""
        return self.target_hip_height / max(self.source_hip_height, 0.001)

    def register_controller_bind_pose(
        self,
        control_name: str,
        bind_pos_ws: List[float],
        bind_rot_ws: List[float],
        joint_pos_ws: List[float],
        joint_rot_ws: List[float]
    ):
        """
        Calibrates the spatial relationship between a rig controller and its driven joint at bind pose.
        """
        pos_offset = v_sub(bind_pos_ws, joint_pos_ws)
        rot_offset = q_multiply(q_normalize(bind_rot_ws), q_inverse(q_normalize(joint_rot_ws)))

        entry = {
            "pos_offset": [float(x) for x in pos_offset],
            "rot_offset": [float(x) for x in rot_offset],
            "bind_pos": [float(x) for x in bind_pos_ws],
            "bind_rot": [float(x) for x in bind_rot_ws]
        }
        self.controller_offsets[control_name] = entry
        self.rig_profile.control_offsets[control_name] = entry

    def get_controller_offset(self, control_name: str) -> Optional[Dict[str, Any]]:
        return self.controller_offsets.get(control_name)

    def get_chain_calib_rotation(self, chain_id: str, control_name: str = "") -> List[float]:
        """
        Returns the calibration quaternion for a chain or control (e.g. A-to-T pose delta).
        """
        if control_name and control_name in self.joint_calib_rotations:
            return list(self.joint_calib_rotations[control_name])
        if chain_id in self.joint_calib_rotations:
            return list(self.joint_calib_rotations[chain_id])
        return q_identity()

    def calibrate_a_pose_to_t_pose(
        self,
        chain_id: str,
        delta_degrees: float = 45.0,
        axis: str = "z"
    ):
        """
        A-pose arms typically angled down ~45 deg relative to T-pose.
        Registers the delta calibration so that source T-pose maps to target A-pose.
        For left arm, down rotation is negative angle around Z (or specified axis).
        """
        axis_lower = axis.lower()
        if axis_lower == "x":
            v_axis = [1.0, 0.0, 0.0]
        elif axis_lower == "y":
            v_axis = [0.0, 1.0, 0.0]
        else:
            v_axis = [0.0, 0.0, 1.0]

        # In standard coordinates, left arm rotates around -Z, right arm around +Z
        sign = -1.0 if "left" in chain_id else 1.0
        rad = math.radians(delta_degrees * sign)
        q_delta = q_from_axis_angle(v_axis, rad)

        self.joint_calib_rotations[chain_id] = q_delta
        self.rig_profile.calibration_rotations[chain_id] = q_delta

    def set_target_limb_geometry(
        self,
        chain_id: str,
        upper_len: float,
        lower_len: float,
        anchor_ws: Optional[List[float]] = None
    ):
        """
        Registers actual target character limb lengths (L1, L2) and chain anchor.
        """
        lens = [float(upper_len), float(lower_len)]
        self.target_limb_lengths[chain_id] = lens
        self.rig_profile.target_limb_lengths[chain_id] = lens
        if anchor_ws is not None:
            anc = [float(x) for x in anchor_ws]
            self.target_chain_anchors[chain_id] = anc
            self.rig_profile.target_chain_anchors[chain_id] = anc

    def get_target_limb_lengths(self, chain_id: str, fallback_len: float) -> Tuple[float, float]:
        if chain_id in self.target_limb_lengths and len(self.target_limb_lengths[chain_id]) >= 2:
            return self.target_limb_lengths[chain_id][0], self.target_limb_lengths[chain_id][1]
        half = fallback_len * 0.5
        return half, half

    def get_target_chain_anchor(self, chain_id: str, fallback_pos: List[float]) -> List[float]:
        if chain_id in self.target_chain_anchors:
            return list(self.target_chain_anchors[chain_id])
        return list(fallback_pos)

    def get_ik_control_world_target(
        self,
        control_name: str,
        target_joint_ws_pos: List[float],
        target_joint_ws_rot: Optional[List[float]] = None
    ) -> Tuple[List[float], List[float]]:
        """
        Computes the target world transform for an IK controller based on calibrated offsets.
        """
        offset_info = self.controller_offsets.get(control_name)
        if offset_info is None:
            return (
                list(target_joint_ws_pos),
                list(target_joint_ws_rot) if target_joint_ws_rot is not None else q_identity()
            )

        pos_offset = offset_info["pos_offset"]
        rot_offset = offset_info["rot_offset"]

        if target_joint_ws_rot is not None:
            norm_rot = q_normalize(target_joint_ws_rot)
            rotated_pos_offset = q_rotate_vector(norm_rot, pos_offset)
            ctrl_pos = v_add(target_joint_ws_pos, rotated_pos_offset)
            ctrl_rot = q_multiply(rot_offset, norm_rot)
        else:
            ctrl_pos = v_add(target_joint_ws_pos, pos_offset)
            ctrl_rot = offset_info.get("bind_rot", q_identity())

        return ctrl_pos, ctrl_rot
