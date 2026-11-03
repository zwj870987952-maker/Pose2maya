"""
retarget.ops.ik_goals_op
========================
Computes IK world targets and reachability diagnostics.
Follows Section 7.4 of HANDOFF.md and AUD-05 / AUD-07 repair requirements:
  - Uses actual target limb geometry (independent per-side lengths L1, L2).
  - Uses calibrated target chain anchor and pelvis displacement.
  - Clamps to target reachable boundaries [|L1 - L2|, L1 + L2] without unbounded stretching.
  - Diagnoses reachability residuals accurately against target geometry.
  - Computes full end-effector world rotation via forward kinematics and calibrated controller offsets.
"""

from typing import List
from pose_core.math3d import (
    q_identity, q_to_euler_deg, q_slerp, q_rotate_vector, q_multiply, q_inverse,
    v_sub, v_length, v_dist, v_add, v_scale, v_norm, v_lerp, fk_reconstruct
)
from .base_op import RetargetOp, RetargetContext


class IKGoalsOp(RetargetOp):
    def __init__(self, chain_id: str, enabled: bool = True, weight: float = 1.0):
        super().__init__(f"IKGoalsOp_{chain_id}", enabled, weight)
        self.chain_id = chain_id

    def execute(self, ctx: RetargetContext) -> bool:
        if not self.enabled or self.weight <= 0.0:
            return True

        retarget_prof = ctx.retarget_profile
        if not retarget_prof.part_mask.get(self.chain_id, True):
            return True

        weight = retarget_prof.chain_weights.get(self.chain_id, self.weight)
        if weight <= 0.0:
            return True

        mode = retarget_prof.chain_modes.get(self.chain_id, "ik")
        rig = ctx.rig_profile
        chain = rig.chains.get(self.chain_id)
        if not chain or not chain.ik_control:
            return True

        if mode != "ik":
            return True

        # Switch attribute
        if chain.fk_ik_switch_attr:
            ctx.result.mode_switches[chain.fk_ik_switch_attr] = chain.ik_value

        source_indices = ctx.source_def.chains.get(self.chain_id, [])
        if len(source_indices) < 3:
            return True

        # Drivable joints: root, mid, end
        # e.g. leg: [2, 3, 4] -> hip=2, knee=3, ankle=4
        # e.g. arm: [74, 75, 76, 77] -> shoulder=75, elbow=76, wrist=77
        root_idx = source_indices[-3]
        mid_idx = source_indices[-2]
        end_idx = source_indices[-1]

        world_pos = ctx.source_pose.world_positions
        if end_idx >= len(world_pos) or root_idx >= len(world_pos) or mid_idx >= len(world_pos):
            return True

        p_root_src = world_pos[root_idx]
        p_mid_src = world_pos[mid_idx]
        p_end_src = world_pos[end_idx]

        # 1. Source limb length & extension ratio
        l1_src = v_dist(p_root_src, p_mid_src)
        l2_src = v_dist(p_mid_src, p_end_src)
        l_src_total = l1_src + l2_src
        d_src_actual = v_dist(p_root_src, p_end_src)
        extension_ratio = d_src_actual / max(l_src_total, 0.001)

        # 2. Target Character Geometry (AUD-05)
        # Query target character's actual limb lengths (L1, L2)
        l1_tgt, l2_tgt = ctx.calibrator.get_target_limb_lengths(self.chain_id, fallback_len=l_src_total)
        l_tgt_max = l1_tgt + l2_tgt
        l_tgt_min = abs(l1_tgt - l2_tgt)

        # Pre-compute FK global rotations if not already cached (AUD-05 / AUD-07)
        if "fk_global_rotations" not in ctx.state:
            _, g_rots = fk_reconstruct(
                ctx.source_def.parent_indices,
                ctx.source_def.rest_translations,
                ctx.source_pose.local_rotations,
                ctx.source_pose.root_translation,
                ctx.source_pose.root_rotation
            )
            ctx.state["fk_global_rotations"] = g_rots

        # Target chain anchor in world space (accounting for pelvis displacement and torso/pelvis rotation) (AUD-05)
        p_anchor_rest = ctx.calibrator.get_target_chain_anchor(self.chain_id, fallback_pos=p_root_src)
        pelvis_disp = ctx.state.get("pelvis_displacement", [0.0, 0.0, 0.0])

        is_leg = "leg" in self.chain_id
        if is_leg:
            q_anchor_rot = ctx.source_pose.root_rotation
        else:
            if "rest_fk_global_rotations" not in ctx.state:
                _, rest_g_rots = fk_reconstruct(
                    ctx.source_def.parent_indices,
                    ctx.source_def.rest_translations,
                    ctx.source_def.rest_rotations
                )
                ctx.state["rest_fk_global_rotations"] = rest_g_rots
            rest_g_rots = ctx.state["rest_fk_global_rotations"]
            g_rots = ctx.state["fk_global_rotations"]
            if len(g_rots) > 37 and len(rest_g_rots) > 37:
                q_anchor_rot = q_multiply(g_rots[37], q_inverse(rest_g_rots[37]))
            else:
                q_anchor_rot = ctx.source_pose.root_rotation

        p_pelvis_rest = [0.0, rig.target_hip_height, 0.0]
        anchor_offset = v_sub(p_anchor_rest, p_pelvis_rest)
        rotated_offset = q_rotate_vector(q_anchor_rot, anchor_offset)
        p_anchor = v_add(p_pelvis_rest, v_add(pelvis_disp, rotated_offset))

        # 3. Compute target end position
        v_dir = v_norm(v_sub(p_end_src, p_root_src))
        d_desired = extension_ratio * l_tgt_max

        # Reachability residual calculation (AUD-05)
        if d_desired > l_tgt_max:
            residual = d_desired - l_tgt_max
            d_actual = l_tgt_max * 0.999
        elif d_desired < l_tgt_min:
            residual = l_tgt_min - d_desired
            d_actual = l_tgt_min * 1.001
        else:
            residual = 0.0
            d_actual = d_desired

        ctx.result.residuals[f"{self.chain_id}_reach"] = residual

        target_end_ws = v_add(p_anchor, v_scale(v_dir, d_actual))

        # 4. End Effector Full World Orientation (AUD-07)
        global_rots = ctx.state["fk_global_rotations"]
        q_end_world = global_rots[end_idx] if end_idx < len(global_rots) else q_identity()

        # 5. Controller offset calibration
        ctrl_pos, ctrl_rot = ctx.calibrator.get_ik_control_world_target(
            control_name=chain.ik_control,
            target_joint_ws_pos=target_end_ws,
            target_joint_ws_rot=q_end_world
        )

        # Weight interpolation with bind reference state (AUD-15)
        offset_info = ctx.calibrator.controller_offsets.get(chain.ik_control)
        if weight < 1.0 and offset_info:
            bind_pos = offset_info.get("bind_pos")
            bind_rot = offset_info.get("bind_rot")
            if bind_pos is not None:
                pelvis_disp = ctx.state.get("pelvis_displacement", [0.0, 0.0, 0.0])
                ref_pos = v_add(bind_pos, pelvis_disp)
                ctrl_pos = v_lerp(ref_pos, ctrl_pos, weight)
            if bind_rot is not None:
                ctrl_rot = q_slerp(bind_rot, ctrl_rot, weight)

        ctrl_euler = q_to_euler_deg(ctrl_rot, rig.rotation_orders.get(chain.ik_control, 'xyz'))

        ctx.result.ik_goals[self.chain_id] = {
            "ik_control": chain.ik_control,
            "target_pos": ctrl_pos,
            "target_rot": ctrl_rot,
            "extension_ratio": extension_ratio
        }

        ctx.result.target_transforms[chain.ik_control] = {
            "t": ctrl_pos,
            "r": ctrl_euler,
            "q": ctrl_rot,
            "space": "world"
        }

        # Save to context for pole vector op and ground contact op
        ctx.state[f"{self.chain_id}_p_root"] = p_anchor
        ctx.state[f"{self.chain_id}_p_mid"] = v_add(p_anchor, v_scale(v_norm(v_sub(p_mid_src, p_root_src)), l1_tgt))
        ctx.state[f"{self.chain_id}_p_end"] = target_end_ws
        ctx.state[f"{self.chain_id}_len"] = l_tgt_max

        return True
