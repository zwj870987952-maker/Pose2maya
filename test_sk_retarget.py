import os
import json
import math
import maya.cmds as cmds
import maya.api.OpenMaya as om

MHR_INDEX_TO_NAME = {
    0: 'root', 1: 'c_spine0', 2: 'c_spine1', 3: 'c_spine2', 4: 'c_spine3', 5: 'c_neck', 6: 'c_head',
    7: 'r_clavicle', 8: 'r_uparm', 9: 'r_lowarm', 10: 'r_wrist_twist', 11: 'r_wrist',
    12: 'l_clavicle', 13: 'l_uparm', 14: 'l_lowarm', 15: 'l_wrist_twist', 16: 'l_wrist',
    17: 'r_upleg', 18: 'r_lowleg', 19: 'r_foot', 20: 'r_talocrural', 21: 'r_subtalar', 22: 'r_transversetarsal', 23: 'r_ball',
    24: 'l_upleg', 25: 'l_lowleg', 26: 'l_foot', 27: 'l_talocrural', 28: 'l_subtalar', 29: 'l_transversetarsal', 30: 'l_ball'
}

def rotate_joint_to_vector(parent_joint, child_joint, target_dir):
    """
    Rotates parent_joint in Maya so that the vector pointing to child_joint aligns with target_dir.
    Uses Shortest Arc Swing Quaternion in Maya World Space.
    """
    if not cmds.objExists(parent_joint) or not cmds.objExists(child_joint):
        return

    # 1. Get current world positions
    p_parent = om.MVector(*cmds.xform(parent_joint, q=True, ws=True, t=True))
    p_child = om.MVector(*cmds.xform(child_joint, q=True, ws=True, t=True))

    curr_dir = (p_child - p_parent).normal()
    des_dir = target_dir.normal()

    # If angle is too small or vectors are identical, skip
    dot = curr_dir * des_dir
    if dot > 0.99999 or curr_dir.length() < 0.001 or des_dir.length() < 0.001:
        return

    # Shortest Arc Quaternion (Swing)
    q_swing = om.MQuaternion(curr_dir, des_dir)

    # 2. Get parent joint's current world matrix & rotation
    m_parent_list = cmds.xform(parent_joint, q=True, ws=True, m=True)
    m_parent = om.MMatrix(m_parent_list)
    tr_parent = om.MTransformationMatrix(m_parent)
    q_curr_world = tr_parent.rotation(asQuaternion=True)

    # 3. New world rotation: Q_new = Q_swing * Q_curr
    q_new_world = q_swing * q_curr_world

    # 4. Convert new world rotation to parent space (local rotation)
    p_node = cmds.listRelatives(parent_joint, parent=True, fullPath=True)
    if p_node:
        m_pnode_list = cmds.xform(p_node[0], q=True, ws=True, m=True)
        m_pnode = om.MMatrix(m_pnode_list)
        tr_pnode = om.MTransformationMatrix(m_pnode)
        q_pnode_world = tr_pnode.rotation(asQuaternion=True)
        # Q_local = Q_parent^-1 * Q_world
        q_local = q_pnode_world.inverse() * q_new_world
    else:
        q_local = q_new_world

    # 5. Extract Euler angles in joint's rotation order
    rot_order = cmds.getAttr(f"{parent_joint}.rotateOrder")
    euler = q_local.asEulerRotation()
    # Convert radians to degrees
    deg_x = math.degrees(euler.x)
    deg_y = math.degrees(euler.y)
    deg_z = math.degrees(euler.z)

    cmds.setAttr(f"{parent_joint}.r", deg_x, deg_y, deg_z)

def test_retarget_sk_test(json_path):
    print(f"[Testing] Retargeting {json_path} onto sk_test joints...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    joint_names = data["skeleton"]["joint_names"]
    world_positions = data["skeleton"]["world_positions"]

    # Parse pos dict
    pos_dict = {}
    for i, (name, p) in enumerate(zip(joint_names, world_positions)):
        anat_name = MHR_INDEX_TO_NAME.get(i, name)
        # Convert Camera Frame (X-right, Y-down, Z-forward) to Maya (X-right, Y-up, Z-depth)
        pos_dict[anat_name] = om.MVector(p[0], -p[1], -p[2])

    # 1. Torso Spine Direction
    v_spine = (pos_dict["c_neck"] - pos_dict["root"]).normal()
    rotate_joint_to_vector("Spine1_M", "Spine2_M", v_spine)
    rotate_joint_to_vector("Spine2_M", "Chest_M", v_spine)
    rotate_joint_to_vector("Chest_M", "Neck_M", v_spine)

    # 2. Neck & Head
    v_head = (pos_dict["c_head"] - pos_dict["c_neck"]).normal()
    rotate_joint_to_vector("Neck_M", "Head_M", v_head)

    # 3. Left Arm
    v_l_uparm = (pos_dict["l_lowarm"] - pos_dict["l_uparm"]).normal()
    rotate_joint_to_vector("Shoulder_L", "Elbow_L", v_l_uparm)
    v_l_lowarm = (pos_dict["l_wrist"] - pos_dict["l_lowarm"]).normal()
    rotate_joint_to_vector("Elbow_L", "Wrist_L", v_l_lowarm)

    # 4. Right Arm
    v_r_uparm = (pos_dict["r_lowarm"] - pos_dict["r_uparm"]).normal()
    rotate_joint_to_vector("Shoulder_R", "Elbow_R", v_r_uparm)
    v_r_lowarm = (pos_dict["r_wrist"] - pos_dict["r_lowarm"]).normal()
    rotate_joint_to_vector("Elbow_R", "Wrist_R", v_r_lowarm)

    # 5. Left Leg
    v_l_upleg = (pos_dict["l_lowleg"] - pos_dict["l_upleg"]).normal()
    rotate_joint_to_vector("Hip_L", "Knee_L", v_l_upleg)
    v_l_lowleg = (pos_dict["l_foot"] - pos_dict["l_lowleg"]).normal()
    rotate_joint_to_vector("Knee_L", "Ankle_L", v_l_lowleg)

    # 6. Right Leg
    v_r_upleg = (pos_dict["r_lowleg"] - pos_dict["r_upleg"]).normal()
    rotate_joint_to_vector("Hip_R", "Knee_R", v_r_upleg)
    v_r_lowleg = (pos_dict["r_foot"] - pos_dict["r_lowleg"]).normal()
    rotate_joint_to_vector("Knee_R", "Ankle_R", v_r_lowleg)

    print("[Testing] SUCCESS: sk_test joints retargeted successfully!")

if __name__ == '__main__':
    sample_json = r"D:\sam-3d-body\outputs\benchmark_results\02_human_dancing_skeleton.json"
    test_retarget_sk_test(sample_json)
