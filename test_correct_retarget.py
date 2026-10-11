import os
import json
import math
import maya.cmds as cmds
import maya.api.OpenMaya as om

# Ground-truth MHR 127 Joint Indices verified from character_torch.skeleton
MHR_INDICES = {
    "root": 0,
    "pelvis": 1,
    "spine1": 34,
    "spine2": 35,
    "spine3": 36,
    "chest": 37,
    "neck": 110,
    "head": 113,
    "r_clavicle": 38,
    "r_shoulder": 39,
    "r_elbow": 40,
    "r_wrist": 41,
    "l_clavicle": 74,
    "l_shoulder": 75,
    "l_elbow": 76,
    "l_wrist": 77,
    "r_hip": 2,
    "r_knee": 3,
    "r_ankle": 4,
    "l_hip": 18,
    "l_knee": 19,
    "l_ankle": 20,
}

def rotate_joint_to_vector(parent_joint, child_joint, target_dir):
    """
    Rotates parent_joint so that the bone vector towards child_joint aligns with target_dir.
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

    # Shortest Arc Swing
    q_swing = om.MQuaternion(curr_dir, des_dir)

    # Current world matrix & quaternion
    m_parent_list = cmds.xform(parent_joint, q=True, ws=True, m=True)
    m_parent = om.MMatrix(m_parent_list)
    tr_parent = om.MTransformationMatrix(m_parent)
    q_curr_world = tr_parent.rotation(asQuaternion=True)

    # New world quaternion
    q_new_world = q_swing * q_curr_world
    tr_new = om.MTransformationMatrix()
    tr_new.setRotation(q_new_world)
    euler = tr_new.rotation(asQuaternion=False)

    cmds.xform(parent_joint, ws=True, ro=[math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z)])

def run_test(json_path):
    # 1. Reset all joints to zero first
    for j in cmds.ls(type='joint') or []:
        try:
            cmds.setAttr(f"{j}.r", 0, 0, 0)
        except Exception:
            pass

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    world_positions = data["skeleton"]["world_positions"]

    # Convert Camera Frame [x, y, z] to Maya [x, -y, -z]
    pos = {}
    for name, idx in MHR_INDICES.items():
        p = world_positions[idx]
        pos[name] = om.MVector(p[0], -p[1], -p[2])

    print(">>> MHR Ground Truth Positions Loaded:")
    print("  Head:", pos["head"])
    print("  Neck:", pos["neck"])
    print("  Chest:", pos["chest"])
    print("  Pelvis:", pos["pelvis"])
    print("  L Shoulder -> L Elbow:", (pos["l_elbow"] - pos["l_shoulder"]).normal())
    print("  R Shoulder -> R Elbow:", (pos["r_elbow"] - pos["r_shoulder"]).normal())
    print("  L Hip -> L Knee:", (pos["l_knee"] - pos["l_hip"]).normal())
    print("  R Hip -> R Knee:", (pos["r_knee"] - pos["r_hip"]).normal())

    # 1. Spine
    v_spine = (pos["neck"] - pos["pelvis"]).normal()
    rotate_joint_to_vector("Spine1_M", "Spine2_M", v_spine)
    rotate_joint_to_vector("Spine2_M", "Chest_M", v_spine)
    rotate_joint_to_vector("Chest_M", "Neck_M", v_spine)

    # 2. Neck & Head
    v_head = (pos["head"] - pos["neck"]).normal()
    rotate_joint_to_vector("Neck_M", "Head_M", v_head)

    # 3. Left Arm
    v_l_uparm = (pos["l_elbow"] - pos["l_shoulder"]).normal()
    rotate_joint_to_vector("Shoulder_L", "Elbow_L", v_l_uparm)
    v_l_lowarm = (pos["l_wrist"] - pos["l_elbow"]).normal()
    rotate_joint_to_vector("Elbow_L", "Wrist_L", v_l_lowarm)

    # 4. Right Arm
    v_r_uparm = (pos["r_elbow"] - pos["r_shoulder"]).normal()
    rotate_joint_to_vector("Shoulder_R", "Elbow_R", v_r_uparm)
    v_r_lowarm = (pos["r_wrist"] - pos["r_elbow"]).normal()
    rotate_joint_to_vector("Elbow_R", "Wrist_R", v_r_lowarm)

    # 5. Left Leg
    v_l_upleg = (pos["l_knee"] - pos["l_hip"]).normal()
    rotate_joint_to_vector("Hip_L", "Knee_L", v_l_upleg)
    v_l_lowleg = (pos["l_ankle"] - pos["l_knee"]).normal()
    rotate_joint_to_vector("Knee_L", "Ankle_L", v_l_lowleg)

    # 6. Right Leg
    v_r_upleg = (pos["r_knee"] - pos["r_hip"]).normal()
    rotate_joint_to_vector("Hip_R", "Knee_R", v_r_upleg)
    v_r_lowleg = (pos["r_ankle"] - pos["r_knee"]).normal()
    rotate_joint_to_vector("Knee_R", "Ankle_R", v_r_lowleg)

    # Take Snapshot to verify visually
    out_img = r"C:\Users\zwj87\Documents\Pose2maya\test_correct_f1.jpg"
    cmds.select("Geo", r=True) if cmds.objExists("Geo") else None
    cmds.viewFit("persp", animate=False)
    cmds.select(cl=True)
    cmds.playblast(
        frame=[1],
        format='image',
        compression='jpg',
        completeFilename=out_img,
        showOrnaments=False,
        viewer=False,
        widthHeight=[512, 512],
        percent=100,
        forceOverwrite=True
    )
    print(f">>> TEST COMPLETED, SNAPSHOT SAVED: {out_img}")

if __name__ == '__main__':
    run_test(r"D:\sam-3d-body\outputs\benchmark_results\01_human_standard_skeleton.json")
