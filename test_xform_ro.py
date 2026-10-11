import maya.cmds as cmds
import maya.api.OpenMaya as om
import json

def test_xform_world_ro():
    j = "Shoulder_L"
    orig_ws_ro = cmds.xform(j, q=True, ws=True, ro=True)
    orig_r = cmds.getAttr(f"{j}.r")[0]
    
    # Try setting world rotation + 10 deg
    test_ro = [orig_ws_ro[0] + 10.0, orig_ws_ro[1], orig_ws_ro[2]]
    cmds.xform(j, ws=True, ro=test_ro)
    
    new_ws_ro = cmds.xform(j, q=True, ws=True, ro=True)
    new_r = cmds.getAttr(f"{j}.r")[0]
    
    # Reset
    cmds.setAttr(f"{j}.r", *orig_r)
    
    print("XFORM_TEST:" + json.dumps({
        'orig_ws_ro': orig_ws_ro,
        'test_ws_ro': test_ro,
        'new_ws_ro': new_ws_ro,
        'diff': [a - b for a, b in zip(new_ws_ro, test_ro)]
    }))

if __name__ == '__main__':
    test_xform_world_ro()
