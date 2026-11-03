"""
retarget.ops.fk_chain_op
========================
FK Chain retargeting operation.
Follows Section 7.3 of HANDOFF.md:
  - Preserves fixed bone lengths and jointOrient.
  - Distributes rotations across multi-bone chains (e.g. spine).
  - Incorporates A-to-T pose calibration and controller bind offsets.
  - Switches rig to FK mode when active.
"""

from pose_core.math3d import (
    q_identity, q_multiply, q_inverse, q_slerp, q_to_euler_deg
)
from .base_op import RetargetOp, RetargetContext


class FKChainOp(RetargetOp):
    def __init__(self, chain_id: str, enabled: bool = True, weight: float = 1.0):
        super().__init__(f"FKChainOp_{chain_id}", enabled, weight)
        self.chain_id = chain_id

    def execute(self, ctx: RetargetContext) -> bool:
        if not self.enabled or self.weight <= 0.0:
            return True

        retarget_prof = ctx.retarget_profile
        # Part mask check
        if not retarget_prof.part_mask.get(self.chain_id, True):
            return True

        # Weight override from retarget profile if specified
        weight = retarget_prof.chain_weights.get(self.chain_id, self.weight)
        if weight <= 0.0:
            return True

        # Mode check: if mode is ik and rig supports ik, FK op does not write
        mode = retarget_prof.chain_modes.get(self.chain_id, "fk")
        rig = ctx.rig_profile
        chain = rig.chains.get(self.chain_id)
        if not chain or not chain.fk_controls:
            return True

        if mode == "ik" and chain.chain_type in ("ik", "fk_ik") and chain.ik_control:
            # IK mode active, FK chain should not drive
            return True

        source_indices = ctx.source_def.chains.get(self.chain_id, [])
        if not source_indices:
            return True

        pose = ctx.source_pose
        fk_ctrls = chain.fk_controls
        num_tgt = len(fk_ctrls)
        num_src = len(source_indices)

        # 1. Ensure mode switch is set to FK mode
        if chain.fk_ik_switch_attr:
            ctx.result.mode_switches[chain.fk_ik_switch_attr] = chain.fk_value

        # 2. Extract and distribute rotations with calibration
        if num_tgt == num_src:
            for i in range(num_tgt):
                ctrl = fk_ctrls[i]
                src_idx = source_indices[i]
                q_src = pose.local_rotations[src_idx] if src_idx < len(pose.local_rotations) else q_identity()
                src_rest_q = ctx.source_def.rest_rotations[src_idx] if src_idx < len(ctx.source_def.rest_rotations) else q_identity()

                # Delta rotation from source rest
                delta_q = q_multiply(q_src, q_inverse(src_rest_q))

                # Chain / Joint calibration (e.g. A-pose to T-pose delta)
                calib_q = ctx.calibrator.get_chain_calib_rotation(self.chain_id, ctrl)
                tgt_q = q_multiply(calib_q, delta_q)

                # Controller bind offset
                ctrl_offset = ctx.calibrator.get_controller_offset(ctrl)
                if ctrl_offset and "rot_offset" in ctrl_offset:
                    tgt_q = q_multiply(tgt_q, ctrl_offset["rot_offset"])

                if weight < 1.0:
                    tgt_q = q_slerp(calib_q, tgt_q, weight)

                euler = q_to_euler_deg(tgt_q, rig.rotation_orders.get(ctrl, 'xyz'))
                ctx.result.target_transforms[ctrl] = {
                    "r": euler,
                    "q": tgt_q
                }
        else:
            # Different joint counts (e.g. 4 spine joints vs 2 FK controls)
            chunk_size = num_src / float(num_tgt)
            for t_idx in range(num_tgt):
                ctrl = fk_ctrls[t_idx]
                start_s = int(t_idx * chunk_size)
                end_s = int((t_idx + 1) * chunk_size)
                if t_idx == num_tgt - 1:
                    end_s = num_src

                accum_delta = q_identity()
                for s_i in range(start_s, end_s):
                    idx = source_indices[s_i]
                    if idx < len(pose.local_rotations):
                        q_src = pose.local_rotations[idx]
                        src_rest_q = ctx.source_def.rest_rotations[idx] if idx < len(ctx.source_def.rest_rotations) else q_identity()
                        d_q = q_multiply(q_src, q_inverse(src_rest_q))
                        accum_delta = q_multiply(accum_delta, d_q)

                calib_q = ctx.calibrator.get_chain_calib_rotation(self.chain_id, ctrl)
                tgt_q = q_multiply(calib_q, accum_delta)

                ctrl_offset = ctx.calibrator.get_controller_offset(ctrl)
                if ctrl_offset and "rot_offset" in ctrl_offset:
                    tgt_q = q_multiply(tgt_q, ctrl_offset["rot_offset"])

                if weight < 1.0:
                    tgt_q = q_slerp(calib_q, tgt_q, weight)

                euler = q_to_euler_deg(tgt_q, rig.rotation_orders.get(ctrl, 'xyz'))
                ctx.result.target_transforms[ctrl] = {
                    "r": euler,
                    "q": tgt_q
                }

        return True
