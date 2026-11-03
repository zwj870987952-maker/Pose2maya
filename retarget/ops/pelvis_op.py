"""
retarget.ops.pelvis_op
======================
Op for Pelvis / Root motion retargeting.
Follows Section 7.2 of HANDOFF.md and AUD-15:
  - Respects part_mask["pelvis"] and chain_weights["pelvis"].
  - Scales displacement by reference hip height ratio.
  - Distinguishes three distinct root motion policies:
      1. in_place: horizontal (X, Z) motion zeroed, only vertical (Y) offset applied.
      2. pelvis_only: horizontal and vertical (X, Y, Z) displacement applied to pelvis_node.
      3. full: horizontal trajectory (X, Z) placed on root_node; vertical (Y) on pelvis_node.
"""

from typing import List
from pose_core.math3d import v_sub, v_scale, q_normalize, q_to_euler_deg
from .base_op import RetargetOp, RetargetContext


class PelvisOp(RetargetOp):
    def __init__(self, enabled: bool = True, weight: float = 1.0):
        super().__init__("PelvisOp", enabled, weight)

    def execute(self, ctx: RetargetContext) -> bool:
        if not self.enabled:
            return True

        retarget_prof = ctx.retarget_profile
        # Part mask check (AUD-15)
        if not retarget_prof.part_mask.get("pelvis", True):
            return True

        weight = retarget_prof.chain_weights.get("pelvis", self.weight)
        if weight <= 0.0:
            return True

        pose = ctx.source_pose
        skel = ctx.source_def
        rig = ctx.rig_profile

        pelvis_ctrl = rig.pelvis_node
        if not pelvis_ctrl:
            return True

        # Joint 1 is pelvis in MHR 127
        if len(pose.world_positions) <= 1 or len(skel.rest_world_positions) <= 1:
            ctx.result.warnings.append("Insufficient joint data for PelvisOp.")
            return False

        curr_pelvis_ws = pose.world_positions[1]
        rest_pelvis_ws = skel.rest_world_positions[1]

        # Relative displacement from rest pose in cm
        disp_source = v_sub(curr_pelvis_ws, rest_pelvis_ws)

        # Scale by reference hip height ratio
        ratio = ctx.calibrator.get_hip_height_ratio()
        disp_target = [
            disp_source[0] * ratio * weight,
            disp_source[1] * ratio * weight,
            disp_source[2] * ratio * weight
        ]

        # Extract pelvis rotation
        pelvis_rot_q = pose.local_rotations[1] if len(pose.local_rotations) > 1 else [0, 0, 0, 1]
        pelvis_rot_deg = q_to_euler_deg(pelvis_rot_q, rig.rotation_orders.get(pelvis_ctrl, 'xyz'))

        # Root motion policy handling (AUD-15)
        mode = retarget_prof.root_motion_mode
        if mode == "in_place":
            # Zero horizontal translation, preserve vertical height displacement
            pelvis_t = [0.0, disp_target[1], 0.0]
            ctx.result.target_transforms[pelvis_ctrl] = {
                "t": pelvis_t,
                "r": pelvis_rot_deg,
                "q": pelvis_rot_q
            }
        elif mode == "pelvis_only":
            # Apply full (X, Y, Z) displacement to pelvis controller
            pelvis_t = [disp_target[0], disp_target[1], disp_target[2]]
            ctx.result.target_transforms[pelvis_ctrl] = {
                "t": pelvis_t,
                "r": pelvis_rot_deg,
                "q": pelvis_rot_q
            }
        elif mode == "full":
            # Full root motion: Root node takes horizontal (X, Z), Pelvis takes vertical (Y)
            root_ctrl = rig.root_node
            if root_ctrl:
                root_t = [disp_target[0], 0.0, disp_target[2]]
                root_r_deg = q_to_euler_deg(pose.root_rotation, rig.rotation_orders.get(root_ctrl, 'xyz'))
                ctx.result.target_transforms[root_ctrl] = {
                    "t": root_t,
                    "r": root_r_deg,
                    "q": pose.root_rotation
                }

            pelvis_t = [0.0, disp_target[1], 0.0]
            ctx.result.target_transforms[pelvis_ctrl] = {
                "t": pelvis_t,
                "r": pelvis_rot_deg,
                "q": pelvis_rot_q
            }

        # Store in context state for downstream ops (IK goals, pole vectors)
        # In in_place mode, do not leak horizontal displacement to limbs (AUD-15)
        ctx.state["pelvis_displacement"] = pelvis_t if mode == "in_place" else disp_target
        ctx.state["pelvis_rotation"] = pelvis_rot_q

        return True
