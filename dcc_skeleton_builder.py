"""
dcc_skeleton_builder.py
=======================
DCC Standard Skeleton Builder & Animator for Autodesk Maya.
Converts SAM 3D / MHR pose estimation output into clean, industry-standard DCC skeletons.
Fixes M01:
  - Builds reference skeleton once with fixed bone lengths and jointOrient.
  - Applies animations strictly via joint local rotations and root translation (FK).
"""

import os
import json
import math
from typing import Union, Dict, Any, List

try:
    import maya.cmds as cmds
    import maya.mel as mel
except ImportError:
    cmds = None
    mel = None

from mhr_dcc_mapper import MHR_127_JOINTS, get_joint_info, get_core_indices
from pose_core.mhr_adapter import load_legacy_skeleton_json, get_authoritative_mhr_skeleton_def
from pose_core.math3d import (
    q_to_euler_deg, cam_pos_to_maya, fk_reconstruct,
    q_multiply, q_inverse, q_identity, euler_to_q
)


class DCCSkeletonBuilder(object):
    def __init__(self, naming_style="ue5", mode="core", prefix="DCC_"):
        self.naming_style = naming_style.lower()
        self.mode = mode.lower()
        self.prefix = prefix

    def get_joint_name(self, idx):
        info = get_joint_info(idx)
        if not info:
            return f"{self.prefix}joint_{idx}"
        base_name = info["ue5_name"] if self.naming_style == "ue5" else info["humanik_name"]
        return f"{self.prefix}{base_name}"

    def build_skeleton(self, json_path_or_dict=None, scale=100.0, world_offset=(0.0, 0.0, 0.0)):
        """
        Builds a standard, hierarchical DCC joint skeleton in the Maya scene in REST POSE.
        Bones are created once and oriented once; bone lengths and jointOrient remain constant.
        """
        if cmds is None:
            return []

        # Load standardized rest definitions
        skel_def = get_authoritative_mhr_skeleton_def()

        # Determine active joint indices
        if self.mode == "core":
            active_indices = set(get_core_indices())
        else:
            active_indices = set(range(len(MHR_127_JOINTS)))

        # Clean up existing skeleton with this prefix if already present
        root_name = self.get_joint_name(0)
        if cmds.objExists(root_name):
            cmds.delete(root_name)

        created_joints = {}
        cmds.select(cl=True)

        # Build in rest pose from skel_def.rest_world_positions
        rest_positions = skel_def.rest_world_positions
        scale_factor = scale / 100.0  # rest positions are already in cm

        for i, (p_idx, anat, ue5, hik, is_core) in enumerate(MHR_127_JOINTS):
            if i not in active_indices:
                continue

            jname = self.get_joint_name(i)
            r_pos = rest_positions[i] if i < len(rest_positions) else [0.0, 0.0, 0.0]

            mx = r_pos[0] * scale_factor + world_offset[0]
            my = r_pos[1] * scale_factor + world_offset[1]
            mz = r_pos[2] * scale_factor + world_offset[2]

            # Find active ancestor
            curr_p = p_idx
            while curr_p >= 0 and curr_p not in active_indices:
                curr_p = MHR_127_JOINTS[curr_p][0]

            if curr_p >= 0 and curr_p in created_joints:
                cmds.select(created_joints[curr_p])
            else:
                cmds.select(cl=True)

            j = cmds.joint(name=jname, p=[mx, my, mz])
            rad = 3.5 if is_core else 1.8
            cmds.setAttr(f"{j}.radius", rad)
            created_joints[i] = j

        # Orient joints once at rest pose
        self.orient_skeleton()
        cmds.select(cl=True)

        print(f"[DCCSkeletonBuilder] Successfully generated DCC rest skeleton '{root_name}' ({len(created_joints)} joints).")
        return list(created_joints.values())

    def orient_skeleton(self):
        """Applies standard DCC joint orientation along bone chains once."""
        if cmds is None:
            return
        root_name = self.get_joint_name(0)
        if not cmds.objExists(root_name):
            return

        all_joints = cmds.listRelatives(root_name, allDescendents=True, type='joint') or []
        all_joints.append(root_name)

        for j in all_joints:
            children = cmds.listRelatives(j, children=True, type='joint') or []
            if children:
                try:
                    cmds.joint(j, edit=True, zso=True, oj="xyz", sao="yup")
                except Exception:
                    pass
            else:
                try:
                    cmds.joint(j, edit=True, zso=True, oj="none")
                except Exception:
                    pass

    def apply_pose(self, json_path_or_dict, scale=100.0, world_offset=(0.0, 0.0, 0.0), keyframe=None):
        """
        Updates the pose of the DCC skeleton via joint rotations and root translation.
        Does NOT alter bone lengths or jointOrient.
        """
        if cmds is None:
            return False

        sample_pose = load_legacy_skeleton_json(json_path_or_dict)
        if keyframe is not None:
            cmds.currentTime(keyframe, update=True)

        scale_factor = scale / 100.0
        root_name = self.get_joint_name(0)

        # 1. Update root translation
        if cmds.objExists(root_name) and len(sample_pose.world_positions) > 0:
            root_pos = sample_pose.world_positions[0]
            mx = root_pos[0] * scale_factor + world_offset[0]
            my = root_pos[1] * scale_factor + world_offset[1]
            mz = root_pos[2] * scale_factor + world_offset[2]
            cmds.xform(root_name, ws=True, t=[mx, my, mz])

        # 2. Compute FK global rotations for input pose and reference pose (AUD-02)
        skel_def = get_authoritative_mhr_skeleton_def()
        _, rest_world_rots = fk_reconstruct(
            skel_def.parent_indices,
            skel_def.rest_translations,
            skel_def.rest_rotations,
            root_translation=[0.0, 0.0, 0.0],
            root_rotation=[0.0, 0.0, 0.0, 1.0]
        )
        _, pose_world_rots = fk_reconstruct(
            skel_def.parent_indices,
            skel_def.rest_translations,
            sample_pose.local_rotations,
            root_translation=sample_pose.root_translation,
            root_rotation=sample_pose.root_rotation
        )

        # 3. Update local rotations
        if self.mode == "core":
            active_indices = set(get_core_indices())
        else:
            active_indices = set(range(len(MHR_127_JOINTS)))

        # Cache Maya rest orientations based on Maya joint hierarchy & jointOrient
        maya_rest_rots = {}
        for i in active_indices:
            jname = self.get_joint_name(i)
            if not cmds.objExists(jname):
                continue
            if cmds.attributeQuery("jointOrient", node=jname, exists=True):
                jo_euler = cmds.getAttr(f"{jname}.jointOrient")[0]
                q_jo = euler_to_q(jo_euler, order='xyz')
            else:
                q_jo = q_identity()

            curr_p = MHR_127_JOINTS[i][0]
            while curr_p >= 0 and curr_p not in active_indices:
                curr_p = MHR_127_JOINTS[curr_p][0]

            if curr_p < 0 or curr_p not in maya_rest_rots:
                maya_rest_rots[i] = q_jo
            else:
                maya_rest_rots[i] = q_multiply(maya_rest_rots[curr_p], q_jo)

        updated_joints = []
        for i in active_indices:
            jname = self.get_joint_name(i)
            if not cmds.objExists(jname):
                continue

            curr_p = MHR_127_JOINTS[i][0]
            while curr_p >= 0 and curr_p not in active_indices:
                curr_p = MHR_127_JOINTS[curr_p][0]

            # Delta world rotation in MHR space from rest to pose
            delta_w_i = q_multiply(pose_world_rots[i], q_inverse(rest_world_rots[i]))
            w_maya_i = q_multiply(delta_w_i, maya_rest_rots[i])

            if curr_p < 0:
                w_maya_p = q_identity()
            else:
                delta_w_p = q_multiply(pose_world_rots[curr_p], q_inverse(rest_world_rots[curr_p]))
                w_maya_p = q_multiply(delta_w_p, maya_rest_rots[curr_p])

            if cmds.attributeQuery("jointOrient", node=jname, exists=True):
                jo_euler = cmds.getAttr(f"{jname}.jointOrient")[0]
                q_jo = euler_to_q(jo_euler, order='xyz')
            else:
                q_jo = q_identity()

            # R_i = JO_i^-1 * (W_p^-1 * W_i)
            q_r = q_multiply(q_inverse(q_jo), q_multiply(q_inverse(w_maya_p), w_maya_i))

            ro_int = cmds.getAttr(f"{jname}.rotateOrder")
            ro_map = {0: 'xyz', 1: 'yzx', 2: 'zxy', 3: 'xzy', 4: 'yxz', 5: 'zyx'}
            order_str = ro_map.get(ro_int, 'xyz')
            euler = q_to_euler_deg(q_r, order=order_str)
            cmds.setAttr(f"{jname}.r", euler[0], euler[1], euler[2])
            updated_joints.append(jname)

        if keyframe is not None and updated_joints:
            if cmds.objExists(root_name):
                cmds.setKeyframe(root_name, attribute='translate', time=keyframe)
            cmds.setKeyframe(updated_joints, attribute='rotate', time=keyframe)
            print(f"[DCCSkeletonBuilder] Keyframed {len(updated_joints)} joints at frame {keyframe}.")

        return True

    def export_fbx(self, output_fbx_path, start_frame=1, end_frame=50):
        if cmds is None:
            return False
        root_name = self.get_joint_name(0)
        if not cmds.objExists(root_name):
            cmds.error(f"[DCCSkeletonBuilder] Skeleton root '{root_name}' not found.")
            return False

        if not cmds.pluginInfo('fbxmaya', q=True, loaded=True):
            try:
                cmds.loadPlugin('fbxmaya')
            except Exception as e:
                cmds.error(f"[DCCSkeletonBuilder] Failed to load FBX plugin: {e}")
                return False

        cmds.select(root_name, hierarchy=True)
        mel.eval("FBXResetExport;")
        mel.eval("FBXExportBakeComplexAnimation -v true;")
        mel.eval(f"FBXExportBakeComplexStart -v {start_frame};")
        mel.eval(f"FBXExportBakeComplexEnd -v {end_frame};")
        mel.eval("FBXExportAnimationOnly -v false;")
        mel.eval("FBXExportSkins -v false;")
        mel.eval("FBXExportShapes -v false;")
        mel.eval("FBXExportInputConnections -v false;")
        mel.eval("FBXExportInAscii -v false;")
        mel.eval("FBXExportUpAxis y;")

        out_norm = output_fbx_path.replace("\\", "/")
        mel.eval(f'FBXExport -f "{out_norm}" -s;')
        print(f"[DCCSkeletonBuilder] Successfully exported FBX to: {output_fbx_path}")
        return True
