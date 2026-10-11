import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

cmds.file(new=True, force=True)

# Create a parent joint with jointOrient
j0 = cmds.joint(p=(0, 0, 0))
cmds.setAttr(f"{j0}.jointOrient", 45, 30, 20)

j1 = cmds.joint(p=(10, 0, 0))
cmds.setAttr(f"{j1}.jointOrient", -28.5, 53.5, -14.5)
cmds.setAttr(f"{j1}.rotateOrder", 5) # ZYX

j2 = cmds.joint(p=(20, 0, 0))

p1 = om.MVector(*cmds.xform(j1, q=True, ws=True, t=True))
p2 = om.MVector(*cmds.xform(j2, q=True, ws=True, t=True))
curr_dir = (p2 - p1).normal()
print(f"curr_dir: {curr_dir}")

des_dir = om.MVector(0, 1, 0)
q_swing = om.MQuaternion(curr_dir, des_dir)

m_curr = om.MMatrix(cmds.xform(j1, q=True, ws=True, m=True))
tr_curr = om.MTransformationMatrix(m_curr)
q_curr = tr_curr.rotation(asQuaternion=True)

q_new = q_swing * q_curr
tr_new = om.MTransformationMatrix()
tr_new.setRotation(q_new)
euler = tr_new.rotation(asQuaternion=False)

print("Attempt 1: cmds.xform ws=True, ro=[math.degrees(euler.x), ...]")
cmds.xform(j1, ws=True, ro=[math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z)])

p2_after = om.MVector(*cmds.xform(j2, q=True, ws=True, t=True))
new_dir = (p2_after - p1).normal()
print(f"new_dir: {new_dir}, target: {des_dir}, dot: {new_dir * des_dir}")
