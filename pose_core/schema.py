"""
pose_core.schema
================
Data contracts and schema definitions for Pose2maya (v2).
Provides typed, validated data containers for Skeletons, Poses, Profiles, and Reports.
"""

import math
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Union
from datetime import datetime

from .math3d import q_norm, fk_reconstruct, v_length


def to_json_compatible(obj: Any) -> Any:
    """
    Recursively converts numpy numbers/arrays and dataclass objects into native JSON-serializable types.
    Preserves boolean types without converting to 0/1. Raises ValueError on non-finite floats (NaN/Inf).
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(f"Non-finite float value encountered during serialization: {obj}")
        return obj
    try:
        import numpy as np
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        if isinstance(obj, (np.floating, float)):
            val = float(obj)
            if not math.isfinite(val):
                raise ValueError(f"Non-finite float value encountered during serialization: {val}")
            return val
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return to_json_compatible(obj.tolist())
    except ImportError:
        pass

    if isinstance(obj, int):
        return obj
    if isinstance(obj, str) or obj is None:
        return obj
    if isinstance(obj, (list, tuple)):
        return [to_json_compatible(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): to_json_compatible(v) for k, v in obj.items()}
    if hasattr(obj, "__dataclass_fields__"):
        return to_json_compatible(asdict(obj))
    return obj


@dataclass
class SkeletonDefinition:
    """
    Standard definition of a humanoid skeleton hierarchy and rest pose.
    All lengths in centimeters (cm), coordinate frame: Y-up, +Z forward.
    """
    schema_version: str = "2.0"
    skeleton_id: str = "mhr_127"
    num_joints: int = 127
    parent_indices: List[int] = field(default_factory=list)
    joint_names: List[str] = field(default_factory=list)
    rest_translations: List[List[float]] = field(default_factory=list)  # (N, 3) cm
    rest_rotations: List[List[float]] = field(default_factory=list)      # (N, 4) quaternions [x, y, z, w]
    rest_world_positions: List[List[float]] = field(default_factory=list)  # (N, 3) cm
    reference_hip_height: float = 92.4  # cm from ground
    chains: Dict[str, List[int]] = field(default_factory=dict)
    units: str = "cm"
    up_axis: str = "+Y"
    forward_axis: str = "+Z"

    def validate(self) -> List[str]:
        errors = []
        n = self.num_joints
        if len(self.parent_indices) != n:
            errors.append(f"parent_indices length ({len(self.parent_indices)}) != num_joints ({n})")
        if len(self.joint_names) != n:
            errors.append(f"joint_names length ({len(self.joint_names)}) != num_joints ({n})")
        if len(self.rest_translations) != n:
            errors.append(f"rest_translations length ({len(self.rest_translations)}) != num_joints ({n})")
        if len(self.rest_rotations) != n:
            errors.append(f"rest_rotations length ({len(self.rest_rotations)}) != num_joints ({n})")

        # Check for DAG and parent bounds and cycles
        for i, p in enumerate(self.parent_indices):
            if p >= n:
                errors.append(f"Joint {i} parent index {p} >= num_joints {n}")
            if p == i:
                errors.append(f"Joint {i} is its own parent (loop detected)")
            elif p >= 0:
                # Cycle check: trace ancestor chain
                curr = p
                visited_in_chain = {i}
                while curr >= 0 and curr < n:
                    if curr in visited_in_chain:
                        errors.append(f"Cycle detected involving joint {curr}")
                        break
                    visited_in_chain.add(curr)
                    curr = self.parent_indices[curr]

        # Check rest_translations finite numbers
        for i, t in enumerate(self.rest_translations):
            if len(t) != 3 or any(not math.isfinite(float(x)) for x in t):
                errors.append(f"Joint {i} rest_translation must be 3 finite floats: {t}")

        # Check quaternion normalization and finiteness
        for i, q in enumerate(self.rest_rotations):
            if len(q) != 4 or any(not math.isfinite(float(x)) for x in q):
                errors.append(f"Joint {i} rest quaternion must be 4 finite floats: {q}")
                continue
            qn = q_norm(q)
            if qn < 1e-4:
                errors.append(f"Joint {i} rest quaternion has zero or near-zero norm: {qn:.4f}")
            elif abs(qn - 1.0) > 0.05:
                errors.append(f"Joint {i} rest quaternion has invalid norm: {qn:.4f}")

        return errors

    def compute_rest_world_positions(self):
        w_pos, _ = fk_reconstruct(
            self.parent_indices,
            self.rest_translations,
            self.rest_rotations
        )
        self.rest_world_positions = w_pos
        return w_pos

    def to_dict(self) -> Dict[str, Any]:
        return to_json_compatible(asdict(self))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SkeletonDefinition":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PoseSample:
    """
    Normalized 3D Pose sample (v2).
    Authoritative inputs: local_rotations, root_translation, root_rotation.
    World coordinates: Centimeters (cm), Y-up, +Z forward.
    """
    schema_version: str = "2.0"
    skeleton_id: str = "mhr_127"
    source_image: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    bbox: Optional[List[float]] = None  # [x, y, w, h] in original image space
    root_translation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])  # cm
    root_rotation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 1.0]) # [x, y, z, w]
    local_rotations: List[List[float]] = field(default_factory=list)  # (N, 4)
    world_positions: List[List[float]] = field(default_factory=list)  # (N, 3) cm (for diagnostic / IK)
    camera: Optional[Dict[str, Any]] = None  # focal_length, cam_t (isolated from root motion)
    keypoints_2d: Optional[List[List[float]]] = None  # (70, 2)
    confidence: Optional[List[float]] = None

    def validate(self, expected_joints: int = 127) -> List[str]:
        errors = []
        if self.schema_version != "2.0":
            errors.append(f"Unsupported schema_version '{self.schema_version}' (expected '2.0')")
        if self.skeleton_id != "mhr_127":
            errors.append(f"Unsupported or mismatched skeleton_id '{self.skeleton_id}' (expected 'mhr_127')")

        if len(self.local_rotations) != expected_joints:
            errors.append(f"local_rotations count ({len(self.local_rotations)}) != expected ({expected_joints})")
        for i, q in enumerate(self.local_rotations):
            if len(q) != 4 or any(not math.isfinite(float(x)) for x in q):
                errors.append(f"Joint {i} local_rotation has non-finite or invalid length: {q}")
                continue
            qn = q_norm(q)
            if qn < 1e-4:
                errors.append(f"Joint {i} local_rotation quaternion has near-zero norm: {qn:.4f}")
            elif abs(qn - 1.0) > 0.05:
                errors.append(f"Joint {i} local_rotation quaternion has invalid norm: {qn:.4f}")

        if self.world_positions:
            if len(self.world_positions) != expected_joints:
                errors.append(f"world_positions count ({len(self.world_positions)}) != expected ({expected_joints})")
            for i, p in enumerate(self.world_positions):
                if len(p) != 3 or any(not math.isfinite(float(x)) for x in p):
                    errors.append(f"Joint {i} world_position must be 3 finite floats: {p}")

        if len(self.root_translation) != 3 or any(not math.isfinite(float(x)) for x in self.root_translation):
            errors.append(f"root_translation must be 3 finite floats: {self.root_translation}")

        if len(self.root_rotation) != 4 or any(not math.isfinite(float(x)) for x in self.root_rotation):
            errors.append(f"root_rotation must be 4 finite floats: {self.root_rotation}")
        else:
            qn = q_norm(self.root_rotation)
            if qn < 1e-4 or abs(qn - 1.0) > 0.05:
                errors.append(f"root_rotation quaternion norm invalid: {qn:.4f}")

        if self.bbox is not None:
            if len(self.bbox) != 4 or any(not math.isfinite(float(x)) for x in self.bbox):
                errors.append(f"bbox must be 4 finite floats: {self.bbox}")

        if self.camera is not None:
            fl = self.camera.get("focal_length")
            if fl is not None and (not math.isfinite(float(fl)) or float(fl) <= 0):
                errors.append(f"camera focal_length must be a positive finite float: {fl}")
            cam_t = self.camera.get("pred_cam_t")
            if cam_t is not None and (len(cam_t) != 3 or any(not math.isfinite(float(x)) for x in cam_t)):
                errors.append(f"camera pred_cam_t must be 3 finite floats: {cam_t}")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        return to_json_compatible(asdict(self))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PoseSample":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class RigChain:
    """
    Definition of a controllable kinematic limb or spine chain on a character rig.
    """
    chain_id: str                          # e.g. "left_arm", "spine", "left_leg"
    chain_type: str = "fk_ik"              # "fk", "ik", "fk_ik"
    target_joints: List[str] = field(default_factory=list)
    fk_controls: List[str] = field(default_factory=list)
    ik_control: Optional[str] = None
    pole_vector_control: Optional[str] = None
    fk_ik_switch_attr: Optional[str] = None
    fk_value: float = 0.0
    ik_value: float = 10.0


@dataclass
class RigProfile:
    """
    Profile representing character rig architecture, controller mappings, and calibration spaces.
    """
    character_id: str = "default_character"
    name: str = "Default Character Rig"
    root_node: str = "Root_M"
    pelvis_node: str = "RootX_M"
    chains: Dict[str, RigChain] = field(default_factory=dict)
    control_offsets: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    calibration_rotations: Dict[str, List[float]] = field(default_factory=dict)
    target_hip_height: float = 92.4
    target_limb_lengths: Dict[str, List[float]] = field(default_factory=dict)
    target_chain_anchors: Dict[str, List[float]] = field(default_factory=dict)
    rotation_orders: Dict[str, str] = field(default_factory=dict)
    stretch_handling: str = "preserve"

    def validate(self) -> List[str]:
        errors = []
        if not self.character_id or not isinstance(self.character_id, str):
            errors.append("RigProfile character_id must be a non-empty string.")
        if not self.pelvis_node or not isinstance(self.pelvis_node, str):
            errors.append("RigProfile pelvis_node must be a non-empty string.")
        if not isinstance(self.chains, dict):
            errors.append("RigProfile chains must be a dictionary.")
        else:
            for cid, chain in self.chains.items():
                if not isinstance(chain, RigChain):
                    errors.append(f"Chain '{cid}' must be a RigChain instance.")
                elif not chain.chain_id:
                    errors.append(f"Chain '{cid}' must have a valid chain_id.")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return to_json_compatible(asdict(self))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RigProfile":
        chains_raw = d.get("chains", {})
        chains_parsed = {}
        for k, v in chains_raw.items():
            if isinstance(v, dict):
                chains_parsed[k] = RigChain(**v)
            else:
                chains_parsed[k] = v
        d_copy = dict(d)
        d_copy["chains"] = chains_parsed
        return cls(**{k: v for k, v in d_copy.items() if k in cls.__dataclass_fields__})


@dataclass
class RetargetProfile:
    """
    Retargeting rules and operation weights between a source skeleton and target rig.
    """
    profile_id: str = "default_retarget"
    source_skeleton_id: str = "mhr_127"
    target_rig_id: str = "advanced_skeleton_5"
    chain_modes: Dict[str, str] = field(default_factory=lambda: {
        "spine": "fk",
        "neck_head": "fk",
        "left_arm": "ik",
        "right_arm": "ik",
        "left_leg": "ik",
        "right_leg": "ik"
    })
    chain_weights: Dict[str, float] = field(default_factory=lambda: {
        "pelvis": 1.0,
        "spine": 1.0,
        "neck_head": 1.0,
        "left_arm": 1.0,
        "right_arm": 1.0,
        "left_leg": 1.0,
        "right_leg": 1.0
    })
    root_motion_mode: str = "in_place"  # "in_place" (default), "pelvis_only", "full"
    pelvis_scale_policy: str = "hip_ratio"  # "hip_ratio", "absolute", "none"
    ground_contact: bool = False
    ground_height: float = 0.0
    contact_legs: Dict[str, bool] = field(default_factory=lambda: {
        "left_leg": True,
        "right_leg": True
    })
    part_mask: Dict[str, bool] = field(default_factory=lambda: {
        "pelvis": True,
        "spine": True,
        "neck_head": True,
        "left_arm": True,
        "right_arm": True,
        "left_leg": True,
        "right_leg": True
    })

    def to_dict(self) -> Dict[str, Any]:
        return to_json_compatible(asdict(self))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RetargetProfile":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class RetargetResult:
    """
    Output of the retargeting calculation engine before applying to Maya.
    """
    success: bool = True
    target_transforms: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    ik_goals: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    mode_switches: Dict[str, float] = field(default_factory=dict)
    residuals: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class WritePlan:
    """
    Transaction plan for Maya writing, checked beforehand.
    """
    can_apply: bool = True
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    channels: List[Dict[str, Any]] = field(default_factory=list)  # [{"node", "attr", "current", "target", "keyframe"}]
    mode_switches: List[Dict[str, Any]] = field(default_factory=list) # [{"attr", "current", "target"}]


@dataclass
class ApplyReport:
    """
    Result of a Maya session commit, preview, or cancel.
    """
    status: str = "success"  # "success", "partial", "failed", "cancelled"
    channels_modified: int = 0
    modified_list: List[str] = field(default_factory=list)
    keyframes_set: int = 0
    undo_available: bool = True
    messages: List[str] = field(default_factory=list)
