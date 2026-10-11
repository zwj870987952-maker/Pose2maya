import maya.cmds as cmds
import json

def check_venom_controls():
    controls = [
        'Venom_Rig2:RootX_M', 'Venom_Rig2:FKSpine1_M', 'Venom_Rig2:FKChest_M',
        'Venom_Rig2:FKNeck_M', 'Venom_Rig2:FKHead_M',
        'Venom_Rig2:IKArm_L', 'Venom_Rig2:IKArm_R', 'Venom_Rig2:PoleArm_L', 'Venom_Rig2:PoleArm_R',
        'Venom_Rig2:IKLeg_L', 'Venom_Rig2:IKLeg_R', 'Venom_Rig2:PoleLeg_L', 'Venom_Rig2:PoleLeg_R',
        'Venom_Rig2:FKIKArm_L', 'Venom_Rig2:FKIKArm_R', 'Venom_Rig2:FKIKLeg_L', 'Venom_Rig2:FKIKLeg_R',
        'Venom_Rig2:FKShoulder_L', 'Venom_Rig2:FKElbow_L', 'Venom_Rig2:FKWrist_L',
        'Venom_Rig2:FKHip_L', 'Venom_Rig2:FKKnee_L', 'Venom_Rig2:FKAnkle_L'
    ]
    exists = {c: cmds.objExists(c) for c in controls}
    print("CONTROL_EXISTS:" + json.dumps(exists))

if __name__ == '__main__':
    check_venom_controls()
