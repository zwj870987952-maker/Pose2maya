import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

cmds.file(new=True, force=True)

# Create parent joint with jointOrient
j0 = cmds.joint(p=(10, 20, 30))
cmds.setAttr(f"{j0}.jointOrient", 45, 30, 20)
cmds.setAttr(f"{j0}.r", 15, 25, 35)

# Child joint with jointOrient and rotateOrder 5 (ZYX)
j1 = cmds.joint(p=(40, 50, 60))
cmds.setAttr(f"{j1}.jointOrient", -28.5, 53.5, -14.5)
cmds.setAttr(f"{j1}.rotateOrder", 5)

# End child to visualize direction
j2 = cmds.joint(p=(70, 50, 60))

# Current world positions
p1_init = om.MVector(*cmds.xform(j1, q=True, ws=True, t=True))
p2_init = om.MVector(*cmds.xform(j2, q=True, ws=True, t=True))
curr_dir = (p2_init - p1_init).normal()
print(f"Initial bone dir: [{curr_dir.x:.3f}, {curr_dir.y:.3f}, {curr_dir.z:.3f}]")

# Desired direction
des_dir = om.MVector(0, 1, 0).normal()
q_swing = om.MQuaternion(curr_dir, des_dir)

# 1. Current world rotation of j1
w1_mat = om.MMatrix(cmds.getAttr(f"{j1}.worldMatrix[0]"))
tr_w1 = om.MTransformationMatrix(w1_mat)
q_w1 = tr_w1.rotation(asQuaternion=True)

# 2. Target world rotation
# Since v_new = v_curr.rotateBy(q_swing), in OpenMaya row vectors:
# new world rot matrix = q_curr_as_mat * q_swing_as_mat? Or q_swing * q_curr?
# Let's test rotating the direction:
# A vector v in world space rotated by q_swing: v_target = v.rotateBy(q_swing)
# For the world matrix W_target: its rotation rows are rotated by q_swing!
m_swing = q_swing.asMatrix()
# In OpenMaya row vectors: W_rot_target = W_rot_init * m_swing
w_rot_init = tr_w1.asRotateMatrix()
w_rot_target = w_rot_init * m_swing

# 3. Solve local M_R:
# W_rot = M_R * M_JO * W_parent_rot
# => M_R = W_rot_target * (M_JO * W_parent_rot).inverse()
w0_mat = om.MMatrix(cmds.getAttr(f"{j0}.worldMatrix[0]"))
tr_w0 = om.MTransformationMatrix(w0_mat)
w_parent_rot = tr_w0.asRotateMatrix()

jo_vals = [math.radians(x) for x in cmds.getAttr(f"{j1}.jointOrient")[0]]
jo_euler = om.MEulerRotation(jo_vals, om.MEulerRotation.kXYZ)
m_jo = jo_euler.asMatrix()

m_r = w_rot_target * (m_jo * w_parent_rot).inverse()

# 4. Extract Euler angles in j1's rotateOrder
ro_int = cmds.getAttr(f"{j1}.rotateOrder")
tr_r = om.MTransformationMatrix(m_r)
euler_r = tr_r.rotation(asQuaternion=False)
euler_r.reorderIt(ro_int)

rx = math.degrees(euler_r.x)
ry = math.degrees(euler_r.y)
rz = math.degrees(euler_r.z)
print(f"Setting local rotation on j1: [{rx:.2f}, {ry:.2f}, {rz:.2f}]")

cmds.setAttr(f"{j1}.r", rx, ry, rz)

# 5. Verify the new bone direction!
p1_after = om.MVector(*cmds.xform(j1, q=True, ws=True, t=True))
p2_after = om.MVector(*cmds.xform(j2, q=True, ws=True, t=True))
new_dir = (p2_after - p1_after).normal()
dot = new_dir * des_dir
print(f"New bone dir: [{new_dir.x:.3f}, {new_dir.y:.3f}, {new_dir.z:.3f}]")
print(f"Target dir:   [{des_dir.x:.3f}, {des_dir.y:.3f}, {des_dir.z:.3f}]")
print(f"DOT PRODUCT:  {dot:.6f}")
