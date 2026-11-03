"""
pose_retargeter.py
==================
Main entry point for Maya retargeting.
Delegates to modular pose_core and retarget engine while preserving backwards-compatible APIs.
"""

import os
import json
from typing import Union, Dict, Any, Optional

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None

from pose_core.schema import RetargetProfile
from pose_core.mhr_adapter import load_legacy_skeleton_json, get_authoritative_mhr_skeleton_def
from retarget.engine import retarget
from retarget.profiles import load_rig_profile, get_preset_as5, get_preset_pure_joints_ue5
from maya_scripts.rig_adapter import prepare_write_plan
from maya_scripts.pose_session import PoseSession
from dcc_skeleton_builder import DCCSkeletonBuilder

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


class PoseRetargeter(object):
    """
    Adaptive Retargeter supporting Character Rigs (AS5 / Venom) and Pure Joint Skeletons.
    """

    def __init__(self, target_prefix=""):
        if target_prefix and not target_prefix.endswith(":"):
            self.target_prefix = f"{target_prefix}:"
        else:
            self.target_prefix = target_prefix or ""
        self.session = PoseSession()

    def resolve_target(self, name):
        if not name:
            return ""
        if self.target_prefix and not name.startswith(self.target_prefix):
            return f"{self.target_prefix}{name}"
        return name

    def is_rig_controller_driven(self):
        if cmds is None:
            return True
        ik_arm = self.resolve_target("IKArm_L")
        root_x = self.resolve_target("RootX_M")
        return cmds.objExists(ik_arm) or cmds.objExists(root_x)

    def build_or_update_template_b(self, json_path_or_dict, scale=100.0, world_offset=None):
        """Builds or updates standard visual reference skeleton B."""
        builder = DCCSkeletonBuilder(naming_style="ue5", mode="core", prefix="MHR_Template:")
        offset = world_offset if world_offset is not None else (180.0, 0.0, 0.0)
        return builder.build_skeleton(json_path_or_dict, scale=scale, world_offset=offset)

    def retarget_pose(self, json_path_or_dict, use_ik=True, keyframe=None):
        """
        Retargets input pose JSON or dict to target character.
        Returns True on successful write, False on missing targets or failure.
        """
        # 1. Parse into standardized PoseSample v2
        try:
            sample_pose = load_legacy_skeleton_json(json_path_or_dict)
        except Exception as e:
            if cmds: cmds.warning(f"[PoseRetargeter] Failed parsing pose data: {e}")
            return False

        # 2. Select RigProfile
        is_rig = self.is_rig_controller_driven()
        if is_rig:
            rig_profile = get_preset_as5()
        else:
            rig_profile = get_preset_pure_joints_ue5()

        # 3. Configure RetargetProfile
        mode_val = "ik" if (use_ik and is_rig) else "fk"
        retarget_prof = RetargetProfile(
            chain_modes={
                "spine": "fk",
                "neck_head": "fk",
                "left_arm": mode_val,
                "right_arm": mode_val,
                "left_leg": mode_val,
                "right_leg": mode_val
            }
        )

        # 4. Run calculation engine
        skel_def = get_authoritative_mhr_skeleton_def()
        result = retarget(sample_pose, skel_def, rig_profile, retarget_prof)
        if not result.success:
            if cmds: cmds.warning(f"[PoseRetargeter] Retarget engine failed: {result.errors}")
            return False

        # 5. Build WritePlan with pre-checks
        plan = prepare_write_plan(result, namespace=self.target_prefix, auto_key=(keyframe is not None))
        if not plan.can_apply:
            msg = f"[PoseRetargeter] Application blocked: {'; '.join(plan.blockers)}"
            if cmds: cmds.warning(msg)
            else: print(msg)
            return False

        # 6. Commit transaction safely
        report = self.session.commit(plan, keyframe=keyframe)
        if report.status == "success":
            print(f"[PoseRetargeter] SUCCESS: Applied pose to {report.channels_modified} channels on '{self.target_prefix or 'default'}'.")
            return True
        else:
            msg = f"[PoseRetargeter] FAILED: {'; '.join(report.messages)}"
            if cmds: cmds.warning(msg)
            else: print(msg)
            return False


def retarget_sample_pose(sample_idx=1, target_namespace="", create_template=False, keyframe=None, use_ik=True):
    sample_names = {
        1: "01_human_standard_skeleton.json",
        2: "02_human_dancing_skeleton.json",
        3: "03_game_3d_ironman_skeleton.json",
        4: "04_anime_illustration_skeleton.json",
        5: "05_strong_perspective_skeleton.json",
        6: "06_limb_occlusion_skeleton.json"
    }

    filename = sample_names.get(sample_idx, "01_human_standard_skeleton.json")
    # Priority: repo data/sample_poses/ -> D:\sam-3d-body fallback
    candidate1 = os.path.join(REPO_ROOT, "data", "sample_poses", filename)
    candidate2 = os.path.join(r"D:\sam-3d-body\outputs\benchmark_results", filename)

    json_file = candidate1 if os.path.exists(candidate1) else candidate2
    if not os.path.exists(json_file):
        print(f"[Error] Benchmark pose file not found: {filename}")
        return False

    retargeter = PoseRetargeter(target_prefix=target_namespace)
    if create_template:
        retargeter.build_or_update_template_b(json_file)
    return retargeter.retarget_pose(json_file, use_ik=use_ik, keyframe=keyframe)


if __name__ == "__main__":
    retarget_sample_pose(sample_idx=2)
