"""
retarget.ops.ground_contact_op
==============================
Adjusts character pelvis and foot goals to respect ground plane contact.
Follows Section 7.4 of HANDOFF.md and AUD-16 repair requirements:
  - Supports per-leg selection (left_leg, right_leg, or both).
  - Handles both penetration (feet below floor) and floating (feet suspended above floor).
  - Synchronizes diagnostic IK goals with final written target transforms.
  - Detects reachability conflicts and adjusts pelvis height when necessary.
"""

import math
from typing import List, Dict
from pose_core.math3d import v_dist
from .base_op import RetargetOp, RetargetContext


class GroundContactOp(RetargetOp):
    def __init__(self, enabled: bool = True, weight: float = 1.0):
        super().__init__("GroundContactOp", enabled, weight)

    def execute(self, ctx: RetargetContext) -> bool:
        if not self.enabled or not ctx.retarget_profile.ground_contact:
            return True

        retarget_prof = ctx.retarget_profile
        floor_h = float(retarget_prof.ground_height)
        contact_legs = getattr(retarget_prof, "contact_legs", {"left_leg": True, "right_leg": True})
        rig = ctx.rig_profile

        # Process each leg selected for ground contact
        for side in ["left_leg", "right_leg"]:
            if not contact_legs.get(side, False):
                continue
            if not retarget_prof.part_mask.get(side, True):
                continue

            chain = rig.chains.get(side)
            if not chain or not chain.ik_control:
                continue

            ctrl = chain.ik_control
            if ctrl not in ctx.result.target_transforms or "t" not in ctx.result.target_transforms[ctrl]:
                continue

            cur_t = ctx.result.target_transforms[ctrl]["t"]
            cur_y = cur_t[1]

            # Sole offset from calibrator if available
            offset_info = ctx.calibrator.get_controller_offset(ctrl)
            sole_offset = offset_info.get("pos_offset", [0.0, 0.0, 0.0])[1] if offset_info else 0.0

            target_y = floor_h + sole_offset
            delta_y = target_y - cur_y

            # Adjust foot height (handles both penetration delta_y > 0 and floating delta_y < 0)
            new_y = cur_y + delta_y * self.weight
            ctx.result.target_transforms[ctrl]["t"][1] = new_y

            # Synchronize diagnostic ik_goals (AUD-16)
            if side in ctx.result.ik_goals and "target_pos" in ctx.result.ik_goals[side]:
                ctx.result.ik_goals[side]["target_pos"][1] = new_y

            # Check reachability against limb length geometrically (AUD-16)
            p_hip = ctx.state.get(f"{side}_p_root")
            l_max = ctx.state.get(f"{side}_len", 80.0)
            if p_hip is not None:
                new_foot_pos = [cur_t[0], new_y, cur_t[2]]
                reach_dist = v_dist(p_hip, new_foot_pos)
                if reach_dist > l_max:
                    dx = new_foot_pos[0] - p_hip[0]
                    dz = new_foot_pos[2] - p_hip[2]
                    d_horiz = math.sqrt(dx * dx + dz * dz)
                    if d_horiz < l_max:
                        # Max vertical separation allowable: h_max = sqrt(l_max^2 - d_horiz^2)
                        h_max = math.sqrt(l_max * l_max - d_horiz * d_horiz)
                        needed_hip_y = new_y + h_max
                        if p_hip[1] > needed_hip_y:
                            drop = p_hip[1] - needed_hip_y
                            pelvis_ctrl = rig.pelvis_node
                            if pelvis_ctrl and pelvis_ctrl in ctx.result.target_transforms:
                                ctx.result.target_transforms[pelvis_ctrl]["t"][1] -= drop * self.weight
                            p_hip[1] -= drop * self.weight
                            final_reach = v_dist(p_hip, new_foot_pos)
                            ctx.result.residuals[f"{side}_ground_reach"] = max(0.0, final_reach - l_max)
                    else:
                        ctx.result.residuals[f"{side}_ground_reach"] = d_horiz - l_max
                        ctx.result.warnings.append(
                            f"Ground contact: {side} is unreachable (horizontal offset {d_horiz:.2f}cm > max length {l_max:.2f}cm)."
                        )
                else:
                    ctx.result.residuals[f"{side}_ground_reach"] = 0.0

                # Re-evaluate pole vector with final grounded positions (AUD-16)
                ctx.state[f"{side}_p_root"] = list(p_hip)
                ctx.state[f"{side}_p_end"] = list(new_foot_pos)
                from retarget.ops.pole_vector_op import PoleVectorOp
                PoleVectorOp(chain_id=side).execute(ctx)

        return True
