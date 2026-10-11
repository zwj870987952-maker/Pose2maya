import json
import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

cmds.file(r"C:\Users\zwj87\Desktop\sk_test.ma", open=True, force=True)

with open(r"D:\sam-3d-body\outputs\benchmark_results\01_human_standard_skeleton.json", 'r', encoding='utf-8') as f:
    data = json.load(f)

world_pos = data["skeleton"]["world_positions"]
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
for k, idx in MHR_INDICES.items():
    p = world_pos[idx]
    pos[k] = om.MVector(p[0], -p[1], -p[2])

print("Pelvis positions:")
print("  R Hip:", pos["r_hip"])
print("  L Hip:", pos["l_hip"])
print("  Hip vector (R->L):", (pos["l_hip"] - pos["r_hip"]).normal())

p_r_hip_maya = om.MVector(*cmds.xform("Hip_R", q=True, ws=True, t=True))
p_l_hip_maya = om.MVector(*cmds.xform("Hip_L", q=True, ws=True, t=True))
print("Maya Hip vector (R->L):", (p_l_hip_maya - p_r_hip_maya).normal())
