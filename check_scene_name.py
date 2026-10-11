import maya.cmds as cmds
import json

def check_current_scene():
    sn = cmds.file(q=True, sceneName=True)
    all_roots = cmds.ls(assemblies=True)
    all_joints = cmds.ls(type='joint') or []
    top_joints = [j for j in all_joints if not cmds.listRelatives(j, parent=True, type='joint')]
    print("CURRENT_SCENE:" + json.dumps({
        'scene_name': sn,
        'assemblies': all_roots,
        'top_joints': top_joints,
        'joint_count': len(all_joints),
        'joints_sample': all_joints[:20]
    }))

if __name__ == '__main__':
    check_current_scene()
