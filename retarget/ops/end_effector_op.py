"""
retarget.ops.end_effector_op
============================
Applies full wrist and foot orientation to IK and FK end effectors.
Follows Section 7.6 of HANDOFF.md and AUD-07:
  - Preserves calibrated IK controller orientations set by IKGoalsOp.
  - Avoids overwriting calibrated IK rotation with uncalibrated local rotations.
  - Directly drives FK end-effectors in FK mode.
"""

from pose_core.math3d import (
    q_identity, q_multiply, q_inverse, q_slerp, q_to_euler_deg, fk_reconstruct
)
from .base_op import RetargetOp, RetargetContext


class EndEffectorOp(RetargetOp):
    def __init__(self, chain_id: str, enabled: bool = True, weight: float = 1.0):
        super().__init__(f"EndEffectorOp_{chain_id}", enabled, weight)
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

        rig = ctx.rig_profile
        chain = rig.chains.get(self.chain_id)
        if not chain:
            return True

        mode = retarget_prof.chain_modes.get(self.chain_id, "ik")
        # In IK mode, IKGoalsOp is the authoritative owner of the IK control transform.
        # Do not overwrite IK control with local wrist rotations (AUD-07).
        if mode == "ik" and chain.chain_type in ("ik", "fk_ik") and chain.ik_control:
            return True

        # FK mode end-effector processing
        source_indices = ctx.source_def.chains.get(self.chain_id, [])
        if not source_indices:
            return True

        end_idx = source_indices[-1]
        pose = ctx.source_pose
        if end_idx >= len(pose.local_rotations):
            return True

        target_ctrl = chain.fk_controls[-1] if chain.fk_controls else None
        if not target_ctrl:
            return True

        if target_ctrl in ctx.result.target_transforms and "r" in ctx.result.target_transforms[target_ctrl]:
            # End effector was already computed (e.g. by FKChainOp); avoid clobbering (AUD-04/AUD-07)
            return True

        q_src = pose.local_rotations[end_idx]
        src_rest_q = ctx.source_def.rest_rotations[end_idx] if end_idx < len(ctx.source_def.rest_rotations) else q_identity()

        delta_q = q_multiply(q_src, q_inverse(src_rest_q))
        calib_q = ctx.calibrator.get_chain_calib_rotation(self.chain_id, target_ctrl)
        tgt_q = q_multiply(calib_q, delta_q)

        ctrl_offset = ctx.calibrator.get_controller_offset(target_ctrl)
        if ctrl_offset and "rot_offset" in ctrl_offset:
            tgt_q = q_multiply(tgt_q, ctrl_offset["rot_offset"])

        if weight < 1.0:
            tgt_q = q_slerp(calib_q, tgt_q, weight)

        euler = q_to_euler_deg(tgt_q, rig.rotation_orders.get(target_ctrl, 'xyz'))
        if target_ctrl not in ctx.result.target_transforms:
            ctx.result.target_transforms[target_ctrl] = {}
        ctx.result.target_transforms[target_ctrl]["r"] = euler
        ctx.result.target_transforms[target_ctrl]["q"] = tgt_q

        return True
