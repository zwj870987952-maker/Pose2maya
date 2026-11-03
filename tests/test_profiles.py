"""
Unit tests for retarget.profiles and retarget.calibration
"""

import unittest
from retarget.profiles import (
    load_rig_profile, save_rig_profile,
    get_preset_as5, get_preset_pure_joints_ue5, resolve_node_name
)
from retarget.calibration import RigCalibrator
from pose_core.mhr_adapter import get_authoritative_mhr_skeleton_def
from pose_core.math3d import q_identity


class TestProfilesAndCalibration(unittest.TestCase):

    def test_namespace_resolution(self):
        self.assertEqual(resolve_node_name("IKArm_L", ""), "IKArm_L")
        self.assertEqual(resolve_node_name("IKArm_L", "Venom_Rig2"), "Venom_Rig2:IKArm_L")
        self.assertEqual(resolve_node_name("Venom_Rig2:IKArm_L", "Venom_Rig2"), "Venom_Rig2:IKArm_L")
        self.assertEqual(resolve_node_name("Root_M", "char:"), "char:Root_M")

    def test_load_and_save_profile(self):
        as5 = get_preset_as5()
        self.assertEqual(as5.character_id, "advanced_skeleton_5")
        self.assertIn("left_arm", as5.chains)
        self.assertEqual(as5.chains["left_arm"].ik_control, "IKArm_L")

        loaded = load_rig_profile("advanced_skeleton_5")
        self.assertEqual(loaded.character_id, as5.character_id)
        self.assertEqual(loaded.root_node, "Root_M")

    def test_rig_calibrator_offsets(self):
        skel = get_authoritative_mhr_skeleton_def()
        rig = get_preset_as5()
        calibrator = RigCalibrator(skel, rig)
        calibrator.set_target_hip_height(100.0)

        # Ratio check: 100 / 92.4
        ratio = calibrator.get_hip_height_ratio()
        self.assertAlmostEqual(ratio, 100.0 / 92.3987, places=3)

        # Controller offset registration
        calibrator.register_controller_bind_pose(
            control_name="IKArm_L",
            bind_pos_ws=[50.0, 140.0, 5.0],
            bind_rot_ws=[0.0, 0.0, 0.0, 1.0],
            joint_pos_ws=[50.0, 140.0, 0.0],
            joint_rot_ws=[0.0, 0.0, 0.0, 1.0]
        )
        ctrl_pos, ctrl_rot = calibrator.get_ik_control_world_target(
            control_name="IKArm_L",
            target_joint_ws_pos=[45.0, 130.0, 10.0],
            target_joint_ws_rot=[0.0, 0.0, 0.0, 1.0]
        )
        # Position offset was [0, 0, 5] -> ctrl_pos should be [45, 130, 15]
        self.assertEqual(ctrl_pos, [45.0, 130.0, 15.0])


if __name__ == '__main__':
    unittest.main()
