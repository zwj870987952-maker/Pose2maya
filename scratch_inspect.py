import maya.cmds as cmds
import maya.api.OpenMaya as om

print("=== SCENE INFO ===")
print("Scene:", cmds.file(q=True, sn=True))
print("Joint count:", len(cmds.ls(type="joint") or []))

joints_to_check = ["Root_M", "Spine1_M", "Spine2_M", "Chest_M", "Neck_M", "Head_M", 
                   "Shoulder_L", "Elbow_L", "Wrist_L", "Hip_L", "Knee_L", "Ankle_L"]
for j in joints_to_check:
    if cmds.objExists(j):
        r = cmds.getAttr(f"{j}.r")[0]
        jo = cmds.getAttr(f"{j}.jointOrient")[0]
        ro = cmds.getAttr(f"{j}.rotateOrder")
        t = cmds.xform(j, q=True, ws=True, t=True)
        print(f"{j:12s} | t: [{t[0]:.1f}, {t[1]:.1f}, {t[2]:.1f}] | r: [{r[0]:.1f}, {r[1]:.1f}, {r[2]:.1f}] | jo: [{jo[0]:.1f}, {jo[1]:.1f}, {jo[2]:.1f}] | ro: {ro}")
    else:
        print(f"{j:12s} NOT FOUND")
