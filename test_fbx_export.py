from dcc_skeleton_builder import DCCSkeletonBuilder
import os

b = DCCSkeletonBuilder(naming_style="ue5", mode="core", prefix="UE5_")
out_fbx = r"C:\Users\zwj87\Documents\Pose2maya\test_export.fbx"
b.export_fbx(out_fbx, 1, 10)
if os.path.exists(out_fbx):
    print(f"FBX Export Verified! Size: {os.path.getsize(out_fbx)} bytes")
