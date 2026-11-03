"""
retarget.ops.base_op
====================
Base class and context for retargeting operations in the OpStack.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from pose_core.schema import (
    SkeletonDefinition, PoseSample, RigProfile, RetargetProfile, RetargetResult
)
from retarget.calibration import RigCalibrator


@dataclass
class RetargetContext:
    source_pose: PoseSample
    source_def: SkeletonDefinition
    rig_profile: RigProfile
    retarget_profile: RetargetProfile
    calibrator: RigCalibrator
    result: RetargetResult = field(default_factory=RetargetResult)
    # Scratchpad for intermediate data between ops
    state: Dict[str, Any] = field(default_factory=dict)


class RetargetOp:
    """Base interface for an atomic retargeting operation."""
    def __init__(self, name: str, enabled: bool = True, weight: float = 1.0):
        self.name = name
        self.enabled = enabled
        self.weight = weight

    def execute(self, ctx: RetargetContext) -> bool:
        raise NotImplementedError
