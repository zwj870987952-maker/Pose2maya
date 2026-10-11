import maya.cmds as cmds
import json

def inspect_joint_orient():
    joints = ["Root_M", "Spine1_M", "Chest_M", "Shoulder_L", "Elbow_L", "Wrist_L", "Hip_L", "Knee_L", "Ankle_L"]
    res = {}
    for j in joints:
        if cmds.objExists(j):
            res[j] = {
                'jo': cmds.getAttr(f"{j}.jointOrient")[0],
                'r': cmds.getAttr(f"{j}.r")[0],
                'ro': cmds.getAttr(f"{j}.rotateOrder"),
                'ws_t': cmds.xform(j, q=True, ws=True, t=True),
                'ws_ro': cmds.xform(j, q=True, ws=True, ro=True)
            }
    print("JOINT_ORIENT_INFO:" + json.dumps(res, indent=2))

if __name__ == '__main__':
    inspect_joint_orient()
