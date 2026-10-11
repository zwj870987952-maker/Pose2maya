"""
DCC Standard Skeleton Builder & Animator for Autodesk Maya
Converts raw SAM 3D / MHR pose estimation output into a clean, industry-standard
DCC humanoid skeleton with hierarchical bones, standard naming, and FBX export capability.
"""

import os
import json
import math
import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om
from mhr_dcc_mapper import MHR_127_JOINTS, get_joint_info, get_core_indices

class DCCSkeletonBuilder(object):
    def __init__(self, naming_style="ue5", mode="core", prefix="DCC_"):
        """
        :param naming_style: 'ue5' (Unreal Mannequin style) or 'humanik' (Maya HumanIK / Mixamo style)
        :param mode: 'core' (Standard humanoid bones) or 'full' (All 127 bones with fingers & face)
        :param prefix: Namespace or name prefix for created joints (e.g. 'DCC_')
        """
        self.naming_style = naming_style.lower()
        self.mode = mode.lower()
        self.prefix = prefix

    def get_joint_name(self, idx):
        info = get_joint_info(idx)
        if not info:
            return f"{self.prefix}joint_{idx}"
        base_name = info["ue5_name"] if self.naming_style == "ue5" else info["humanik_name"]
        return f"{self.prefix}{base_name}"

    def build_skeleton(self, json_path_or_dict, scale=100.0, world_offset=(0.0, 0.0, 0.0)):
        """
        Builds a standard, hierarchical DCC joint skeleton in the Maya scene.
        """
        if isinstance(json_path_or_dict, str):
            with open(json_path_or_dict, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = json_path_or_dict

        skel_data = data.get("skeleton", {})
        world_positions = skel_data.get("world_positions", [])
        if not world_positions or len(world_positions) < 120:
            cmds.error("[DCCSkeletonBuilder] Invalid or insufficient world_positions in JSON.")
            return []

        # Determine which joints to build
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

        # Topological pass: MHR_127_JOINTS is strictly ordered parent < child
        for i, (p_idx, anat, ue5, hik, is_core) in enumerate(MHR_127_JOINTS):
            if i not in active_indices:
                continue

            jname = self.get_joint_name(i)
            raw_pos = world_positions[i]

            # Coordinate transformation from SAM 3D Camera space to Maya World space:
            # X_maya = X_cam * scale + offset_x
            # Y_maya = -Y_cam * scale + offset_y
            # Z_maya = -Z_cam * scale + offset_z
            mx = raw_pos[0] * scale + world_offset[0]
            my = (-raw_pos[1]) * scale + world_offset[1]
            mz = (-raw_pos[2]) * scale + world_offset[2]

            # Find parent joint
            # If in 'core' mode and direct parent is not in core, climb up to nearest active ancestor
            curr_p = p_idx
            while curr_p >= 0 and curr_p not in active_indices:
                curr_p = MHR_127_JOINTS[curr_p][0]

            if curr_p >= 0 and curr_p in created_joints:
                p_joint_name = created_joints[curr_p]
                cmds.select(p_joint_name)
            else:
                cmds.select(cl=True)

            j = cmds.joint(name=jname, p=[mx, my, mz])
            # Set display radius and bone draw style
            rad = 3.5 if is_core else 1.8
            cmds.setAttr(f"{j}.radius", rad)
            created_joints[i] = j

        # Orient joints so that local axes point cleanly down bone chains
        self.orient_skeleton()

        cmds.select(cl=True)
        print(f"[DCCSkeletonBuilder] Successfully generated DCC skeleton '{root_name}' ({len(created_joints)} joints, style={self.naming_style}, mode={self.mode}).")
        return list(created_joints.values())

    def orient_skeleton(self):
        """
        Applies standard DCC joint orientation along bone chains.
        Primary axis X points to child, secondary axis Y points Up.
        """
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
        Updates the positions of joints in the DCC skeleton and optionally keys them.
        """
        if isinstance(json_path_or_dict, str):
            with open(json_path_or_dict, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = json_path_or_dict

        skel_data = data.get("skeleton", {})
        world_positions = skel_data.get("world_positions", [])
        if not world_positions:
            return False

        if keyframe is not None:
            cmds.currentTime(keyframe, update=True)

        if self.mode == "core":
            active_indices = set(get_core_indices())
        else:
            active_indices = set(range(len(MHR_127_JOINTS)))

        updated_joints = []
        for i in active_indices:
            if i < len(world_positions):
                jname = self.get_joint_name(i)
                if cmds.objExists(jname):
                    raw_pos = world_positions[i]
                    mx = raw_pos[0] * scale + world_offset[0]
                    my = (-raw_pos[1]) * scale + world_offset[1]
                    mz = (-raw_pos[2]) * scale + world_offset[2]
                    cmds.xform(jname, ws=True, t=[mx, my, mz])
                    updated_joints.append(jname)

        if keyframe is not None and updated_joints:
            cmds.setKeyframe(updated_joints, time=keyframe, attribute='translate')
            # Also calculate and key local rotations so FK animation is captured
            self.orient_skeleton()
            cmds.setKeyframe(updated_joints, time=keyframe, attribute='rotate')
            print(f"[DCCSkeletonBuilder] Keyframed {len(updated_joints)} joints at frame {keyframe}.")

        return True

    def export_fbx(self, output_fbx_path, start_frame=1, end_frame=50):
        """
        Exports the generated DCC skeleton and timeline animation to a clean FBX file.
        """
        root_name = self.get_joint_name(0)
        if not cmds.objExists(root_name):
            cmds.error(f"[DCCSkeletonBuilder] Skeleton root '{root_name}' not found.")
            return False

        # Ensure FBX plugin is loaded
        if not cmds.pluginInfo('fbxmaya', q=True, loaded=True):
            try:
                cmds.loadPlugin('fbxmaya')
            except Exception as e:
                cmds.error(f"[DCCSkeletonBuilder] Failed to load FBX plugin: {e}")
                return False

        cmds.select(root_name, hierarchy=True)

        # Standard clean FBX export settings for Game Engines (UE5/Unity)
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
