import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

cmds.file(new=True, force=True)

# Create a test joint
j1 = cmds.joint(p=(0, 0, 0))
j2 = cmds.joint(p=(10, 0, 0))

# Current vector is (1, 0, 0)
# We want it to point at (0, 1, 0)
v_curr = om.MVector(1, 0, 0)
v_des = om.MVector(0, 1, 0)
q_swing = om.MQuaternion(v_curr, v_des) # 90 deg around Z

# Get current world matrix of j1
m_curr = om.MMatrix(cmds.xform(j1, q=True, ws=True, m=True))
tr_curr = om.MTransformationMatrix(m_curr)
q_curr = tr_curr.rotation(asQuaternion=True)

q_new = q_swing * q_curr
tr_new = om.MTransformationMatrix()
tr_new.setRotation(q_new)
euler = tr_new.rotation(asQuaternion=False)

print(f"euler XYZ: [{math.degrees(euler.x):.1f}, {math.degrees(euler.y):.1f}, {math.degrees(euler.z):.1f}]")

cmds.xform(j1, ws=True, ro=[math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z)])

p2 = om.MVector(*cmds.xform(j2, q=True, ws=True, t=True))
print(f"j2 pos after simple xform: [{p2.x:.1f}, {p2.y:.1f}, {p2.z:.1f}]")
