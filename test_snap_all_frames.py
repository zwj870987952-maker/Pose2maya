import os
import maya.cmds as cmds

cmds.setAttr("persp.translateX", 0)
cmds.setAttr("persp.translateY", 550)
cmds.setAttr("persp.translateZ", 1500)
cmds.setAttr("persp.rotateX", 0)
cmds.setAttr("persp.rotateY", 0)
cmds.setAttr("persp.rotateZ", 0)

cmds.select("Geo", r=True) if cmds.objExists("Geo") else None
cmds.viewFit("persp", animate=False)
cmds.select(cl=True)

out_dir = r"C:\Users\zwj87\Documents\Pose2maya\snapshots"
os.makedirs(out_dir, exist_ok=True)

frames = [1, 10, 20, 30, 40, 50]
for f in frames:
    cmds.currentTime(f, update=True)
    cmds.refresh(cv=True, f=True)
    out_img = os.path.join(out_dir, f"frame_{f:02d}.jpg")
    cmds.playblast(
        frame=[f],
        format='image',
        compression='jpg',
        completeFilename=out_img,
        showOrnaments=False,
        viewer=False,
        widthHeight=[512, 512],
        percent=100,
        forceOverwrite=True
    )
    print(f"Captured frame {f} -> {out_img}")
