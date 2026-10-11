import maya.cmds as cmds

for f in [1, 10, 20, 30, 40, 50]:
    cmds.currentTime(f)
    r_sh = cmds.getAttr("Shoulder_L.r")[0]
    r_hp = cmds.getAttr("Hip_L.r")[0]
    print(f"Frame {f:2d} | Shoulder_L: [{r_sh[0]:.1f}, {r_sh[1]:.1f}, {r_sh[2]:.1f}] | Hip_L: [{r_hp[0]:.1f}, {r_hp[1]:.1f}, {r_hp[2]:.1f}]")
