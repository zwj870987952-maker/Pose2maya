"""
retarget.profiles
=================
Storage, preset library, and namespace resolution for RigProfile and RetargetProfile.
"""

import os
import json
from typing import Dict, List, Optional, Any

from pose_core.schema import RigProfile, RigChain, RetargetProfile

PROFILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profiles")


def resolve_node_name(base_name: str, namespace: str = "") -> str:
    """
    Appends namespace prefix if provided, handles existing prefixes safely.
    """
    if not base_name:
        return ""
    if not namespace:
        return base_name
    ns = namespace.rstrip(":") + ":"
    if base_name.startswith(ns):
        return base_name
    return f"{ns}{base_name}"


# -----------------------------------------------------------------------------
# Standard Built-in Presets
# -----------------------------------------------------------------------------

def get_preset_as5() -> RigProfile:
    """Advanced Skeleton 5 standard humanoid biped profile."""
    chains = {
        "spine": RigChain(
            chain_id="spine",
            chain_type="fk",
            target_joints=["spine_01", "spine_02", "spine_03", "spine_04_chest"],
            fk_controls=["FKSpine1_M", "FKChest_M"]
        ),
        "neck_head": RigChain(
            chain_id="neck_head",
            chain_type="fk",
            target_joints=["neck_01", "head"],
            fk_controls=["FKNeck_M", "FKHead_M"]
        ),
        "left_arm": RigChain(
            chain_id="left_arm",
            chain_type="fk_ik",
            target_joints=["l_clavicle", "l_upperarm", "l_lowerarm", "l_hand"],
            fk_controls=["FKScapula_L", "FKShoulder_L", "FKElbow_L", "FKWrist_L"],
            ik_control="IKArm_L",
            pole_vector_control="PoleArm_L",
            fk_ik_switch_attr="FKIKArm_L.FKIKBlend",
            fk_value=0.0,
            ik_value=10.0
        ),
        "right_arm": RigChain(
            chain_id="right_arm",
            chain_type="fk_ik",
            target_joints=["r_clavicle", "r_upperarm", "r_lowerarm", "r_hand"],
            fk_controls=["FKScapula_R", "FKShoulder_R", "FKElbow_R", "FKWrist_R"],
            ik_control="IKArm_R",
            pole_vector_control="PoleArm_R",
            fk_ik_switch_attr="FKIKArm_R.FKIKBlend",
            fk_value=0.0,
            ik_value=10.0
        ),
        "left_leg": RigChain(
            chain_id="left_leg",
            chain_type="fk_ik",
            target_joints=["l_thigh", "l_calf", "l_foot"],
            fk_controls=["FKHip_L", "FKKnee_L", "FKAnkle_L"],
            ik_control="IKLeg_L",
            pole_vector_control="PoleLeg_L",
            fk_ik_switch_attr="FKIKLeg_L.FKIKBlend",
            fk_value=0.0,
            ik_value=10.0
        ),
        "right_leg": RigChain(
            chain_id="right_leg",
            chain_type="fk_ik",
            target_joints=["r_thigh", "r_calf", "r_foot"],
            fk_controls=["FKHip_R", "FKKnee_R", "FKAnkle_R"],
            ik_control="IKLeg_R",
            pole_vector_control="PoleLeg_R",
            fk_ik_switch_attr="FKIKLeg_R.FKIKBlend",
            fk_value=0.0,
            ik_value=10.0
        )
    }

    return RigProfile(
        character_id="advanced_skeleton_5",
        name="Advanced Skeleton 5 Biped",
        root_node="Root_M",
        pelvis_node="RootX_M",
        chains=chains,
        stretch_handling="preserve"
    )


def get_preset_pure_joints_ue5() -> RigProfile:
    """Pure joint deformation skeleton with UE5 Mannequin naming convention."""
    chains = {
        "spine": RigChain(
            chain_id="spine",
            chain_type="fk",
            target_joints=["spine_01", "spine_02", "spine_03", "spine_04"],
            fk_controls=["spine_01", "spine_02", "spine_03", "spine_04"]
        ),
        "neck_head": RigChain(
            chain_id="neck_head",
            chain_type="fk",
            target_joints=["neck_01", "head"],
            fk_controls=["neck_01", "head"]
        ),
        "left_arm": RigChain(
            chain_id="left_arm",
            chain_type="fk",
            target_joints=["clavicle_l", "upperarm_l", "lowerarm_l", "hand_l"],
            fk_controls=["clavicle_l", "upperarm_l", "lowerarm_l", "hand_l"]
        ),
        "right_arm": RigChain(
            chain_id="right_arm",
            chain_type="fk",
            target_joints=["clavicle_r", "upperarm_r", "lowerarm_r", "hand_r"],
            fk_controls=["clavicle_r", "upperarm_r", "lowerarm_r", "hand_r"]
        ),
        "left_leg": RigChain(
            chain_id="left_leg",
            chain_type="fk",
            target_joints=["thigh_l", "calf_l", "foot_l", "ball_l"],
            fk_controls=["thigh_l", "calf_l", "foot_l", "ball_l"]
        ),
        "right_leg": RigChain(
            chain_id="right_leg",
            chain_type="fk",
            target_joints=["thigh_r", "calf_r", "foot_r", "ball_r"],
            fk_controls=["thigh_r", "calf_r", "foot_r", "ball_r"]
        )
    }

    return RigProfile(
        character_id="pure_joints_ue5",
        name="UE5 Mannequin Joints",
        root_node="root",
        pelvis_node="pelvis",
        chains=chains,
        stretch_handling="ignore"
    )


def get_preset_pure_joints_humanik() -> RigProfile:
    """Pure joint deformation skeleton with HumanIK / Mixamo naming convention."""
    chains = {
        "spine": RigChain(
            chain_id="spine",
            chain_type="fk",
            target_joints=["Spine", "Spine1", "Spine2", "Spine3"],
            fk_controls=["Spine", "Spine1", "Spine2", "Spine3"]
        ),
        "neck_head": RigChain(
            chain_id="neck_head",
            chain_type="fk",
            target_joints=["Neck", "Head"],
            fk_controls=["Neck", "Head"]
        ),
        "left_arm": RigChain(
            chain_id="left_arm",
            chain_type="fk",
            target_joints=["LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand"],
            fk_controls=["LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand"]
        ),
        "right_arm": RigChain(
            chain_id="right_arm",
            chain_type="fk",
            target_joints=["RightShoulder", "RightArm", "RightForeArm", "RightHand"],
            fk_controls=["RightShoulder", "RightArm", "RightForeArm", "RightHand"]
        ),
        "left_leg": RigChain(
            chain_id="left_leg",
            chain_type="fk",
            target_joints=["LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase"],
            fk_controls=["LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase"]
        ),
        "right_leg": RigChain(
            chain_id="right_leg",
            chain_type="fk",
            target_joints=["RightUpLeg", "RightLeg", "RightFoot", "RightToeBase"],
            fk_controls=["RightUpLeg", "RightLeg", "RightFoot", "RightToeBase"]
        )
    }

    return RigProfile(
        character_id="pure_joints_humanik",
        name="Maya HumanIK / Mixamo Joints",
        root_node="Hips",
        pelvis_node="Hips",
        chains=chains,
        stretch_handling="ignore"
    )


# -----------------------------------------------------------------------------
# Disk Persistence
# -----------------------------------------------------------------------------

def save_rig_profile(profile: RigProfile, filepath: Optional[str] = None) -> str:
    os.makedirs(PROFILES_DIR, exist_ok=True)
    path = filepath or os.path.join(PROFILES_DIR, f"{profile.character_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)
    return path


def load_rig_profile(filepath_or_id: str) -> RigProfile:
    path = filepath_or_id
    if not os.path.exists(path) and not path.endswith(".json"):
        candidate = os.path.join(PROFILES_DIR, f"{filepath_or_id}.json")
        if os.path.exists(candidate):
            path = candidate

    if not os.path.exists(path):
        # Fall back to built-in presets
        if "as5" in filepath_or_id.lower() or "advanced" in filepath_or_id.lower():
            return get_preset_as5()
        elif "ue5" in filepath_or_id.lower():
            return get_preset_pure_joints_ue5()
        elif "humanik" in filepath_or_id.lower() or "hik" in filepath_or_id.lower():
            return get_preset_pure_joints_humanik()
        raise FileNotFoundError(f"RigProfile file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return RigProfile.from_dict(data)


def save_retarget_profile(profile: RetargetProfile, filepath: Optional[str] = None) -> str:
    os.makedirs(PROFILES_DIR, exist_ok=True)
    path = filepath or os.path.join(PROFILES_DIR, f"{profile.profile_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)
    return path


def load_retarget_profile(filepath_or_id: str) -> RetargetProfile:
    path = filepath_or_id
    if not os.path.exists(path) and not path.endswith(".json"):
        candidate = os.path.join(PROFILES_DIR, f"{filepath_or_id}.json")
        if os.path.exists(candidate):
            path = candidate

    if not os.path.exists(path):
        return RetargetProfile(profile_id=filepath_or_id)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return RetargetProfile.from_dict(data)


def export_default_presets():
    """Generates all default profile JSON files into profiles/ directory."""
    save_rig_profile(get_preset_as5())
    save_rig_profile(get_preset_pure_joints_ue5())
    save_rig_profile(get_preset_pure_joints_humanik())
    save_retarget_profile(RetargetProfile(
        profile_id="default_retarget",
        source_skeleton_id="mhr_127",
        target_rig_id="advanced_skeleton_5"
    ))
