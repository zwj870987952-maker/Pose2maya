import maya.cmds as cmds

def reset_all_joints():
    joints = cmds.ls(type='joint') or []
    for j in joints:
        try:
            cmds.setAttr(f"{j}.r", 0, 0, 0)
        except Exception:
            pass
    print(f"RESET_DONE: Reset {len(joints)} joints to (0,0,0)")

if __name__ == '__main__':
    reset_all_joints()
