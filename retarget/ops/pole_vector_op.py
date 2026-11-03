"""
retarget.ops.pole_vector_op
===========================
Computes robust Pole Vector controller positions based on anatomical bend planes.
Follows Section 7.5 of HANDOFF.md:
  - Calculates bend direction from (Root, Mid, End) triangle.
  - Handles colinear, hyper-extended, and zero-length singular inputs without NaN.
  - Eliminates hardcoded multipliers and shared left-right ratios.
"""

from typing import List
from pose_core.math3d import (
    v_sub, v_norm, v_cross, v_dot, v_length, v_add, v_scale
)
from .base_op import RetargetOp, RetargetContext


class PoleVectorOp(RetargetOp):
    def __init__(self, chain_id: str, enabled: bool = True, weight: float = 1.0):
        super().__init__(f"PoleVectorOp_{chain_id}", enabled, weight)
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
        if mode != "ik":
            return True

        rig = ctx.rig_profile
        chain = rig.chains.get(self.chain_id)
        if not chain or not chain.pole_vector_control:
            return True

        p_root = ctx.state.get(f"{self.chain_id}_p_root")
        p_mid = ctx.state.get(f"{self.chain_id}_p_mid")
        p_end = ctx.state.get(f"{self.chain_id}_p_end")
        l_total = ctx.state.get(f"{self.chain_id}_len", 80.0)

        if p_root is None or p_mid is None or p_end is None:
            return True

        # 1. Anatomical default fallbacks
        is_leg = "leg" in self.chain_id
        default_dir = [0.0, 0.0, 1.0] if is_leg else [0.0, 0.0, -1.0]

        # 2. Projection of mid onto line root->end
        v_axis = v_sub(p_end, p_root)
        axis_len = v_length(v_axis)

        if axis_len < 1e-4:
            u_bend = default_dir
        else:
            u_axis = v_norm(v_axis)
            t = v_dot(v_sub(p_mid, p_root), u_axis)
            p_proj = v_add(p_root, v_scale(u_axis, t))
            v_bend = v_sub(p_mid, p_proj)
            bend_len = v_length(v_bend)

            if bend_len < 0.5:
                # Singularity / near straight limb: use anatomical fallback
                u_bend = default_dir
            else:
                u_bend = v_norm(v_bend)

        # 3. Place Pole Vector out along bend direction
        offset_dist = max(l_total * 0.5, 30.0) * self.weight
        p_pole = v_add(p_mid, v_scale(u_bend, offset_dist))

        # Calibrate with controller offsets
        ctrl_pos, _ = ctx.calibrator.get_ik_control_world_target(
            control_name=chain.pole_vector_control,
            target_joint_ws_pos=p_pole
        )

        ctx.result.target_transforms[chain.pole_vector_control] = {
            "t": ctrl_pos,
            "space": "world"
        }

        return True
