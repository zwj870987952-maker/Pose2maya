import os
import maya.cmds as cmds
from dcc_skeleton_builder import DCCSkeletonBuilder

# Keep current scene with sk_test.ma or clean reload
# Let's build the DCC Skeleton at X = 250 so it stands right beside sk_test character!
builder = DCCSkeletonBuilder(naming_style="ue5", mode="core", prefix="UE5_")
joints = builder.build_skeleton(
    r"D:\sam-3d-body\outputs\benchmark_results\01_human_standard_skeleton.json",
    scale=100.0,
    world_offset=[250.0, 0.0, 0.0]
)

print(f"Generated {len(joints)} joints:")
for j in joints[:10]:
    p = cmds.xform(j, q=True, ws=True, t=True)
    print(f"  {j:20s} | parent: {cmds.listRelatives(j, p=True)} | pos: [{p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f}]")

# Let's frame persp to view both characters side by side
cmds.select(cl=True)
cmds.select("Geo") if cmds.objExists("Geo") else None
cmds.select("UE5_root", add=True) if cmds.objExists("UE5_root") else None
cmds.viewFit("persp", animate=False)
cmds.select(cl=True)

out_img = r"C:\Users\zwj87\Documents\Pose2maya\test_dcc_skeleton_side_by_side.jpg"
cmds.playblast(
    frame=[1],
    format='image',
    compression='jpg',
    completeFilename=out_img,
    showOrnaments=False,
    viewer=False,
    widthHeight=[640, 512],
    percent=100,
    forceOverwrite=True
)
print("Saved side-by-side snapshot:", out_img)
