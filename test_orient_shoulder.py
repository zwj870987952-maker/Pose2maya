import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

cmds.file(r"C:\Users\zwj87\Desktop\sk_test.ma", open=True, force=True)

def orient_bone(parent_joint, child_joint, target_dir):
    p_parent = om.MVector(*cmds.xform(parent_joint, q=True, ws=True, t=True))
    p_child = om.MVector(*cmds.xform(child_joint, q=True, ws=True, t=True))
    curr_dir = (p_child - p_parent).normal()
    des_dir = target_dir.normal()
    
    print(f"Parent: {parent_joint}, Child: {child_joint}")
    print(f"  Init dir:   [{curr_dir.x:.3f}, {curr_dir.y:.3f}, {curr_dir.z:.3f}]")
    print(f"  Target dir: [{des_dir.x:.3f}, {des_dir.y:.3f}, {des_dir.z:.3f}]")
    
    q_swing = om.MQuaternion(curr_dir, des_dir)
    m_swing = q_swing.asMatrix()
    
    w_mat = om.MMatrix(cmds.getAttr(f"{parent_joint}.worldMatrix[0]"))
    tr_w = om.MTransformationMatrix(w_mat)
    w_rot_init = tr_w.asRotateMatrix()
    w_rot_target = w_rot_init * m_swing
    
    parent_node = cmds.listRelatives(parent_joint, p=True)
    if parent_node:
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
    print(f"  Setting r: [{rx:.2f}, {ry:.2f}, {rz:.2f}]")
    cmds.setAttr(f"{parent_joint}.r", rx, ry, rz)
    
    p_parent_after = om.MVector(*cmds.xform(parent_joint, q=True, ws=True, t=True))
    p_child_after = om.MVector(*cmds.xform(child_joint, q=True, ws=True, t=True))
    new_dir = (p_child_after - p_parent_after).normal()
    print(f"  Result dir: [{new_dir.x:.3f}, {new_dir.y:.3f}, {new_dir.z:.3f}]")
    print(f"  Dot product: {new_dir * des_dir:.6f}")

target_l_arm = om.MVector(0.143, -0.968, -0.205)
orient_bone("Shoulder_L", "Elbow_L", target_l_arm)
