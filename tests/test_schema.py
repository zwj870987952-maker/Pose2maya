"""
Unit tests for pose_core.schema and pose_core.mhr_adapter
"""

import os
import unittest
from pose_core.schema import SkeletonDefinition, PoseSample, RigProfile, RetargetProfile
from pose_core.mhr_adapter import (
    get_authoritative_mhr_skeleton_def,
    load_legacy_skeleton_json
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_JSON = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")


class TestSchemaAndAdapter(unittest.TestCase):

    def test_skeleton_definition_validation(self):
        # Valid definition
        skel = SkeletonDefinition(
            skeleton_id="test",
            num_joints=3,
            parent_indices=[-1, 0, 1],
            joint_names=["root", "spine", "head"],
            rest_translations=[[0, 0, 0], [0, 50, 0], [0, 50, 0]],
            rest_rotations=[[0, 0, 0, 1], [0, 0, 0, 1], [0, 0, 0, 1]],
            reference_hip_height=50.0
        )
        errors = skel.validate()
        self.assertEqual(len(errors), 0)

        # Invalid cycle
        skel_cycle = SkeletonDefinition(
            skeleton_id="cycle",
            num_joints=2,
            parent_indices=[1, 0],
            joint_names=["a", "b"],
            rest_translations=[[0, 0, 0], [0, 10, 0]],
            rest_rotations=[[0, 0, 0, 1], [0, 0, 0, 1]]
        )
        errors_cycle = skel_cycle.validate()
        self.assertTrue(any("Cycle" in e or "parent" in e for e in errors_cycle))

    def test_authoritative_mhr_skeleton_def(self):
        skel = get_authoritative_mhr_skeleton_def()
        self.assertEqual(skel.num_joints, 127)
        self.assertEqual(len(skel.parent_indices), 127)
        self.assertEqual(len(skel.rest_translations), 127)
        self.assertEqual(skel.units, "cm")
        self.assertEqual(skel.up_axis, "+Y")
        self.assertAlmostEqual(skel.reference_hip_height, 92.3987, places=3)
        self.assertIn("spine", skel.chains)
        self.assertIn("left_arm", skel.chains)
        self.assertIn("right_leg", skel.chains)

        errors = skel.validate()
        self.assertEqual(errors, [])

    def test_load_legacy_skeleton_json(self):
        if not os.path.exists(SAMPLE_JSON):
            self.skipTest(f"Sample file not found: {SAMPLE_JSON}")

        sample = load_legacy_skeleton_json(SAMPLE_JSON)
        self.assertEqual(sample.schema_version, "2.0")
        self.assertEqual(sample.skeleton_id, "mhr_127")
        self.assertEqual(len(sample.local_rotations), 127)
        self.assertEqual(len(sample.world_positions), 127)

        # Check that pelvis (joint 1) height is positive (Y-up, ~92 cm)
        pelvis_pos = sample.world_positions[1]
        self.assertGreater(pelvis_pos[1], 80.0)  # > 80 cm
        self.assertLess(pelvis_pos[1], 110.0)   # < 110 cm

        # Camera parameter separation check
        self.assertIsNotNone(sample.camera)
        self.assertIn("pred_cam_t", sample.camera)
        self.assertEqual(sample.root_translation, [0.0, 0.0, 0.0])


if __name__ == '__main__':
    unittest.main()
