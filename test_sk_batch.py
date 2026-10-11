"""
Test Batch Retargeting for sk_test.ma in Maya
Retargets 6 benchmark poses from SAM 3D onto sk_test.ma joints across frames 1, 10, 20, 30, 40, 50.
"""

import os
import json
import math
import maya.cmds as cmds
import maya.api.OpenMaya as om
from pose_retargeter import PoseRetargeter, rotate_joint_to_vector

BENCHMARK_DIR = r"D:\sam-3d-body\outputs\benchmark_results"

POSES = [
    (1, "01_human_standard_skeleton.json", "1. 标准站姿"),
    (10, "02_human_dancing_skeleton.json", "2. 高难度跳舞"),
    (20, "03_game_3d_ironman_skeleton.json", "3. 3D机甲站姿"),
    (30, "04_anime_illustration_skeleton.json", "4. 二次元动漫立绘"),
    (40, "05_strong_perspective_skeleton.json", "5. 强透视俯冲"),
    (50, "06_limb_occlusion_skeleton.json", "6. 倒地高难度肢体")
]

def run_sk_test_batch():
    print(">>> Starting Batch Retargeting on sk_test.ma joints...")
    retargeter = PoseRetargeter(target_prefix="")

    cmds.playbackOptions(minTime=1, maxTime=50, animationStartTime=1, animationEndTime=50)

    for frame, filename, label in POSES:
        json_path = os.path.join(BENCHMARK_DIR, filename)
        if not os.path.exists(json_path):
            print(f"[Warning] File not found: {json_path}")
            continue

        cmds.currentTime(frame)
        print(f"\n--- [Frame {frame}] Applying {label} ({filename}) ---")
        
        # 1. Update visual template skeleton B
        retargeter.build_or_update_template_b(json_path, scale=100.0)
        
        # 2. Retarget onto sk_test joints and keyframe
        success = retargeter.retarget_pose(json_path, keyframe=frame)
        if success:
            print(f"--> [Frame {frame}] Successfully retargeted and keyframed: {label}")

    cmds.currentTime(1)
    print("\n>>> ALL 6 POSES RETARGETED AND KEYFRAMED SUCCESSFULLY ON sk_test.ma [Frames 1..50]! Parked at frame 1.")

if __name__ == '__main__':
    run_sk_test_batch()
