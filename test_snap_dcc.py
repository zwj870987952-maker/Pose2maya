import maya.cmds as cmds

cmds.select("UE5_root", r=True)
cmds.viewFit("persp", animate=False)
cmds.select(cl=True)

out_dcc = r"C:\Users\zwj87\Documents\Pose2maya\test_dcc_skeleton_closeup.jpg"
cmds.playblast(
    frame=[1],
    format='image',
    compression='jpg',
    completeFilename=out_dcc,
    showOrnaments=True, # Show joints and names
    viewer=False,
    widthHeight=[512, 512],
    percent=100,
    forceOverwrite=True
)
print("Saved closeup snapshot:", out_dcc)
