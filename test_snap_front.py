import maya.cmds as cmds

# Set persp camera to look directly from front-3/4
cmds.setAttr("persp.translateX", 0)
cmds.setAttr("persp.translateY", 550)
cmds.setAttr("persp.translateZ", 1500)
cmds.setAttr("persp.rotateX", 0)
cmds.setAttr("persp.rotateY", 0)
cmds.setAttr("persp.rotateZ", 0)

cmds.select("Geo", r=True) if cmds.objExists("Geo") else None
cmds.viewFit("persp", animate=False)
cmds.select(cl=True)

out_front = r"C:\Users\zwj87\Documents\Pose2maya\test_dancing_front.jpg"
cmds.playblast(
    frame=[1],
    format='image',
    compression='jpg',
    completeFilename=out_front,
    showOrnaments=False,
    viewer=False,
    widthHeight=[512, 512],
    percent=100,
    forceOverwrite=True
)
print("Front snapshot saved:", out_front)
