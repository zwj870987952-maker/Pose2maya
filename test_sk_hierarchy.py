import maya.cmds as cmds

cmds.file(r"C:\Users\zwj87\Desktop\sk_test.ma", open=True, force=True)

root_parent = cmds.listRelatives("Root_M", p=True)
print("Root_M parent:", root_parent)

# Also check the hierarchy of the spine and limbs in sk_test.ma:
for j in ["Root_M", "Spine1_M", "Spine2_M", "Chest_M", "Neck_M", "Head_M",
          "Scapula_L", "Shoulder_L", "Elbow_L", "Wrist_L",
          "Hip_L", "Knee_L", "Ankle_L"]:
    p = cmds.listRelatives(j, p=True)
    c = cmds.listRelatives(j, c=True, type='joint')
    print(f"{j:12s} | parent: {p[0] if p else 'None':12s} | children: {c}")
