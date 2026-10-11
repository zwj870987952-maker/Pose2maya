import maya.cmds as cmds
import json

def get_venom_dimensions():
    joints = {
        'root': 'Venom_Rig2:RootX_M',
        'hip_l': 'Venom_Rig2:Hip_L',
        'knee_l': 'Venom_Rig2:Knee_L',
        'ankle_l': 'Venom_Rig2:Ankle_L',
        'shoulder_l': 'Venom_Rig2:Shoulder_L',
        'elbow_l': 'Venom_Rig2:Elbow_L',
        'wrist_l': 'Venom_Rig2:Wrist_L',
        'head': 'Venom_Rig2:Head_M'
    }
    positions = {}
    for k, j in joints.items():
        if cmds.objExists(j):
            positions[k] = cmds.xform(j, q=True, ws=True, t=True)
    
    # Calculate leg length and arm length
    res = {'positions': positions}
    if 'hip_l' in positions and 'knee_l' in positions and 'ankle_l' in positions:
        import math
        def dist(p1, p2):
            return math.sqrt(sum((a - b)**2 for a, b in zip(p1, p2)))
        res['leg_length'] = dist(positions['hip_l'], positions['knee_l']) + dist(positions['knee_l'], positions['ankle_l'])
        res['arm_length'] = dist(positions['shoulder_l'], positions['elbow_l']) + dist(positions['elbow_l'], positions['wrist_l'])
        res['total_height'] = positions['head'][1] - positions['ankle_l'][1] if 'head' in positions and 'ankle_l' in positions else 0

    print("VENOM_DIMENSIONS:" + json.dumps(res))

if __name__ == '__main__':
    get_venom_dimensions()
