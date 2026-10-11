import maya.cmds as cmds
import json

def inspect_venom_ctrls():
    members = cmds.sets('Venom_Rig2:ControlSet', q=True) or []
    # Find root and main
    mains = [m for m in members if 'Main' in m or 'Root' in m or 'IK' in m or 'Hip' in m]
    sample = {m: cmds.xform(m, q=True, ws=True, t=True) for m in mains[:15]}
    print("VENOM_MAINS:" + json.dumps(sample))

if __name__ == '__main__':
    inspect_venom_ctrls()
