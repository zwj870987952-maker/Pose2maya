import maya.cmds as cmds
import maya.api.OpenMaya as om

for side in ["L", "R"]:
    sh = f"Shoulder_{side}"
    el = f"Elbow_{side}"
    wr = f"Wrist_{side}"
    hp = f"Hip_{side}"
    kn = f"Knee_{side}"
    ak = f"Ankle_{side}"
    print(f"=== SIDE {side} ===")
    print(f"  {sh} ws pos: {cmds.xform(sh, q=True, ws=True, t=True)}")
    print(f"  {el} ws pos: {cmds.xform(el, q=True, ws=True, t=True)}")
    print(f"  {wr} ws pos: {cmds.xform(wr, q=True, ws=True, t=True)}")
    print(f"  {hp} ws pos: {cmds.xform(hp, q=True, ws=True, t=True)}")
    print(f"  {kn} ws pos: {cmds.xform(kn, q=True, ws=True, t=True)}")
    print(f"  {ak} ws pos: {cmds.xform(ak, q=True, ws=True, t=True)}")
