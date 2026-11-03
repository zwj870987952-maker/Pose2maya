"""
retarget.engine
===============
OpStack execution engine for humanoid pose retargeting.
Connects Source SkeletonDefinition, PoseSample, RigProfile, and RetargetProfile.
"""

from typing import List, Optional

from pose_core.schema import (
    SkeletonDefinition, PoseSample, RigProfile, RetargetProfile, RetargetResult
)
from pose_core.mhr_adapter import get_authoritative_mhr_skeleton_def
from retarget.calibration import RigCalibrator
from retarget.profiles import get_preset_as5, load_retarget_profile
from retarget.ops import (
    RetargetOp, RetargetContext,
    PelvisOp, FKChainOp, IKGoalsOp,
    PoleVectorOp, EndEffectorOp, GroundContactOp
)


class RetargetEngine:
    def __init__(self, ops: Optional[List[RetargetOp]] = None):
        self.ops = ops if ops is not None else self._build_default_op_stack()

    def _build_default_op_stack(self) -> List[RetargetOp]:
        ops = []
        # 1. Pelvis motion & root scaling
        ops.append(PelvisOp())

        # 2. FK Chains (spine, neck/head, and limbs if FK requested)
        for chain_id in ["spine", "neck_head", "left_arm", "right_arm", "left_leg", "right_leg"]:
            ops.append(FKChainOp(chain_id=chain_id))

        # 3. IK Limb Goals
        for chain_id in ["left_arm", "right_arm", "left_leg", "right_leg"]:
            ops.append(IKGoalsOp(chain_id=chain_id))

        # 4. Pole Vectors (elbows & knees)
        for chain_id in ["left_arm", "right_arm", "left_leg", "right_leg"]:
            ops.append(PoleVectorOp(chain_id=chain_id))

        # 5. End effector orientation (hands & feet)
        for chain_id in ["left_arm", "right_arm", "left_leg", "right_leg"]:
            ops.append(EndEffectorOp(chain_id=chain_id))

        # 6. Optional floor contact
        ops.append(GroundContactOp())

        return ops

    def retarget(
        self,
        source_pose: PoseSample,
        source_def: Optional[SkeletonDefinition] = None,
        rig_profile: Optional[RigProfile] = None,
        retarget_profile: Optional[RetargetProfile] = None,
        calibrator: Optional[RigCalibrator] = None
    ) -> RetargetResult:
        """
        Executes retargeting pipeline on input pose sample.
        """
        import copy
        if source_def is None:
            source_def = get_authoritative_mhr_skeleton_def()
        if rig_profile is None:
            rig_profile = get_preset_as5()
        if retarget_profile is None:
            retarget_profile = load_retarget_profile("default_retarget")

        # Input validation (AUD-17)
        pose_errors = source_pose.validate(source_def.num_joints)
        def_errors = source_def.validate()
        rig_errors = rig_profile.validate() if hasattr(rig_profile, "validate") else []
        if pose_errors or def_errors or rig_errors:
            res = RetargetResult(success=False)
            res.errors.extend(pose_errors)
            res.errors.extend(def_errors)
            res.errors.extend(rig_errors)
            return res

        # Reconstruct world_positions if empty (AUD-11 / AUD-17)
        if (not source_pose.world_positions or len(source_pose.world_positions) == 0) and source_pose.local_rotations:
            from pose_core.math3d import fk_reconstruct
            source_pose.world_positions, _ = fk_reconstruct(
                source_def.parent_indices,
                source_def.rest_translations,
                source_pose.local_rotations,
                root_translation=source_pose.root_translation,
                root_rotation=source_pose.root_rotation
            )

        # Deep-copy retarget_profile so caller's object is never mutated (AUD-15)
        eff_retarget_prof = copy.deepcopy(retarget_profile)

        if calibrator is None:
            calibrator = RigCalibrator(source_def, rig_profile)

        ctx = RetargetContext(
            source_pose=source_pose,
            source_def=source_def,
            rig_profile=rig_profile,
            retarget_profile=eff_retarget_prof,
            calibrator=calibrator
        )

        # Validate chain mode compatibility against target rig capabilities
        for chain_id, chain in rig_profile.chains.items():
            req_mode = eff_retarget_prof.chain_modes.get(chain_id, "fk")
            if req_mode == "ik" and (chain.chain_type == "fk" or not chain.ik_control):
                eff_retarget_prof.chain_modes[chain_id] = "fk"
                ctx.result.warnings.append(
                    f"Chain '{chain_id}' does not support IK on rig '{rig_profile.character_id}'; automatically fell back to FK."
                )

        for op in self.ops:
            try:
                op_ok = op.execute(ctx)
                if op_ok is False:
                    ctx.result.errors.append(f"{op.name} failed during execution.")
                    ctx.result.success = False
            except Exception as e:
                ctx.result.errors.append(f"Error executing {op.name}: {str(e)}")
                ctx.result.success = False

        if not ctx.result.target_transforms:
            ctx.result.warnings.append("No controller or joint transforms were generated.")

        return ctx.result


def retarget(
    source_pose: PoseSample,
    source_def: Optional[SkeletonDefinition] = None,
    rig_profile: Optional[RigProfile] = None,
    retarget_profile: Optional[RetargetProfile] = None,
    calibrator: Optional[RigCalibrator] = None
) -> RetargetResult:
    """Convenience functional wrapper for RetargetEngine."""
    engine = RetargetEngine()
    return engine.retarget(source_pose, source_def, rig_profile, retarget_profile, calibrator)
