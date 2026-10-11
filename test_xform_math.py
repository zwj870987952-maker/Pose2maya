import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

cmds.file(r"C:\Users\zwj87\Desktop\sk_test.ma", open=True, force=True)

joint = "Shoulder_L"
child = "Elbow_L"

p_parent = om.MVector(*cmds.xform(joint, q=True, ws=True, t=True))
p_child = om.MVector(*cmds.xform(child, q=True, ws=True, t=True))
curr_dir = (p_child - p_parent).normal()
print("Before:")
print(f"  Parent ws pos: {p_parent}")
print(f"  Child ws pos: {p_child}")
print(f"  Bone dir: {curr_dir}")
print(f"  Joint rotate: {cmds.getAttr(f'{joint}.r')}")
print(f"  Joint JO: {cmds.getAttr(f'{joint}.jointOrient')}")
print(f"  Joint RO: {cmds.getAttr(f'{joint}.rotateOrder')}")

des_dir = om.MVector(0.143, -0.968, -0.205).normal()
q_swing = om.MQuaternion(curr_dir, des_dir)

# Current world matrix
m_parent = om.MMatrix(cmds.xform(joint, q=True, ws=True, m=True))
tr_parent = om.MTransformationMatrix(m_parent)
q_curr = tr_parent.rotation(asQuaternion=True)

q_new = q_swing * q_curr
tr_new = om.MTransformationMatrix()
tr_new.setRotation(q_new)
euler = tr_new.rotation(asQuaternion=False)

print(f"Applying ws ro: {[math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z)]}")
cmds.xform(joint, ws=True, ro=[math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z)])

p_parent_after = om.MVector(*cmds.xform(joint, q=True, ws=True, t=True))
p_child_after = om.MVector(*cmds.xform(child, q=True, ws=True, t=True))
new_dir = (p_child_after - p_parent_after).normal()
print("After cmds.xform ws ro:")
print(f"  Parent ws pos: {p_parent_after}")
print(f"  Child ws pos: {p_child_after}")
print(f"  New Bone dir: {new_dir}")
print(f"  Target dir was: {des_dir}")
print(f"  Dot with target: {new_dir * des_dir}")
print(f"  Joint rotate after: {cmds.getAttr(f'{joint}.r')}")
