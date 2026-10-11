import maya.cmds as cmds
import json

def inspect_sk_test_joints():
    check_joints = [
        "Root_M", "Spine1_M", "Spine2_M", "Chest_M", "Neck_M", "Head_M",
        "Clavicle01_L", "Shoulder_L", "Elbow_L", "Wrist_L",
        "Clavicle01_R", "Shoulder_R", "Elbow_R", "Wrist_R",
        "Hip_L", "Knee_L", "Ankle_L", "Toes_L",
        "Hip_R", "Knee_R", "Ankle_R", "Toes_R"
    ]
    
    positions = {}
    rotations = {}
    for j in check_joints:
        if cmds.objExists(j):
            positions[j] = cmds.xform(j, q=True, ws=True, t=True)
            rotations[j] = cmds.xform(j, q=True, ws=True, ro=True)
    
    # Calculate height
    h = positions["Head_M"][1] - positions["Ankle_L"][1] if "Head_M" in positions and "Ankle_L" in positions else 0
    
    print("SK_TEST_JOINTS:" + json.dumps({
        'positions': positions,
        'rotations': rotations,
        'character_height': h
    }, indent=2))

if __name__ == '__main__':
    inspect_sk_test_joints()
