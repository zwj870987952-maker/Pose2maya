import maya.cmds as cmds
import os

def take_snapshots():
    out_dir = r"C:\Users\zwj87\Documents\Pose2maya"
    os.makedirs(out_dir, exist_ok=True)
    
    # Focus persp camera on character
    cmds.select("Geo", r=True) if cmds.objExists("Geo") else None
    cmds.viewFit("persp", animate=False)
    cmds.select(cl=True)
    
    for f in [1, 10]:
        cmds.currentTime(f)
        img_path = os.path.join(out_dir, f"snapshot_f{f}.jpg")
        cmds.playblast(
            frame=[f],
            format='image',
            compression='jpg',
            completeFilename=img_path,
            showOrnaments=False,
            viewer=False,
            widthHeight=[512, 512],
            percent=100,
            forceOverwrite=True
        )
        print(f"SNAPSHOT_SAVED: {img_path}")

if __name__ == '__main__':
    take_snapshots()
