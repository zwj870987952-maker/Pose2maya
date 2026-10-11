import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

cmds.file(new=True, force=True)
j = cmds.joint(p=(0, 0, 0))
cmds.setAttr(f"{j}.jointOrient", 30, 45, 60)
cmds.setAttr(f"{j}.r", 10, 20, 30)

m_list = cmds.getAttr(f"{j}.matrix")
m = om.MMatrix(m_list)

jo_euler = om.MEulerRotation([math.radians(x) for x in [30, 45, 60]], om.MEulerRotation.kXYZ)
r_euler = om.MEulerRotation([math.radians(x) for x in [10, 20, 30]], om.MEulerRotation.kXYZ)

m_jo = jo_euler.asMatrix()
m_r = r_euler.asMatrix()

m_r_jo = m_r * m_jo
m_jo_r = m_jo * m_r

def get_m(mat, r, c):
    # In OpenMaya 2.0, mat.getElement(r, c)
    return mat.getElement(r, c)

def rot_equal(m1, m2):
    diff = 0
    for i in range(3):
        for j_idx in range(3):
            diff += abs(get_m(m1, i, j_idx) - get_m(m2, i, j_idx))
    return diff

print("Diff with R * JO:", rot_equal(m, m_r_jo))
print("Diff with JO * R:", rot_equal(m, m_jo_r))
