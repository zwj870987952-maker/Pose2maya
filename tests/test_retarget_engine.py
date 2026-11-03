"""
Unit tests for retarget.engine, ops, and calibration
"""

import os
import unittest
from pose_core.mhr_adapter import load_legacy_skeleton_json, get_authoritative_mhr_skeleton_def
from pose_core.schema import RetargetProfile
from retarget.engine import retarget, RetargetEngine
from retarget.profiles import get_preset_as5, get_preset_pure_joints_ue5

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_JSON = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
DANCING_JSON = os.path.join(REPO_ROOT, "data", "sample_poses", "02_human_dancing_skeleton.json")


class TestRetargetEngine(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(SAMPLE_JSON):
            self.skipTest(f"Sample JSON not found: {SAMPLE_JSON}")
        self.sample_pose = load_legacy_skeleton_json(SAMPLE_JSON)
        self.skel_def = get_authoritative_mhr_skeleton_def()

    def test_default_as5_retargeting(self):
        as5_rig = get_preset_as5()
        res = retarget(self.sample_pose, self.skel_def, as5_rig)

        self.assertTrue(res.success)
        self.assertGreater(len(res.target_transforms), 0)

        # Check Pelvis
        self.assertIn("RootX_M", res.target_transforms)
        self.assertIn("t", res.target_transforms["RootX_M"])

        # Check IK controls
        self.assertIn("IKArm_L", res.target_transforms)
        self.assertIn("IKArm_R", res.target_transforms)
        self.assertIn("IKLeg_L", res.target_transforms)
        self.assertIn("IKLeg_R", res.target_transforms)
        self.assertIn("PoleArm_L", res.target_transforms)
        self.assertIn("PoleLeg_L", res.target_transforms)

        # Check mode switches
        self.assertIn("FKIKArm_L.FKIKBlend", res.mode_switches)
        self.assertEqual(res.mode_switches["FKIKArm_L.FKIKBlend"], 10.0)

    def test_fk_mode_retargeting(self):
        as5_rig = get_preset_as5()
        retarget_prof = RetargetProfile(
            chain_modes={
                "spine": "fk",
                "neck_head": "fk",
                "left_arm": "fk",
                "right_arm": "fk",
                "left_leg": "fk",
                "right_leg": "fk"
            }
        )
        res = retarget(self.sample_pose, self.skel_def, as5_rig, retarget_prof)

        self.assertTrue(res.success)
        # Should drive FK controls instead of IK
        self.assertIn("FKShoulder_L", res.target_transforms)
        self.assertIn("FKElbow_L", res.target_transforms)
        self.assertIn("FKWrist_L", res.target_transforms)
        self.assertNotIn("IKArm_L", res.target_transforms)

        # Mode switch should be FK value (0.0)
        self.assertEqual(res.mode_switches["FKIKArm_L.FKIKBlend"], 0.0)

    def test_pure_joints_ue5_retargeting(self):
        ue5_rig = get_preset_pure_joints_ue5()
        retarget_prof = RetargetProfile(
            chain_modes={
                "spine": "fk",
                "neck_head": "fk",
                "left_arm": "fk",
                "right_arm": "fk",
                "left_leg": "fk",
                "right_leg": "fk"
            }
        )
        res = retarget(self.sample_pose, self.skel_def, ue5_rig, retarget_prof)

        self.assertTrue(res.success)
        self.assertIn("upperarm_l", res.target_transforms)
        self.assertIn("lowerarm_l", res.target_transforms)
        self.assertIn("thigh_l", res.target_transforms)

    def test_part_masking(self):
        as5_rig = get_preset_as5()
        retarget_prof = RetargetProfile(
            part_mask={
                "spine": True,
                "neck_head": True,
                "left_arm": False,  # Mask out left arm
                "right_arm": True,
                "left_leg": True,
                "right_leg": True
            }
        )
        res = retarget(self.sample_pose, self.skel_def, as5_rig, retarget_prof)
        self.assertNotIn("IKArm_L", res.target_transforms)
        self.assertNotIn("PoleArm_L", res.target_transforms)
        self.assertIn("IKArm_R", res.target_transforms)

    def test_straight_limb_singularity(self):
        # Create synthetic pose where limb is perfectly straight
        straight_pose = load_legacy_skeleton_json(SAMPLE_JSON)
        # Hip at [0, 90, 0], Knee at [0, 50, 0], Ankle at [0, 10, 0] (perfect line along Y)
        straight_pose.world_positions[2] = [10.0, 90.0, 0.0]
        straight_pose.world_positions[3] = [10.0, 50.0, 0.0]
        straight_pose.world_positions[4] = [10.0, 10.0, 0.0]

        as5_rig = get_preset_as5()
        res = retarget(straight_pose, self.skel_def, as5_rig)
        self.assertTrue(res.success)
        pole_pos = res.target_transforms["PoleLeg_L"]["t"]
        # Must not be NaN or Inf
        for coord in pole_pos:
            self.assertFalse(coord != coord, "Coordinate is NaN")
            self.assertTrue(abs(coord) < 1e6, "Coordinate exploded")


if __name__ == '__main__':
    unittest.main()
