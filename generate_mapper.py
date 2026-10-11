import json

gt = json.load(open('c:/Users/zwj87/Documents/Pose2maya/mhr_127_ground_truth.json'))
parents = gt['parents']

names = [
    # 0..1
    ('root', 'root', 'Root', True),
    ('pelvis', 'pelvis', 'Hips', True),
    # 2..8
    ('l_thigh', 'thigh_l', 'LeftUpLeg', True),
    ('l_calf', 'calf_l', 'LeftLeg', True),
    ('l_foot', 'foot_l', 'LeftFoot', True),
    ('l_ball', 'ball_l', 'LeftToeBase', True),
    ('l_toe_end', 'toe_end_l', 'LeftToe_End', False),
    ('l_heel', 'heel_l', 'LeftHeel', False),
    ('l_heel_end', 'heel_end_l', 'LeftHeelEnd', False),
    # 9..12
    ('l_calf_twist_01', 'calf_twist_01_l', 'LeftLegTwist1', False),
    ('l_calf_twist_02', 'calf_twist_02_l', 'LeftLegTwist2', False),
    ('l_calf_twist_03', 'calf_twist_03_l', 'LeftLegTwist3', False),
    ('l_calf_twist_04', 'calf_twist_04_l', 'LeftLegTwist4', False),
    # 13..17
    ('l_thigh_twist_01', 'thigh_twist_01_l', 'LeftUpLegTwist1', False),
    ('l_thigh_twist_02', 'thigh_twist_02_l', 'LeftUpLegTwist2', False),
    ('l_thigh_twist_03', 'thigh_twist_03_l', 'LeftUpLegTwist3', False),
    ('l_thigh_twist_04', 'thigh_twist_04_l', 'LeftUpLegTwist4', False),
    ('l_thigh_twist_05', 'thigh_twist_05_l', 'LeftUpLegTwist5', False),
    # 18..24
    ('r_thigh', 'thigh_r', 'RightUpLeg', True),
    ('r_calf', 'calf_r', 'RightLeg', True),
    ('r_foot', 'foot_r', 'RightFoot', True),
    ('r_ball', 'ball_r', 'RightToeBase', True),
    ('r_toe_end', 'toe_end_r', 'RightToe_End', False),
    ('r_heel', 'heel_r', 'RightHeel', False),
    ('r_heel_end', 'heel_end_r', 'RightHeelEnd', False),
    # 25..28
    ('r_calf_twist_01', 'calf_twist_01_r', 'RightLegTwist1', False),
    ('r_calf_twist_02', 'calf_twist_02_r', 'RightLegTwist2', False),
    ('r_calf_twist_03', 'calf_twist_03_r', 'RightLegTwist3', False),
    ('r_calf_twist_04', 'calf_twist_04_r', 'RightLegTwist4', False),
    # 29..33
    ('r_thigh_twist_01', 'thigh_twist_01_r', 'RightUpLegTwist1', False),
    ('r_thigh_twist_02', 'thigh_twist_02_r', 'RightUpLegTwist2', False),
    ('r_thigh_twist_03', 'thigh_twist_03_r', 'RightUpLegTwist3', False),
    ('r_thigh_twist_04', 'thigh_twist_04_r', 'RightUpLegTwist4', False),
    ('r_thigh_twist_05', 'thigh_twist_05_r', 'RightUpLegTwist5', False),
    # 34..37
    ('spine_01', 'spine_01', 'Spine', True),
    ('spine_02', 'spine_02', 'Spine1', True),
    ('spine_03', 'spine_03', 'Spine2', True),
    ('spine_04_chest', 'spine_04', 'Spine3', True),
    # 38..42
    ('r_clavicle', 'clavicle_r', 'RightShoulder', True),
    ('r_upperarm', 'upperarm_r', 'RightArm', True),
    ('r_lowerarm', 'lowerarm_r', 'RightForeArm', True),
    ('r_hand', 'hand_r', 'RightHand', True),
    ('r_hand_palm', 'hand_palm_r', 'RightHandMiddle0', False),
    # 43..47
    ('r_thumb_01', 'thumb_01_r', 'RightHandThumb1', True),
    ('r_thumb_02', 'thumb_02_r', 'RightHandThumb2', True),
    ('r_thumb_03', 'thumb_03_r', 'RightHandThumb3', True),
    ('r_thumb_04', 'thumb_04_r', 'RightHandThumb4', False),
    ('r_thumb_end', 'thumb_end_r', 'RightHandThumb_End', False),
    # 48..51
    ('r_index_01', 'index_01_r', 'RightHandIndex1', True),
    ('r_index_02', 'index_02_r', 'RightHandIndex2', True),
    ('r_index_03', 'index_03_r', 'RightHandIndex3', True),
    ('r_index_end', 'index_end_r', 'RightHandIndex_End', False),
    # 52..55
    ('r_middle_01', 'middle_01_r', 'RightHandMiddle1', True),
    ('r_middle_02', 'middle_02_r', 'RightHandMiddle2', True),
    ('r_middle_03', 'middle_03_r', 'RightHandMiddle3', True),
    ('r_middle_end', 'middle_end_r', 'RightHandMiddle_End', False),
    # 56..59
    ('r_ring_01', 'ring_01_r', 'RightHandRing1', True),
    ('r_ring_02', 'ring_02_r', 'RightHandRing2', True),
    ('r_ring_03', 'ring_03_r', 'RightHandRing3', True),
    ('r_ring_end', 'ring_end_r', 'RightHandRing_End', False),
    # 60..64
    ('r_pinky_01', 'pinky_01_r', 'RightHandPinky1', True),
    ('r_pinky_02', 'pinky_02_r', 'RightHandPinky2', True),
    ('r_pinky_03', 'pinky_03_r', 'RightHandPinky3', True),
    ('r_pinky_04', 'pinky_04_r', 'RightHandPinky4', False),
    ('r_pinky_end', 'pinky_end_r', 'RightHandPinky_End', False),
    # 65..68
    ('r_lowerarm_twist_01', 'lowerarm_twist_01_r', 'RightForeArmTwist1', False),
    ('r_lowerarm_twist_02', 'lowerarm_twist_02_r', 'RightForeArmTwist2', False),
    ('r_lowerarm_twist_03', 'lowerarm_twist_03_r', 'RightForeArmTwist3', False),
    ('r_lowerarm_twist_04', 'lowerarm_twist_04_r', 'RightForeArmTwist4', False),
    # 69..73
    ('r_upperarm_twist_01', 'upperarm_twist_01_r', 'RightArmTwist1', False),
    ('r_upperarm_twist_02', 'upperarm_twist_02_r', 'RightArmTwist2', False),
    ('r_upperarm_twist_03', 'upperarm_twist_03_r', 'RightArmTwist3', False),
    ('r_upperarm_twist_04', 'upperarm_twist_04_r', 'RightArmTwist4', False),
    ('r_upperarm_twist_05', 'upperarm_twist_05_r', 'RightArmTwist5', False),
    # 74..78
    ('l_clavicle', 'clavicle_l', 'LeftShoulder', True),
    ('l_upperarm', 'upperarm_l', 'LeftArm', True),
    ('l_lowerarm', 'lowerarm_l', 'LeftForeArm', True),
    ('l_hand', 'hand_l', 'LeftHand', True),
    ('l_hand_palm', 'hand_palm_l', 'LeftHandMiddle0', False),
    # 79..83
    ('l_thumb_01', 'thumb_01_l', 'LeftHandThumb1', True),
    ('l_thumb_02', 'thumb_02_l', 'LeftHandThumb2', True),
    ('l_thumb_03', 'thumb_03_l', 'LeftHandThumb3', True),
    ('l_thumb_04', 'thumb_04_l', 'LeftHandThumb4', False),
    ('l_thumb_end', 'thumb_end_l', 'LeftHandThumb_End', False),
    # 84..87
    ('l_index_01', 'index_01_l', 'LeftHandIndex1', True),
    ('l_index_02', 'index_02_l', 'LeftHandIndex2', True),
    ('l_index_03', 'index_03_l', 'LeftHandIndex3', True),
    ('l_index_end', 'index_end_l', 'LeftHandIndex_End', False),
    # 88..91
    ('l_middle_01', 'middle_01_l', 'LeftHandMiddle1', True),
    ('l_middle_02', 'middle_02_l', 'LeftHandMiddle2', True),
    ('l_middle_03', 'middle_03_l', 'LeftHandMiddle3', True),
    ('l_middle_end', 'middle_end_l', 'LeftHandMiddle_End', False),
    # 92..95
    ('l_ring_01', 'ring_01_l', 'LeftHandRing1', True),
    ('l_ring_02', 'ring_02_l', 'LeftHandRing2', True),
    ('l_ring_03', 'ring_03_l', 'LeftHandRing3', True),
    ('l_ring_end', 'ring_end_l', 'LeftHandRing_End', False),
    # 96..100
    ('l_pinky_01', 'pinky_01_l', 'LeftHandPinky1', True),
    ('l_pinky_02', 'pinky_02_l', 'LeftHandPinky2', True),
    ('l_pinky_03', 'pinky_03_l', 'LeftHandPinky3', True),
    ('l_pinky_04', 'pinky_04_l', 'LeftHandPinky4', False),
    ('l_pinky_end', 'pinky_end_l', 'LeftHandPinky_End', False),
    # 101..104
    ('l_lowerarm_twist_01', 'lowerarm_twist_01_l', 'LeftForeArmTwist1', False),
    ('l_lowerarm_twist_02', 'lowerarm_twist_02_l', 'LeftForeArmTwist2', False),
    ('l_lowerarm_twist_03', 'lowerarm_twist_03_l', 'LeftForeArmTwist3', False),
    ('l_lowerarm_twist_04', 'lowerarm_twist_04_l', 'LeftForeArmTwist4', False),
    # 105..109
    ('l_upperarm_twist_01', 'upperarm_twist_01_l', 'LeftArmTwist1', False),
    ('l_upperarm_twist_02', 'upperarm_twist_02_l', 'LeftArmTwist2', False),
    ('l_upperarm_twist_03', 'upperarm_twist_03_l', 'LeftArmTwist3', False),
    ('l_upperarm_twist_04', 'upperarm_twist_04_l', 'LeftArmTwist4', False),
    ('l_upperarm_twist_05', 'upperarm_twist_05_l', 'LeftArmTwist5', False),
    # 110..113
    ('neck_01', 'neck_01', 'Neck', True),
    ('neck_02', 'neck_02', 'Neck1', False),
    ('neck_twist', 'neck_twist', 'NeckTwist', False),
    ('head', 'head', 'Head', True),
    # 114..121
    ('jaw', 'jaw', 'Jaw', False),
    ('chin', 'chin', 'Chin', False),
    ('tongue', 'tongue', 'Tongue', False),
    ('teeth_lower', 'teeth_lower', 'TeethLower', False),
    ('lip_lower_mid', 'lip_lower_mid', 'LipLowerMid', False),
    ('lip_lower_l', 'lip_lower_l', 'LipLowerL', False),
    ('lip_lower_r', 'lip_lower_r', 'LipLowerR', False),
    ('mouth_corner_l', 'mouth_corner_l', 'MouthCornerL', False),
    # 122..126
    ('eye_r', 'eye_r', 'RightEye', False),
    ('eyeball_r', 'eyeball_r', 'RightEyeBall', False),
    ('eye_l', 'eye_l', 'LeftEye', False),
    ('eyeball_l', 'eyeball_l', 'LeftEyeBall', False),
    ('head_top', 'head_top', 'Head_End', False)
]

assert len(names) == 127
assert len(parents) == 127

with open('c:/Users/zwj87/Documents/Pose2maya/mhr_dcc_mapper.py', 'w', encoding='utf-8') as f:
    f.write('"""\nAuthoritative 127-Joint MHR to DCC Naming & Hierarchy Mapper\n"""\n\n')
    f.write('MHR_127_JOINTS = [\n')
    for i in range(127):
        p = parents[i]
        anat, ue5, hik, is_core = names[i]
        f.write(f'    ({p}, "{anat}", "{ue5}", "{hik}", {is_core}),\n')
    f.write(']\n\n')
    f.write('assert len(MHR_127_JOINTS) == 127\n\n')
    f.write('def get_joint_info(idx):\n    if 0 <= idx < 127:\n        p, a, u, h, c = MHR_127_JOINTS[idx]\n        return {"index": idx, "parent_index": p, "anatomical_name": a, "ue5_name": u, "humanik_name": h, "is_core": c}\n    return None\n\n')
    f.write('def get_core_indices():\n    return [i for i, j in enumerate(MHR_127_JOINTS) if j[4]]\n')

print("generate_mapper.py completed successfully!")
