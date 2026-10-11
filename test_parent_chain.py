import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

cmds.file(new=True, force=True)
j0 = cmds.joint(p=(10, 20, 30))
cmds.setAttr(f"{j0}.r", 15, 25, 35)
j1 = cmds.joint(p=(40, 50, 60))
cmds.setAttr(f"{j1}.jointOrient", 10, 20, 30)
cmds.setAttr(f"{j1}.r", 5, 10, 15)

w0 = om.MMatrix(cmds.getAttr(f"{j0}.worldMatrix[0]"))
w1 = om.MMatrix(cmds.getAttr(f"{j1}.worldMatrix[0]"))
l1 = om.MMatrix(cmds.getAttr(f"{j1}.matrix"))

# In OpenMaya, row vectors: v' = v * M
# Child world matrix = l1 * w0 or w0 * l1?
m_test1 = l1 * w0
m_test2 = w0 * l1

def mat_diff(m1, m2):
    return sum(abs(m1.getElement(i, j) - m2.getElement(i, j)) for i in range(4) for j in range(4))

print("Diff child world matrix vs (l1 * w0):", mat_diff(w1, m_test1))
print("Diff child world matrix vs (w0 * l1):", mat_diff(w1, m_test2))
