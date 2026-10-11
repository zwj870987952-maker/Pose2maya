import maya.cmds as cmds
import json

def inspect():
    joints = cmds.ls(type='joint') or []
    top_joints = [j for j in joints if not cmds.listRelatives(j, parent=True, type='joint')]
    transforms = cmds.ls(assemblies=True) or []
    result = {
        'top_joints': top_joints,
        'all_joints_count': len(joints),
        'top_transforms': transforms,
        'joints_sample': joints[:20]
    }
    print("SCENE_INSPECT_RESULT:" + json.dumps(result))

if __name__ == '__main__':
    inspect()
