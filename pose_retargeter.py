"""
Unified 3D Pose Retargeter for Autodesk Maya
Supports:
1. Pure Joint Skeletons (Deformation bones, e.g. sk_test.ma) via Hierarchical Swing-Vector Alignment
   - Solves exact Euler rotations taking jointOrient, rotateOrder, and parent matrices into account
2. Full Character Rigs (e.g. Advanced Skeleton 5, Venom_Rig2) via IK/FK Goal & Pole-Vector Mapping
3. Template Skeleton B generation & visual preview from SAM 3D / MHR pose estimation output
"""

import os
import json
import math
import maya.cmds as cmds
import maya.api.OpenMaya as om

# -----------------------------------------------------------------------------------
# 1. Ground Truth MHR 127 Anatomical Indices (Reverse-engineered from mhr_model.pt)
# -----------------------------------------------------------------------------------
MHR_GROUND_TRUTH_INDICES = {
    "root": 0,
    "pelvis": 1,
    "spine1": 34,
    "spine2": 35,
    "spine3": 36,
    "chest": 37,
    "neck": 110,
    "head": 113,
    "l_clavicle": 74,
    "l_shoulder": 75,
    "l_elbow": 76,
    "l_wrist": 77,
    "r_clavicle": 38,
    "r_shoulder": 39,
    "r_elbow": 40,
    "r_wrist": 41,
    "l_hip": 2,
    "l_knee": 3,
    "l_ankle": 4,
    "r_hip": 18,
    "r_knee": 19,
    "r_ankle": 20,
}


def orient_joint(parent_joint, child_joint, target_dir):
    """
    Bulletproof rotation solver for Maya joints with jointOrient and arbitrary rotateOrder.
    Rotates parent_joint so that child_joint aligns with target_dir in World Space.
    Formula: M_R = W_rot_target * (M_JO * W_parent_rot)^-1
    """
    if not cmds.objExists(parent_joint) or not cmds.objExists(child_joint):
        return

    p_parent = om.MVector(*cmds.xform(parent_joint, q=True, ws=True, t=True))
    p_child = om.MVector(*cmds.xform(child_joint, q=True, ws=True, t=True))
    curr_dir = (p_child - p_parent).normal()
    des_dir = target_dir.normal()

    dot = curr_dir * des_dir
    if dot > 0.99999 or curr_dir.length() < 0.001 or des_dir.length() < 0.001:
        return

    q_swing = om.MQuaternion(curr_dir, des_dir)
    m_swing = q_swing.asMatrix()

    # Current world rotation matrix of parent_joint
    w_mat = om.MMatrix(cmds.getAttr(f"{parent_joint}.worldMatrix[0]"))
    tr_w = om.MTransformationMatrix(w_mat)
    w_rot_init = tr_w.asRotateMatrix()
    w_rot_target = w_rot_init * m_swing

    # Parent node's world rotation matrix
    parent_node = cmds.listRelatives(parent_joint, p=True)
    if parent_node and cmds.objExists(parent_node[0]):
        w_parent_mat = om.MMatrix(cmds.getAttr(f"{parent_node[0]}.worldMatrix[0]"))
        tr_parent_w = om.MTransformationMatrix(w_parent_mat)
        w_parent_rot = tr_parent_w.asRotateMatrix()
    else:
        w_parent_rot = om.MMatrix.kIdentity

    # JointOrient matrix
    jo_vals = [math.radians(x) for x in cmds.getAttr(f"{parent_joint}.jointOrient")[0]]
    jo_euler = om.MEulerRotation(jo_vals, om.MEulerRotation.kXYZ)
    m_jo = jo_euler.asMatrix()

    # Solve M_R:
    m_r = w_rot_target * (m_jo * w_parent_rot).inverse()

    # Reorder to joint's specific rotateOrder
    ro_int = cmds.getAttr(f"{parent_joint}.rotateOrder")
    tr_r = om.MTransformationMatrix(m_r)
    euler_r = tr_r.rotation(asQuaternion=False)
    euler_r.reorderIt(ro_int)

    rx = math.degrees(euler_r.x)
    ry = math.degrees(euler_r.y)
    rz = math.degrees(euler_r.z)
    cmds.setAttr(f"{parent_joint}.r", rx, ry, rz)


class PoseRetargeter(object):
    """
    Adaptive Retargeter capable of retargeting onto both Rig Controllers and Pure Joint Skeletons.
    """

    def __init__(self, target_prefix=""):
        if target_prefix and not target_prefix.endswith(":"):
            self.target_prefix = f"{target_prefix}:"
        else:
            self.target_prefix = target_prefix or ""
        self.template_prefix = "MHR_Template:"

    def resolve_target(self, name):
        """Prepend target namespace if needed."""
        if not name:
            return ""
        if self.target_prefix and not name.startswith(self.target_prefix):
            return f"{self.target_prefix}{name}"
        return name

    def is_rig_controller_driven(self):
        """Detect whether character A has Rig controllers or is a pure joint skeleton."""
        ik_arm = self.resolve_target("IKArm_L")
        root_x = self.resolve_target("RootX_M")
        return cmds.objExists(ik_arm) or cmds.objExists(root_x)

    # -------------------------------------------------------------------------------
    # Build Skeleton B (Template Skeleton)
    # -------------------------------------------------------------------------------
    def build_or_update_template_b(self, json_path_or_dict, scale=100.0, world_offset=None):
        if isinstance(json_path_or_dict, str):
            with open(json_path_or_dict, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json_path_or_dict

        skel_data = data.get("skeleton", {})
        num_joints = skel_data.get("num_joints", 0)
        parent_indices = skel_data.get("parent_indices", [])
        world_positions = skel_data.get("world_positions", [])

        if not world_positions:
            cmds.error("[PoseRetargeter] Invalid skeleton JSON data.")
            return []

        # Find reference root position from target A
        if world_offset is None:
            ref_root = self.resolve_target("RootX_M")
            if not cmds.objExists(ref_root):
                ref_root = self.resolve_target("Root_M")
            if cmds.objExists(ref_root):
                target_pos = cmds.xform(ref_root, q=True, ws=True, t=True)
                world_offset = [target_pos[0] + 180.0, target_pos[1], target_pos[2]]
            else:
                world_offset = [180.0, 0.0, 0.0]

        created_joints = []
        cmds.select(cl=True)

        for i in range(min(num_joints, len(world_positions))):
            maya_jname = f"{self.template_prefix}Joint_{i:03d}"
            pos = world_positions[i]

            # Coordinate conversion: X -> X, Y -> -Y, Z -> -Z
            mx = pos[0] * scale + world_offset[0]
            my = (-pos[1]) * scale + world_offset[1]
            mz = (-pos[2]) * scale + world_offset[2]

            parent_idx = parent_indices[i] if i < len(parent_indices) else -1

            if cmds.objExists(maya_jname):
                cmds.xform(maya_jname, ws=True, t=[mx, my, mz])
            else:
                if parent_idx >= 0 and parent_idx < i:
                    p_name = f"{self.template_prefix}Joint_{parent_idx:03d}"
                    if cmds.objExists(p_name):
                        cmds.select(p_name)
                    else:
                        cmds.select(cl=True)
                else:
                    cmds.select(cl=True)

                j = cmds.joint(n=maya_jname, p=[mx, my, mz], rad=2.5)
                created_joints.append(j)

        cmds.select(cl=True)
        print(f"[PoseRetargeter] Template Skeleton B built/updated ({len(world_positions)} joints).")
        return created_joints

    # -------------------------------------------------------------------------------
    # Retarget Pose Master Dispatcher
    # -------------------------------------------------------------------------------
    def retarget_pose(self, json_path_or_dict, use_ik=True, keyframe=None):
        if isinstance(json_path_or_dict, str):
            with open(json_path_or_dict, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json_path_or_dict

        skel_data = data.get("skeleton", {})
        world_positions = skel_data.get("world_positions", [])

        if not world_positions or len(world_positions) < 120:
            cmds.warning("[PoseRetargeter] Insufficient joint count in pose data.")
            return False

        # Build position lookup using ground-truth indices
        # Camera coords [x, y, z] -> Maya coords [x, -y, -z]
        pos_dict = {}
        for anat_name, idx in MHR_GROUND_TRUTH_INDICES.items():
            if idx < len(world_positions):
                p = world_positions[idx]
                pos_dict[anat_name] = om.MVector(p[0], -p[1], -p[2])

        if self.is_rig_controller_driven():
            print(f"[PoseRetargeter] Detected Controller Rig on {self.target_prefix}. Using IK/FK Rig retargeting.")
            return self._retarget_to_rig(pos_dict, use_ik, keyframe)
        else:
            print(f"[PoseRetargeter] Detected Joint Hierarchy on {self.target_prefix or 'Root_M'}. Using Exact Joint Swing retargeting.")
            return self._retarget_to_joints(pos_dict, keyframe)

    # -------------------------------------------------------------------------------
    # Mode A: Joint-to-Joint Hierarchical Swing Retargeting (sk_test.ma)
    # -------------------------------------------------------------------------------
    def _retarget_to_joints(self, pos_dict, keyframe=None):
        if keyframe is not None:
            cmds.currentTime(keyframe, update=True)

        target_joints = [
            self.resolve_target(j) for j in [
                "Root_M", "Spine1_M", "Spine2_M", "Chest_M", "Neck_M", "Head_M",
                "Scapula_L", "Shoulder_L", "Elbow_L", "Wrist_L",
                "Scapula_R", "Shoulder_R", "Elbow_R", "Wrist_R",
                "Hip_L", "Knee_L", "Ankle_L",
                "Hip_R", "Knee_R", "Ankle_R"
            ]
        ]

        # Reset rotations to evaluate clean base pose
        for j in target_joints:
            if cmds.objExists(j):
                cmds.setAttr(f"{j}.r", 0, 0, 0)

        # 1. Spine (Top-down)
        v_spine = (pos_dict["chest"] - pos_dict["pelvis"]).normal()
        root_m = self.resolve_target("Root_M")
        s1 = self.resolve_target("Spine1_M")
        s2 = self.resolve_target("Spine2_M")
        ch = self.resolve_target("Chest_M")
        nk = self.resolve_target("Neck_M")
        hd = self.resolve_target("Head_M")

        orient_joint(root_m, s1, v_spine)
        orient_joint(s1, s2, v_spine)
        orient_joint(s2, ch, (pos_dict["chest"] - pos_dict["spine2"]).normal())
        orient_joint(ch, nk, (pos_dict["neck"] - pos_dict["chest"]).normal())
        orient_joint(nk, hd, (pos_dict["head"] - pos_dict["neck"]).normal())

        # 2. Left Arm
        sca_l = self.resolve_target("Scapula_L")
        sh_l = self.resolve_target("Shoulder_L")
        el_l = self.resolve_target("Elbow_L")
        wr_l = self.resolve_target("Wrist_L")

        orient_joint(sca_l, sh_l, (pos_dict["l_shoulder"] - pos_dict["l_clavicle"]).normal())
        orient_joint(sh_l, el_l, (pos_dict["l_elbow"] - pos_dict["l_shoulder"]).normal())
        orient_joint(el_l, wr_l, (pos_dict["l_wrist"] - pos_dict["l_elbow"]).normal())

        # 3. Right Arm
        sca_r = self.resolve_target("Scapula_R")
        sh_r = self.resolve_target("Shoulder_R")
        el_r = self.resolve_target("Elbow_R")
        wr_r = self.resolve_target("Wrist_R")

        orient_joint(sca_r, sh_r, (pos_dict["r_shoulder"] - pos_dict["r_clavicle"]).normal())
        orient_joint(sh_r, el_r, (pos_dict["r_elbow"] - pos_dict["r_shoulder"]).normal())
        orient_joint(el_r, wr_r, (pos_dict["r_wrist"] - pos_dict["r_elbow"]).normal())

        # 4. Left Leg
        hp_l = self.resolve_target("Hip_L")
        kn_l = self.resolve_target("Knee_L")
        ak_l = self.resolve_target("Ankle_L")

        orient_joint(hp_l, kn_l, (pos_dict["l_knee"] - pos_dict["l_hip"]).normal())
        orient_joint(kn_l, ak_l, (pos_dict["l_ankle"] - pos_dict["l_knee"]).normal())

        # 5. Right Leg
        hp_r = self.resolve_target("Hip_R")
        kn_r = self.resolve_target("Knee_R")
        ak_r = self.resolve_target("Ankle_R")

        orient_joint(hp_r, kn_r, (pos_dict["r_knee"] - pos_dict["r_hip"]).normal())
        orient_joint(kn_r, ak_r, (pos_dict["r_ankle"] - pos_dict["r_knee"]).normal())

        if keyframe is not None:
            valid = [n for n in target_joints if cmds.objExists(n)]
            cmds.setKeyframe(valid, time=keyframe)
            print(f"[PoseRetargeter] Keyframed {len(valid)} joints at frame {keyframe}.")

        print("[PoseRetargeter] SUCCESS: Retargeted to Joint Skeleton!")
        return True

    # -------------------------------------------------------------------------------
    # Mode B: Rig Controller IK/FK Retargeting (Advanced Skeleton)
    # -------------------------------------------------------------------------------
    def _retarget_to_rig(self, pos_dict, use_ik=True, keyframe=None):
        if keyframe is not None:
            cmds.currentTime(keyframe, update=True)

        if use_ik:
            for side in ["_L", "_R"]:
                arm_blend = self.resolve_target(f"FKIKArm{side}.FKIKBlend")
                leg_blend = self.resolve_target(f"FKIKLeg{side}.FKIKBlend")
                if cmds.objExists(arm_blend): cmds.setAttr(arm_blend, 10.0)
                if cmds.objExists(leg_blend): cmds.setAttr(leg_blend, 10.0)

        b_root = pos_dict["pelvis"]
        b_neck = pos_dict["neck"]
        b_l_hip = pos_dict["l_hip"]
        b_l_knee = pos_dict["l_knee"]
        b_l_ankle = pos_dict["l_ankle"]
        b_leg_len = (b_l_knee - b_l_hip).length() + (b_l_ankle - b_l_knee).length()

        b_l_shoulder = pos_dict["l_shoulder"]
        b_l_elbow = pos_dict["l_elbow"]
        b_l_wrist = pos_dict["l_wrist"]
        b_arm_len = (b_l_elbow - b_l_shoulder).length() + (b_l_wrist - b_l_elbow).length()

        tgt_hip_l = self.resolve_target("FKHip_L")
        tgt_knee_l = self.resolve_target("FKKnee_L")
        tgt_ankle_l = self.resolve_target("FKAnkle_L")
        tgt_leg_len = 100.0
        if cmds.objExists(tgt_hip_l) and cmds.objExists(tgt_knee_l) and cmds.objExists(tgt_ankle_l):
            p_hip = om.MVector(*cmds.xform(tgt_hip_l, q=True, ws=True, t=True))
            p_knee = om.MVector(*cmds.xform(tgt_knee_l, q=True, ws=True, t=True))
            p_ankle = om.MVector(*cmds.xform(tgt_ankle_l, q=True, ws=True, t=True))
            tgt_leg_len = (p_knee - p_hip).length() + (p_ankle - p_knee).length()

        tgt_sh_l = self.resolve_target("FKShoulder_L")
        tgt_el_l = self.resolve_target("FKElbow_L")
        tgt_wr_l = self.resolve_target("FKWrist_L")
        tgt_arm_len = 80.0
        if cmds.objExists(tgt_sh_l) and cmds.objExists(tgt_el_l) and cmds.objExists(tgt_wr_l):
            p_sh = om.MVector(*cmds.xform(tgt_sh_l, q=True, ws=True, t=True))
            p_el = om.MVector(*cmds.xform(tgt_el_l, q=True, ws=True, t=True))
            p_wr = om.MVector(*cmds.xform(tgt_wr_l, q=True, ws=True, t=True))
            tgt_arm_len = (p_el - p_sh).length() + (p_wr - p_el).length()

        leg_scale = tgt_leg_len / max(b_leg_len, 0.001)
        arm_scale = tgt_arm_len / max(b_arm_len, 0.001)

        v_b_spine = (b_neck - b_root).normal()
        pitch = math.degrees(math.atan2(v_b_spine.z, v_b_spine.y))
        roll = -math.degrees(math.atan2(v_b_spine.x, v_b_spine.y))

        fk_spine1 = self.resolve_target("FKSpine1_M")
        fk_chest = self.resolve_target("FKChest_M")
        if cmds.objExists(fk_spine1) and cmds.objExists(fk_chest):
            cmds.setAttr(f"{fk_spine1}.rx", pitch * 0.4)
            cmds.setAttr(f"{fk_spine1}.rz", roll * 0.4)
            cmds.setAttr(f"{fk_chest}.rx", pitch * 0.6)
            cmds.setAttr(f"{fk_chest}.rz", roll * 0.6)

        b_head = pos_dict["head"]
        v_b_head = (b_head - b_neck).normal()
        head_pitch = math.degrees(math.atan2(v_b_head.z, v_b_head.y))
        head_roll = -math.degrees(math.atan2(v_b_head.x, v_b_head.y))
        fk_neck = self.resolve_target("FKNeck_M")
        fk_head = self.resolve_target("FKHead_M")
        if cmds.objExists(fk_neck):
            cmds.setAttr(f"{fk_neck}.rx", head_pitch * 0.5)
            cmds.setAttr(f"{fk_neck}.rz", head_roll * 0.5)
        if cmds.objExists(fk_head):
            cmds.setAttr(f"{fk_head}.rx", head_pitch * 0.5)
            cmds.setAttr(f"{fk_head}.rz", head_roll * 0.5)

        limb_configs = [
            {
                "uparm": "l_shoulder", "lowarm": "l_elbow", "wrist": "l_wrist",
                "upleg": "l_hip", "lowleg": "l_knee", "foot": "l_ankle",
                "ik_arm": "IKArm_L", "pole_arm": "PoleArm_L", "fk_sh": "FKShoulder_L",
                "ik_leg": "IKLeg_L", "pole_leg": "PoleLeg_L", "fk_hip": "FKHip_L"
            },
            {
                "uparm": "r_shoulder", "lowarm": "r_elbow", "wrist": "r_wrist",
                "upleg": "r_hip", "lowleg": "r_knee", "foot": "r_ankle",
                "ik_arm": "IKArm_R", "pole_arm": "PoleArm_R", "fk_sh": "FKShoulder_R",
                "ik_leg": "IKLeg_R", "pole_leg": "PoleLeg_R", "fk_hip": "FKHip_R"
            }
        ]

        modified = [fk_spine1, fk_chest, fk_neck, fk_head]

        for cfg in limb_configs:
            if cfg["uparm"] in pos_dict and cfg["wrist"] in pos_dict:
                b_sh_pos = pos_dict[cfg["uparm"]]
                b_el_pos = pos_dict.get(cfg["lowarm"], b_sh_pos)
                b_wr_pos = pos_dict[cfg["wrist"]]
                v_arm = b_wr_pos - b_sh_pos
                v_el = b_el_pos - b_sh_pos

                tgt_sh = self.resolve_target(cfg["fk_sh"])
                tgt_ik_arm = self.resolve_target(cfg["ik_arm"])
                tgt_pole_arm = self.resolve_target(cfg["pole_arm"])

                if cmds.objExists(tgt_sh) and cmds.objExists(tgt_ik_arm):
                    tgt_sh_ws = om.MVector(*cmds.xform(tgt_sh, q=True, ws=True, t=True))
                    tgt_wrist_pos = tgt_sh_ws + v_arm * arm_scale
                    cmds.xform(tgt_ik_arm, ws=True, t=[tgt_wrist_pos.x, tgt_wrist_pos.y, tgt_wrist_pos.z])
                    modified.append(tgt_ik_arm)

                if cmds.objExists(tgt_sh) and cmds.objExists(tgt_pole_arm):
                    tgt_sh_ws = om.MVector(*cmds.xform(tgt_sh, q=True, ws=True, t=True))
                    tgt_elbow_pos = tgt_sh_ws + v_el * arm_scale * 1.6
                    cmds.xform(tgt_pole_arm, ws=True, t=[tgt_elbow_pos.x, tgt_elbow_pos.y, tgt_elbow_pos.z])
                    modified.append(tgt_pole_arm)

            if cfg["upleg"] in pos_dict and cfg["foot"] in pos_dict:
                b_hip_pos = pos_dict[cfg["upleg"]]
                b_kn_pos = pos_dict.get(cfg["lowleg"], b_hip_pos)
                b_ft_pos = pos_dict[cfg["foot"]]
                v_leg = b_ft_pos - b_hip_pos
                v_kn = b_kn_pos - b_hip_pos

                tgt_hip = self.resolve_target(cfg["fk_hip"])
                tgt_ik_leg = self.resolve_target(cfg["ik_leg"])
                tgt_pole_leg = self.resolve_target(cfg["pole_leg"])

                if cmds.objExists(tgt_hip) and cmds.objExists(tgt_ik_leg):
                    tgt_hip_ws = om.MVector(*cmds.xform(tgt_hip, q=True, ws=True, t=True))
                    tgt_ankle_pos = tgt_hip_ws + v_leg * leg_scale
                    cmds.xform(tgt_ik_leg, ws=True, t=[tgt_ankle_pos.x, tgt_ankle_pos.y, tgt_ankle_pos.z])
                    modified.append(tgt_ik_leg)

                if cmds.objExists(tgt_hip) and cmds.objExists(tgt_pole_leg):
                    tgt_hip_ws = om.MVector(*cmds.xform(tgt_hip, q=True, ws=True, t=True))
                    tgt_knee_pos = tgt_hip_ws + v_kn * leg_scale * 1.6
                    cmds.xform(tgt_pole_leg, ws=True, t=[tgt_knee_pos.x, tgt_knee_pos.y, tgt_knee_pos.z])
                    modified.append(tgt_pole_leg)

        if keyframe is not None:
            valid = [n for n in modified if cmds.objExists(n)]
            cmds.setKeyframe(valid, time=keyframe)
            print(f"[PoseRetargeter] Keyframed {len(valid)} controls at frame {keyframe}.")

        print("[PoseRetargeter] SUCCESS: Retargeted to Rig Controls!")
        return True


def retarget_sample_pose(sample_idx=1, target_namespace="", create_template=False, keyframe=None):
    sample_files = {
        1: r"D:\sam-3d-body\outputs\benchmark_results\01_human_standard_skeleton.json",
        2: r"D:\sam-3d-body\outputs\benchmark_results\02_human_dancing_skeleton.json",
        3: r"D:\sam-3d-body\outputs\benchmark_results\03_game_3d_ironman_skeleton.json",
        4: r"D:\sam-3d-body\outputs\benchmark_results\04_anime_illustration_skeleton.json",
        5: r"D:\sam-3d-body\outputs\benchmark_results\05_strong_perspective_skeleton.json",
        6: r"D:\sam-3d-body\outputs\benchmark_results\06_limb_occlusion_skeleton.json"
    }

    json_file = sample_files.get(sample_idx)
    if not json_file or not os.path.exists(json_file):
        print(f"[Error] Benchmark file not found for index {sample_idx}: {json_file}")
        return False

    retargeter = PoseRetargeter(target_prefix=target_namespace)
    if create_template:
        retargeter.build_or_update_template_b(json_file)
    retargeter.retarget_pose(json_file, use_ik=True, keyframe=keyframe)
    return True


if __name__ == "__main__":
    retarget_sample_pose(sample_idx=2, target_namespace="", keyframe=cmds.currentTime(q=True))
