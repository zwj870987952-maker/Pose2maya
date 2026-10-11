import os
import json
import math
import maya.cmds as cmds
import maya.api.OpenMaya as om

def orient_joint(parent_joint, child_joint, target_dir):
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

    w_mat = om.MMatrix(cmds.getAttr(f"{parent_joint}.worldMatrix[0]"))
    tr_w = om.MTransformationMatrix(w_mat)
    w_rot_init = tr_w.asRotateMatrix()
    w_rot_target = w_rot_init * m_swing

    parent_node = cmds.listRelatives(parent_joint, p=True)
    if parent_node and cmds.objExists(parent_node[0]):
        w_parent_mat = om.MMatrix(cmds.getAttr(f"{parent_node[0]}.worldMatrix[0]"))
        tr_parent_w = om.MTransformationMatrix(w_parent_mat)
        w_parent_rot = tr_parent_w.asRotateMatrix()
    else:
        w_parent_rot = om.MMatrix.kIdentity

    jo_vals = [math.radians(x) for x in cmds.getAttr(f"{parent_joint}.jointOrient")[0]]
    jo_euler = om.MEulerRotation(jo_vals, om.MEulerRotation.kXYZ)
    m_jo = jo_euler.asMatrix()

    m_r = w_rot_target * (m_jo * w_parent_rot).inverse()

    ro_int = cmds.getAttr(f"{parent_joint}.rotateOrder")
    tr_r = om.MTransformationMatrix(m_r)
    euler_r = tr_r.rotation(asQuaternion=False)
    euler_r.reorderIt(ro_int)

    rx = math.degrees(euler_r.x)
    ry = math.degrees(euler_r.y)
    rz = math.degrees(euler_r.z)
    cmds.setAttr(f"{parent_joint}.r", rx, ry, rz)

def apply_pose_clean(json_path, frame_num):
    cmds.currentTime(frame_num)

    target_joints = [
        "Root_M", "Spine1_M", "Spine2_M", "Chest_M", "Neck_M", "Head_M",
        "Scapula_L", "Shoulder_L", "Elbow_L", "Wrist_L",
        "Scapula_R", "Shoulder_R", "Elbow_R", "Wrist_R",
        "Hip_L", "Knee_L", "Ankle_L",
        "Hip_R", "Knee_R", "Ankle_R"
    ]

    # Reset all target joints to 0 local rotation first
    for j in target_joints:
        if cmds.objExists(j):
            cmds.setAttr(f"{j}.r", 0, 0, 0)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    world_pos = data["skeleton"]["world_positions"]

    def get_v(idx):
        p = world_pos[idx]
        return om.MVector(p[0], -p[1], -p[2])

    # 1. Spine
    v_spine = (get_v(37) - get_v(1)).normal()
    orient_joint("Root_M", "Spine1_M", v_spine)
    orient_joint("Spine1_M", "Spine2_M", v_spine)
    orient_joint("Spine2_M", "Chest_M", (get_v(37) - get_v(35)).normal())
    orient_joint("Chest_M", "Neck_M", (get_v(110) - get_v(37)).normal())
    orient_joint("Neck_M", "Head_M", (get_v(113) - get_v(110)).normal())

    # 2. Left Arm
    orient_joint("Scapula_L", "Shoulder_L", (get_v(75) - get_v(74)).normal())
    orient_joint("Shoulder_L", "Elbow_L", (get_v(76) - get_v(75)).normal())
    orient_joint("Elbow_L", "Wrist_L", (get_v(77) - get_v(76)).normal())

    # 3. Right Arm
    orient_joint("Scapula_R", "Shoulder_R", (get_v(39) - get_v(38)).normal())
    orient_joint("Shoulder_R", "Elbow_R", (get_v(40) - get_v(39)).normal())
    orient_joint("Elbow_R", "Wrist_R", (get_v(41) - get_v(40)).normal())

    # 4. Left Leg
    orient_joint("Hip_L", "Knee_L", (get_v(3) - get_v(2)).normal())
    orient_joint("Knee_L", "Ankle_L", (get_v(4) - get_v(3)).normal())

    # 5. Right Leg
    orient_joint("Hip_R", "Knee_R", (get_v(19) - get_v(18)).normal())
    orient_joint("Knee_R", "Ankle_R", (get_v(20) - get_v(19)).normal())

    # Keyframe
    valid_joints = [j for j in target_joints if cmds.objExists(j)]
    cmds.setKeyframe(valid_joints, time=frame_num)

    r_sh = cmds.getAttr("Shoulder_L.r")[0]
    r_hp = cmds.getAttr("Hip_L.r")[0]
    print(f"Frame {frame_num:2d} ({os.path.basename(json_path)}) -> Shoulder_L: [{r_sh[0]:.1f}, {r_sh[1]:.1f}, {r_sh[2]:.1f}] | Hip_L: [{r_hp[0]:.1f}, {r_hp[1]:.1f}, {r_hp[2]:.1f}]")

def run():
    cmds.file(r"C:\Users\zwj87\Desktop\sk_test.ma", open=True, force=True)
    cmds.playbackOptions(min=1, max=60, animationStartTime=1, animationEndTime=60)

    benchmarks = [
        (1, r"D:\sam-3d-body\outputs\benchmark_results\01_human_standard_skeleton.json"),
        (10, r"D:\sam-3d-body\outputs\benchmark_results\02_human_dancing_skeleton.json"),
        (20, r"D:\sam-3d-body\outputs\benchmark_results\03_game_3d_ironman_skeleton.json"),
        (30, r"D:\sam-3d-body\outputs\benchmark_results\04_anime_illustration_skeleton.json"),
        (40, r"D:\sam-3d-body\outputs\benchmark_results\05_strong_perspective_skeleton.json"),
        (50, r"D:\sam-3d-body\outputs\benchmark_results\06_limb_occlusion_skeleton.json"),
    ]

    for f, p in benchmarks:
        if os.path.exists(p):
            apply_pose_clean(p, f)

if __name__ == '__main__':
    run()
