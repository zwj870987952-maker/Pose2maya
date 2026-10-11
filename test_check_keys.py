import maya.cmds as cmds

for j in ["Shoulder_L", "Hip_L", "Spine1_M"]:
    keys = cmds.keyframe(j, q=True, timeChange=True)
    print(f"{j} key times: {sorted(list(set(keys))) if keys else 'No keys'}")
