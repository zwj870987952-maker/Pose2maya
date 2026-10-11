import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

cmds.file(r"C:\Users\zwj87\Desktop\sk_test.ma", open=True, force=True)

# Test MQuaternion rotation order and OpenMaya math
v1 = om.MVector(1, 0, 0)
v2 = om.MVector(0, 1, 0)
q_z90 = om.MQuaternion(v1, v2) # 90 deg around Z
v_test = v1.rotateBy(q_z90)
print(f"v1 (1,0,0) rotated by q(v1, v2) -> ({v_test.x:.2f}, {v_test.y:.2f}, {v_test.z:.2f})")

# Now let's test rotating a joint properly in Maya!
# Let's see: If we want a child joint to point towards target_dir in World Space:
# What is the exact matrix math?
# Let W_parent be parent joint's world matrix.
# In Maya:
# If parent joint rotates by delta_R in world space around parent joint position:
# For any point P in child space: P_new_ws = parent_pos + delta_R * (P_old_ws - parent_pos)
# We want: (child_pos_new - parent_pos).normal() == target_dir!
# That means delta_R must be om.MQuaternion(curr_dir, target_dir)!
# Now, what should the parent joint's local rotation attribute (cmds.setAttr joint.r) be?
# Let's derive it directly from matrices!

# Parent joint P, grandparent GP:
# P.worldMatrix = GP.worldMatrix * P.matrix
# In Maya joint:
# P.matrix = Translate * JointOrient * Rotate * Scale
# Wait! Let's check Maya's joint transform formula:
# cmds.getAttr(joint + ".matrix")
# Let's print how jointOrient and rotate combine in Maya!

joint = "Shoulder_L"
parent = cmds.listRelatives(joint, p=True)[0]
print(f"Joint: {joint}, Parent in Maya: {parent}")

# Let's test setting world matrix directly or computing local rotation directly via MTransformationMatrix!
