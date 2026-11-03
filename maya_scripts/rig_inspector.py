"""
maya_scripts.rig_inspector
==========================
Inspects active Maya scene DAG, character namespaces, node types, and attribute capabilities.
Runs in Maya environment (cmds / mel).
"""

import copy
import math
from typing import Dict, List, Any, Optional, Tuple

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None

from retarget.profiles import resolve_node_name
from pose_core.schema import RigProfile
from pose_core.math3d import v_dist, v_sub, euler_to_q, q_multiply, q_inverse, q_normalize, q_rotate_vector


def is_maya_available() -> bool:
    return cmds is not None


def auto_detect_character_namespace() -> str:
    """
    Scans scene for known character root or pelvis nodes and returns namespace prefix.
    """
    if not is_maya_available():
        return ""

    # Check top-level
    known_roots = ["Root_M", "RootX_M", "Hips", "root", "pelvis"]
    for r in known_roots:
        if cmds.objExists(r):
            return ""

    # Check namespaces
    namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
    for ns in namespaces:
        if ns in ["UI", "shared"]:
            continue
        for r in known_roots:
            if cmds.objExists(f"{ns}:{r}"):
                return f"{ns}:"

    return ""


def inspect_scene_character(namespace: str = "") -> Dict[str, Any]:
    """
    Detailed scene inspection for character retargeting suitability.
    """
    if not is_maya_available():
        return {"available": False, "error": "Maya cmds not available"}

    ns = namespace.rstrip(":") + ":" if namespace else ""

    # Detect rig style
    as5_indicators = ["RootX_M", "IKArm_L", "FKShoulder_L", "FKIKArm_L"]
    hik_indicators = ["Hips", "LeftUpLeg", "LeftArm", "LeftHand"]
    ue5_indicators = ["pelvis", "thigh_l", "upperarm_l", "hand_l"]

    matched_as5 = [x for x in as5_indicators if cmds.objExists(f"{ns}{x}")]
    matched_hik = [x for x in hik_indicators if cmds.objExists(f"{ns}{x}")]
    matched_ue5 = [x for x in ue5_indicators if cmds.objExists(f"{ns}{x}")]

    if len(matched_as5) >= 2:
        rig_type = "advanced_skeleton_5"
        confidence = len(matched_as5) / float(len(as5_indicators))
    elif len(matched_hik) >= 2:
        rig_type = "pure_joints_humanik"
        confidence = len(matched_hik) / float(len(hik_indicators))
    elif len(matched_ue5) >= 2:
        rig_type = "pure_joints_ue5"
        confidence = len(matched_ue5) / float(len(ue5_indicators))
    else:
        rig_type = "custom"
        confidence = 0.0

    # Check locked attributes on matched nodes
    locked_channels = []
    has_animation = []
    all_matched = matched_as5 or matched_hik or matched_ue5
    for node_base in all_matched:
        node = f"{ns}{node_base}"
        for attr in ["tx", "ty", "tz", "rx", "ry", "rz"]:
            full_attr = f"{node}.{attr}"
            if cmds.objExists(full_attr):
                if cmds.getAttr(full_attr, lock=True):
                    locked_channels.append(full_attr)
                curves = cmds.keyframe(full_attr, q=True, name=True) or []
                if curves:
                    has_animation.append(full_attr)

    return {
        "available": True,
        "namespace": ns,
        "rig_type": rig_type,
        "confidence": confidence,
        "matched_nodes": [f"{ns}{x}" for x in all_matched],
        "locked_channels": locked_channels,
        "animated_channels": has_animation
    }


def calibrate_profile_from_scene(profile: RigProfile, namespace: str = "") -> Tuple[RigProfile, List[str]]:
    """
    Measures bone lengths, chain anchors, pelvis height, and controller bind offsets
    directly from active Maya scene objects, saving them into the RigProfile.
    Atomic execution: operates on a deepcopy and only returns modified profile on complete success.
    """
    if not is_maya_available():
        return profile, ["Maya cmds not available"]

    new_profile = copy.deepcopy(profile)
    ns = namespace.rstrip(":") + ":" if namespace else ""
    captured_items: List[str] = []

    ro_map = {0: 'xyz', 1: 'yzx', 2: 'zxy', 3: 'xzy', 4: 'yxz', 5: 'zyx'}

    # 1. Pelvis / Hip height
    pelvis_full = f"{ns}{new_profile.pelvis_node}"
    if cmds.objExists(pelvis_full):
        pos = cmds.xform(pelvis_full, q=True, ws=True, t=True)
        new_profile.target_hip_height = float(pos[1])
        captured_items.append(f"pelvis_height: {pos[1]:.2f}cm")

    # 2. Chains: limb lengths and anchors
    for chain_id, chain in new_profile.chains.items():
        if not chain.fk_controls or len(chain.fk_controls) < 3:
            continue

        # If 4 controls (e.g. clavicle, upperarm, forearm, wrist)
        if len(chain.fk_controls) >= 4:
            n0 = f"{ns}{chain.fk_controls[1]}"      # Upperarm / Shoulder
            n1 = f"{ns}{chain.fk_controls[2]}"      # Forearm / Elbow
            n2 = f"{ns}{chain.fk_controls[3]}"      # Hand / Wrist
        else:
            # 3 controls (e.g. thigh, calf, foot)
            n0 = f"{ns}{chain.fk_controls[0]}"      # Thigh / Hip
            n1 = f"{ns}{chain.fk_controls[1]}"      # Calf / Knee
            n2 = f"{ns}{chain.fk_controls[2]}"      # Foot / Ankle

        if cmds.objExists(n0) and cmds.objExists(n1) and cmds.objExists(n2):
            p0 = cmds.xform(n0, q=True, ws=True, t=True)
            p1 = cmds.xform(n1, q=True, ws=True, t=True)
            p2 = cmds.xform(n2, q=True, ws=True, t=True)

            l1 = float(v_dist(p0, p1))
            l2 = float(v_dist(p1, p2))
            new_profile.target_limb_lengths[chain_id] = [l1, l2]
            new_profile.target_chain_anchors[chain_id] = [float(x) for x in p0]
            captured_items.append(f"{chain_id}_lengths: [{l1:.2f}, {l2:.2f}]cm")

            # 3. IK Controller bind offset
            if chain.ik_control:
                ik_node = f"{ns}{chain.ik_control}"
                if cmds.objExists(ik_node):
                    p_ik = cmds.xform(ik_node, q=True, ws=True, t=True)
                    r_ik_euler = cmds.xform(ik_node, q=True, ws=True, ro=True)
                    ik_ro_int = cmds.getAttr(f"{ik_node}.rotateOrder") if cmds.attributeQuery("rotateOrder", node=ik_node, exists=True) else 0
                    ik_order = ro_map.get(ik_ro_int, 'xyz')
                    q_ik = euler_to_q(r_ik_euler, order=ik_order)

                    r_joint_euler = cmds.xform(n2, q=True, ws=True, ro=True)
                    joint_ro_int = cmds.getAttr(f"{n2}.rotateOrder") if cmds.attributeQuery("rotateOrder", node=n2, exists=True) else 0
                    joint_order = ro_map.get(joint_ro_int, 'xyz')
                    q_joint = euler_to_q(r_joint_euler, order=joint_order)

                    # pos_offset in joint local rest frame
                    v_diff = v_sub(p_ik, p2)
                    pos_offset_local = q_rotate_vector(q_inverse(q_joint), v_diff)
                    rot_offset = q_multiply(q_normalize(q_ik), q_inverse(q_normalize(q_joint)))

                    new_profile.control_offsets[chain.ik_control] = {
                        "pos_offset": [float(x) for x in pos_offset_local],
                        "rot_offset": [float(x) for x in rot_offset],
                        "bind_pos": [float(x) for x in p_ik],
                        "bind_rot": [float(x) for x in q_ik]
                    }
                    captured_items.append(f"{chain.ik_control}_bind_offset")

    return new_profile, captured_items
