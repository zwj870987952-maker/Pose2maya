import maya.cmds as cmds
import json

def check_venom():
    controls = [c for c in cmds.ls(type='transform') if 'Venom_Rig2:' in c and not cmds.listRelatives(c, shapes=True, type='mesh')]
    all_sets = cmds.ls(type='objectSet') or []
    venom_sets = [s for s in all_sets if 'Venom' in s or 'Control' in s]
    
    # Check if there are IK/FK controls
    ik_ctrls = [c for c in controls if any(k in c for k in ['IK', 'FK', 'Root', 'Spine', 'Arm', 'Leg'])]
    
    print("VENOM_INFO:" + json.dumps({
        'venom_sets': venom_sets,
        'ik_ctrls_sample': ik_ctrls[:30],
        'total_controls': len(controls)
    }))

if __name__ == '__main__':
    check_venom()
