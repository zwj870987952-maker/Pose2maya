import maya.cmds as cmds
import json

def check_all_sets():
    sets = cmds.ls(type='objectSet') or []
    ctrl_sets = [s for s in sets if 'ControlSet' in s]
    result = {}
    for cs in ctrl_sets:
        members = cmds.sets(cs, q=True) or []
        result[cs] = {
            'count': len(members),
            'sample': members[:15]
        }
    print("CTRL_SETS:" + json.dumps(result))

if __name__ == '__main__':
    check_all_sets()
