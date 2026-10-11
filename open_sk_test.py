import maya.cmds as cmds
import json

def open_sk_test():
    file_path = "C:/Users/zwj87/Desktop/sk_test.ma"
    cmds.file(file_path, open=True, force=True)
    
    # Query scene contents
    joints = cmds.ls(type='joint') or []
    top_joints = [j for j in joints if not cmds.listRelatives(j, parent=True, type='joint')]
    meshes = cmds.ls(type='mesh') or []
    assemblies = cmds.ls(assemblies=True) or []
    
    # Check bounds
    bbox = cmds.exactWorldBoundingBox(top_joints[0]) if top_joints else []
    
    print("OPEN_RESULT:" + json.dumps({
        'scene': cmds.file(q=True, sceneName=True),
        'total_joints': len(joints),
        'top_joints': top_joints,
        'assemblies': assemblies,
        'meshes_count': len(meshes),
        'root_bbox': bbox
    }))

if __name__ == '__main__':
    open_sk_test()
