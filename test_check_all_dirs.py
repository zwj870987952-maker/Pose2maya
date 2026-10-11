import json
import maya.api.OpenMaya as om

with open(r"D:\sam-3d-body\outputs\benchmark_results\01_human_standard_skeleton.json", 'r', encoding='utf-8') as f:
    data = json.load(f)

world_pos = data["skeleton"]["world_positions"]

def get_v(idx):
    p = world_pos[idx]
    return om.MVector(p[0], -p[1], -p[2])

print("VERIFIED TARGET VECTORS (01_human_standard):")
print("Spine (Pelvis 1 -> Chest 37):", (get_v(37) - get_v(1)).normal())
print("Neck (Neck 110 -> Head 113):", (get_v(113) - get_v(110)).normal())

print("L Clavicle (74 -> 75):", (get_v(75) - get_v(74)).normal())
print("L UpArm (75 -> 76):", (get_v(76) - get_v(75)).normal())
print("L ForeArm (76 -> 77):", (get_v(77) - get_v(76)).normal())

print("R Clavicle (38 -> 39):", (get_v(39) - get_v(38)).normal())
print("R UpArm (39 -> 40):", (get_v(40) - get_v(39)).normal())
print("R ForeArm (40 -> 41):", (get_v(41) - get_v(40)).normal())

print("L Thigh (2 -> 3):", (get_v(3) - get_v(2)).normal())
print("L Shin (3 -> 4):", (get_v(4) - get_v(3)).normal())

print("R Thigh (18 -> 19):", (get_v(19) - get_v(18)).normal())
print("R Shin (19 -> 20):", (get_v(20) - get_v(19)).normal())
