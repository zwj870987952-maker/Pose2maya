import maya.cmds as cmds
from dcc_skeleton_builder import DCCSkeletonBuilder

# Build full 127 joints DCC skeleton
builder = DCCSkeletonBuilder(naming_style="ue5", mode="full", prefix="UE5_Full_")
joints = builder.build_skeleton(
    r"D:\sam-3d-body\outputs\benchmark_results\01_human_standard_skeleton.json",
    scale=100.0,
    world_offset=[150.0, 0.0, 0.0]
)

print(f"Generated {len(joints)} joints in FULL mode!")
print("Sample fingers on Left Hand:")
for j in joints:
    if "thumb" in j or "index" in j or "pinky" in j:
        print(f"  {j} -> parent: {cmds.listRelatives(j, p=True)}")
