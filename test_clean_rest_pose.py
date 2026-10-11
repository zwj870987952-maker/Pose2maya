import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

# Reload sk_test.ma cleanly
cmds.file(r"C:\Users\zwj87\Desktop\sk_test.ma", open=True, force=True)

print("Freshly loaded scene.")
# Check rest pose of key joints
for j in ["Root_M", "Spine1_M", "Chest_M", "Neck_M", "Head_M", "Shoulder_L", "Elbow_L", "Wrist_L", "Hip_L", "Knee_L", "Ankle_L"]:
    p = cmds.xform(j, q=True, ws=True, t=True)
    r = cmds.getAttr(f"{j}.r")[0]
    jo = cmds.getAttr(f"{j}.jointOrient")[0]
    ro = cmds.getAttr(f"{j}.rotateOrder")
    print(f"{j:12s} | ws_pos: [{p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f}] | r: [{r[0]:.1f}, {r[1]:.1f}, {r[2]:.1f}] | jo: [{jo[0]:.1f}, {jo[1]:.1f}, {jo[2]:.1f}] | ro: {ro}")
