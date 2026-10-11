import json
import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

with open(r"D:\sam-3d-body\outputs\benchmark_results\01_human_standard_skeleton.json", 'r', encoding='utf-8') as f:
    data = json.load(f)

world_positions = data["skeleton"]["world_positions"]
MHR_INDICES = {
    "root": 0, "pelvis": 1,
    "spine1": 34, "spine2": 35, "spine3": 36, "chest": 37,
    "neck": 110, "head": 113,
    "r_clavicle": 38, "r_shoulder": 39, "r_elbow": 40, "r_wrist": 41,
    "l_clavicle": 74, "l_shoulder": 75, "l_elbow": 76, "l_wrist": 77,
    "r_hip": 2, "r_knee": 3, "r_ankle": 4,
    "l_hip": 18, "l_knee": 19, "l_ankle": 20
}

pos = {}
for name, idx in MHR_INDICES.items():
    p = world_positions[idx]
    # Note: raw p has pelvis ~ -0.92, head ~ -1.51
    pos[name] = om.MVector(p[0], -p[1], -p[2])

print("Target MHR directions:")
v_spine = (pos["chest"] - pos["pelvis"]).normal()
print(f"Spine dir: [{v_spine.x:.3f}, {v_spine.y:.3f}, {v_spine.z:.3f}]")
v_neck = (pos["head"] - pos["neck"]).normal()
print(f"Neck dir: [{v_neck.x:.3f}, {v_neck.y:.3f}, {v_neck.z:.3f}]")

v_l_arm = (pos["l_elbow"] - pos["l_shoulder"]).normal()
print(f"L UpArm dir: [{v_l_arm.x:.3f}, {v_l_arm.y:.3f}, {v_l_arm.z:.3f}]")
v_l_forearm = (pos["l_wrist"] - pos["l_elbow"]).normal()
print(f"L ForeArm dir: [{v_l_forearm.x:.3f}, {v_l_forearm.y:.3f}, {v_l_forearm.z:.3f}]")

v_l_thigh = (pos["l_knee"] - pos["l_hip"]).normal()
print(f"L Thigh dir: [{v_l_thigh.x:.3f}, {v_l_thigh.y:.3f}, {v_l_thigh.z:.3f}]")
v_l_shin = (pos["l_ankle"] - pos["l_knee"]).normal()
print(f"L Shin dir: [{v_l_shin.x:.3f}, {v_l_shin.y:.3f}, {v_l_shin.z:.3f}]")

print("\nCurrent Maya bone vectors in Rest Pose:")
for p_name, c_name in [("Spine1_M", "Chest_M"), ("Neck_M", "Head_M"), 
                       ("Shoulder_L", "Elbow_L"), ("Elbow_L", "Wrist_L"),
                       ("Hip_L", "Knee_L"), ("Knee_L", "Ankle_L")]:
    p = om.MVector(*cmds.xform(p_name, q=True, ws=True, t=True))
    c = om.MVector(*cmds.xform(c_name, q=True, ws=True, t=True))
    v = (c - p).normal()
    print(f"{p_name}->{c_name}: [{v.x:.3f}, {v.y:.3f}, {v.z:.3f}]")
