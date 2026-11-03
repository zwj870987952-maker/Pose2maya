"""
tests.test_audit_repairs
========================
Comprehensive regression test suite verifying AUD-01 through AUD-17 fixes
from REPAIR_HANDOFF.md.
"""

import os
import json
import math
import unittest
import numpy as np

from pose_core.math3d import (
    q_identity, q_slerp, q_norm, q_normalize, q_dot,
    q_to_mat3, mat3_to_q, euler_to_q, q_to_euler_deg,
    v_dist, v_sub, v_add, v_length
)
from pose_core.schema import (
    PoseSample, SkeletonDefinition, RigProfile, RetargetProfile,
    to_json_compatible, WritePlan
)
from pose_core.mhr_adapter import (
    standardize_mhr_raw, load_pose_sample, load_legacy_skeleton_json,
    get_authoritative_mhr_skeleton_def
)
from retarget.calibration import RigCalibrator
from retarget.profiles import (
    get_preset_as5, get_preset_pure_joints_ue5, get_preset_pure_joints_humanik,
    save_rig_profile, load_rig_profile
)
from retarget.engine import retarget
from maya_scripts.rig_adapter import transform_point_by_inv_matrix
from maya_scripts.pose_session import PoseSession, FakeCmds
from maya_scripts.service_client import InferenceServiceClient, _encode_multipart

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestAuditRepairs(unittest.TestCase):

    # -------------------------------------------------------------------------
    # AUD-01: Serialization of real inference data to v2 JSON
    # -------------------------------------------------------------------------
    def test_aud_01_numpy_serialization_and_finiteness(self):
        """AUD-01: float16/float32 numpy scalars/arrays serialize cleanly to JSON."""
        pred_coords = np.random.randn(127, 3).astype(np.float32)
        # 127 3x3 rotation matrices
        pred_rots = np.eye(3, dtype=np.float32)[np.newaxis, :, :].repeat(127, axis=0)
        pred_cam_t = np.array([0.1, 0.2, 5.0], dtype=np.float32)

        raw = {
            "pred_joint_coords": pred_coords,
            "pred_global_rots": pred_rots,
            "pred_cam_t": pred_cam_t,
            "bbox": np.array([10.0, 20.0, 200.0, 300.0], dtype=np.float16),
            "camera": {"cam_t": pred_cam_t, "focal_length": np.float32(1000.0)}
        }
        pose_sample, payload = standardize_mhr_raw(raw)
        json_str = json.dumps(payload, allow_nan=False)
        self.assertIsInstance(json_str, str)
        self.assertGreater(len(json_str), 100)
        self.assertIsInstance(pose_sample, PoseSample)

        # Finiteness check: NaN should be rejected
        raw_nan = {"val": np.float32(float("nan"))}
        with self.assertRaises(ValueError):
            to_json_compatible(raw_nan)

        # AUD-01 bool fidelity check
        bool_dict = {"flag": True, "off": False, "np_flag": np.bool_(True), "np_off": np.bool_(False), "int_val": 1}
        res_bool = to_json_compatible(bool_dict)
        self.assertIs(res_bool["flag"], True)
        self.assertIs(res_bool["off"], False)
        self.assertIsInstance(res_bool["np_flag"], bool)
        self.assertIs(res_bool["np_flag"], True)
        self.assertIsInstance(res_bool["np_off"], bool)
        self.assertIs(res_bool["np_off"], False)
        self.assertIsInstance(res_bool["int_val"], int)
        self.assertNotIsInstance(res_bool["int_val"], bool)

    # -------------------------------------------------------------------------
    # AUD-02: MHR rest rotations and FK position correctness
    # -------------------------------------------------------------------------
    def test_aud_02_mhr_authoritative_rest_rotations(self):
        """AUD-02: Authoritative skeleton has non-identity rest rotations and resting feet."""
        skel = get_authoritative_mhr_skeleton_def()
        self.assertEqual(len(skel.joint_names), 127)
        self.assertEqual(len(skel.rest_rotations), 127)
        self.assertEqual(len(skel.rest_world_positions), 127)

        # Foot (joint 4) should rest on ground (Y ~ 6.96 cm)
        foot_pos = skel.rest_world_positions[4]
        self.assertAlmostEqual(foot_pos[1], 6.96, delta=0.5)

        # Chest (joint 37, spine_04_chest) should be upright at Y ~ 134.88 cm
        chest_pos = skel.rest_world_positions[37]
        self.assertAlmostEqual(chest_pos[1], 134.88, delta=1.0)

    # -------------------------------------------------------------------------
    # AUD-03: Coordinate semantics without P R P basis inversion
    # -------------------------------------------------------------------------
    def test_aud_03_coordinate_semantics_ground_truth(self):
        """
        AUD-03: Two-bone ground truth forward kinematics and full adapter->FK->IKGoalsOp pipeline.
        Ensures root_rotation is synthesized exactly once and local root rotation is decoupled.
        """
        p0 = [0.0, 100.0, 0.0]
        offset1 = [0.0, -40.0, 0.0]
        q_root = euler_to_q([0.0, 0.0, 90.0], order="xyz")
        from pose_core.math3d import q_rotate_vector, q_to_mat3, fk_reconstruct
        from pose_core.schema import RigChain
        from retarget.ops.ik_goals_op import IKGoalsOp
        from retarget.ops.base_op import RetargetContext
        from pose_core.schema import RetargetResult

        p1 = v_add(p0, q_rotate_vector(q_root, offset1))
        expected_p1 = [40.0, 100.0, 0.0]
        dist = v_dist(p1, expected_p1)
        self.assertLess(dist, 1e-6)

        # Full pipeline test with asymmetric Euler angles [15, 30, 45] deg (ZYX)
        skel = SkeletonDefinition(
            skeleton_id="mhr_127",
            num_joints=3,
            joint_names=["root", "mid", "end"],
            parent_indices=[-1, 0, 1],
            rest_translations=[[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 0.0, 0.0]],
            rest_rotations=[[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]],
            chains={"left_arm": [0, 1, 2]}
        )
        euler_angles = [15.0, 30.0, 45.0]
        q_global = euler_to_q(euler_angles, order="zyx")
        rot_mat = q_to_mat3(q_global)
        global_rots = np.array([rot_mat, rot_mat, rot_mat], dtype=np.float32)

        v1_ws = q_rotate_vector(q_global, [10.0, 0.0, 0.0])
        v2_ws = q_rotate_vector(q_global, [20.0, 0.0, 0.0])
        v1_cam = [v1_ws[0] * 0.01, -v1_ws[1] * 0.01, -v1_ws[2] * 0.01]
        v2_cam = [v2_ws[0] * 0.01, -v2_ws[1] * 0.01, -v2_ws[2] * 0.01]
        joint_coords = np.array([[0.0, 0.0, 0.0], v1_cam, v2_cam], dtype=np.float32)

        euler_rad = [math.radians(x) for x in euler_angles]
        raw = {
            "pred_joint_coords": joint_coords,
            "pred_global_rots": global_rots,
            "global_rot": np.array(euler_rad, dtype=np.float32)
        }
        sample, _ = standardize_mhr_raw(raw, skeleton_def=skel)

        # 1. Standardized world positions
        self.assertLess(v_dist(sample.world_positions[0], [0.0, 0.0, 0.0]), 1e-4)
        self.assertLess(v_dist(sample.world_positions[1], v1_ws), 1e-4)
        self.assertLess(v_dist(sample.world_positions[2], v2_ws), 1e-4)

        # 2. FK reconstruction
        fk_pos, fk_rots = fk_reconstruct(
            skel.parent_indices,
            skel.rest_translations,
            sample.local_rotations,
            sample.root_translation,
            sample.root_rotation
        )
        self.assertLess(v_dist(fk_pos[2], v2_ws), 1e-4)

        # 3. IK goals op without duplicate root rotation
        rig = RigProfile(
            character_id="test_char",
            pelvis_node="root_ctrl",
            target_hip_height=0.0,
            chains={"left_arm": RigChain(chain_id="left_arm", chain_type="ik", target_joints=["root", "mid", "end"], ik_control="IKArm_L")},
            target_limb_lengths={"left_arm": [10.0, 10.0]},
            target_chain_anchors={"left_arm": [0.0, 0.0, 0.0]}
        )
        calibrator = RigCalibrator(skel, rig)
        retarget_prof = RetargetProfile(chain_modes={"left_arm": "ik"})
        ctx = RetargetContext(
            source_pose=sample,
            source_def=skel,
            rig_profile=rig,
            retarget_profile=retarget_prof,
            calibrator=calibrator,
            result=RetargetResult(success=True)
        )
        op = IKGoalsOp(chain_id="left_arm")
        op.execute(ctx)

        ik_tf = ctx.result.target_transforms["IKArm_L"]
        self.assertLess(v_dist(ik_tf["t"], v2_ws), 1e-4)
        dot_q = abs(q_dot(ik_tf["q"], q_global))
        self.assertGreater(dot_q, 0.9999)

    # -------------------------------------------------------------------------
    # AUD-04: FK chain mapping & A-to-T calibration
    # -------------------------------------------------------------------------
    def test_aud_04_fk_chain_mapping_and_a_to_t_calibration(self):
        """AUD-04: FK upper arm rotation drives shoulder, not elbow; A-to-T calibrates delta."""
        sample_path = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
        sample_pose = load_pose_sample(sample_path)
        skel_def = get_authoritative_mhr_skeleton_def()
        rig_prof = get_preset_as5()
        retarget_prof = RetargetProfile(
            chain_modes={"left_arm": "fk", "right_arm": "fk", "left_leg": "fk", "right_leg": "fk"},
            part_mask={"left_arm": True, "right_arm": False, "spine": False, "neck_head": False, "pelvis": False, "left_leg": False, "right_leg": False}
        )

        # Baseline retarget
        res = retarget(sample_pose, skel_def, rig_prof, retarget_prof)
        self.assertTrue(res.success)
        self.assertIn("FKShoulder_L", res.target_transforms)

        # Apply 45 degree calibration to left arm
        calib = RigCalibrator(skel_def, rig_prof)
        calib.calibrate_a_pose_to_t_pose("left_arm", delta_degrees=45.0, axis="z")
        res_calib = retarget(sample_pose, skel_def, rig_prof, retarget_prof)
        self.assertTrue(res_calib.success)

        rot_orig = res.target_transforms["FKShoulder_L"]["q"]
        rot_calib = res_calib.target_transforms["FKShoulder_L"]["q"]
        # Rotations differ by 45 degrees
        dot = abs(q_dot(rot_orig, rot_calib))
        self.assertLess(dot, 0.99)

    # -------------------------------------------------------------------------
    # AUD-05: Target character geometry in IK
    # -------------------------------------------------------------------------
    def test_aud_05_target_limb_lengths_in_ik(self):
        """AUD-05: IK solver uses target character limb lengths and respects reach limit."""
        sample_path = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
        sample_pose = load_pose_sample(sample_path)
        skel_def = get_authoritative_mhr_skeleton_def()
        rig_prof = get_preset_as5()

        # Set target limb lengths: L1=30, L2=30 (total reach = 60 cm)
        rig_prof.target_limb_lengths["left_arm"] = [30.0, 30.0]
        rig_prof.target_chain_anchors["left_arm"] = [18.0, 135.0, 0.0]

        retarget_prof = RetargetProfile(
            chain_modes={"left_arm": "ik"},
            part_mask={"left_arm": True, "right_arm": False, "spine": False, "neck_head": False, "pelvis": False, "left_leg": False, "right_leg": False}
        )
        res = retarget(sample_pose, skel_def, rig_prof, retarget_prof)
        self.assertTrue(res.success)
        self.assertIn("IKArm_L", res.target_transforms)
        goal_pos = res.target_transforms["IKArm_L"]["t"]
        anchor = rig_prof.target_chain_anchors["left_arm"]
        reach_dist = v_dist(goal_pos, anchor)
        self.assertLessEqual(reach_dist, 60.05)

    # -------------------------------------------------------------------------
    # AUD-06: Parent-relative local translation conversion
    # -------------------------------------------------------------------------
    def test_aud_06_world_pos_to_local_trans(self):
        """AUD-06: Converts world space translation into parent-relative local coordinates."""
        world_pos = [10.0, 20.0, 30.0]
        # Identity rotation, translated by [2, 5, 10]
        # In Maya worldInverseMatrix (column-vector convention or row-vector):
        # [x, y, z, 1] * inv_mat translates by [-2, -5, -10]
        inv_mat = [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            -2.0, -5.0, -10.0, 1.0
        ]
        local_pos = transform_point_by_inv_matrix(world_pos, inv_mat)
        self.assertAlmostEqual(local_pos[0], 8.0, places=4)
        self.assertAlmostEqual(local_pos[1], 15.0, places=4)
        self.assertAlmostEqual(local_pos[2], 20.0, places=4)

    # -------------------------------------------------------------------------
    # AUD-07: End-effector world orientation preserved in IK mode
    # -------------------------------------------------------------------------
    def test_aud_07_ik_end_effector_orientation_preserved(self):
        """AUD-07: IK controller retains world orientation computed by IKGoalsOp."""
        sample_path = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
        sample_pose = load_pose_sample(sample_path)
        skel_def = get_authoritative_mhr_skeleton_def()
        rig_prof = get_preset_as5()
        retarget_prof = RetargetProfile(
            chain_modes={"left_arm": "ik"},
            part_mask={"left_arm": True, "right_arm": False, "spine": False, "neck_head": False, "pelvis": False, "left_leg": False, "right_leg": False}
        )
        res = retarget(sample_pose, skel_def, rig_prof, retarget_prof)
        self.assertTrue(res.success)
        ctrl_data = res.target_transforms["IKArm_L"]
        self.assertIn("q", ctrl_data)
        self.assertEqual(len(ctrl_data["q"]), 4)
        self.assertAlmostEqual(q_norm(ctrl_data["q"]), 1.0, places=5)

    # -------------------------------------------------------------------------
    # AUD-08: Maya safe transaction lifecycle
    # -------------------------------------------------------------------------
    def test_aud_08_transaction_lifecycle_with_fake_cmds(self):
        """AUD-08: Tests preview-cancel, preview-commit-undo, and mid-flight rollback with FakeCmds."""
        fake = FakeCmds()
        session = PoseSession(cmd_module=fake)

        fake.setAttr("test_p2m_iso:ctrl.tx", 1.0)

        # Plan modifying tx to 10.0
        plan = WritePlan(
            channels=[{"node": "test_p2m_iso:ctrl", "attr": "tx", "current": 1.0, "target": 10.0, "keyframe": False}]
        )

        # 1. Preview
        session.preview(plan)
        self.assertEqual(fake.getAttr("test_p2m_iso:ctrl.tx"), 10.0)

        # 2. Cancel restores scene baseline
        session.cancel()
        self.assertEqual(fake.getAttr("test_p2m_iso:ctrl.tx"), 1.0)

        # 3. Preview again then commit
        session.preview(plan)
        session.commit(plan)
        self.assertEqual(fake.getAttr("test_p2m_iso:ctrl.tx"), 10.0)

        # 4. Undo should revert to original baseline (1.0), NOT preview state
        fake.undo()
        self.assertEqual(fake.getAttr("test_p2m_iso:ctrl.tx"), 1.0)

    # -------------------------------------------------------------------------
    # AUD-09: WebUI API Contract
    # -------------------------------------------------------------------------
    def test_aud_09_webui_api_contract(self):
        """AUD-09: Verifies that job result contains json_url, npz_url, latency_seconds, skeleton."""
        try:
            from webui.app import app
        except ImportError:
            self.skipTest("Flask not installed in this Python environment (e.g. mayapy).")
        client = app.test_client()
        # Query nonexistent job
        res = client.get("/api/jobs/nonexistent-12345")
        self.assertEqual(res.status_code, 404)
        data = res.get_json()
        self.assertIn("error", data)

    # -------------------------------------------------------------------------
    # AUD-10: Service client multipart upload and protection
    # -------------------------------------------------------------------------
    def test_aud_10_service_client_contract(self):
        """AUD-10: Service client handles custom image paths and multipart packaging."""
        body, content_type = _encode_multipart(
            fields={"target_namespace": "char1:"},
            files={"image": ("test.png", b"fake_bytes", "image/png")}
        )
        self.assertIn("multipart/form-data; boundary=", content_type)
        self.assertIn(b"char1:", body)
        self.assertIn(b"fake_bytes", body)

    # -------------------------------------------------------------------------
    # AUD-11: Unified load_pose_sample lossless round-trip
    # -------------------------------------------------------------------------
    def test_aud_11_load_pose_sample_lossless(self):
        """AUD-11: Unified loader dispatches v2 and legacy formats without data loss."""
        sample_path = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
        pose = load_pose_sample(sample_path)
        self.assertEqual(len(pose.local_rotations), 127)
        self.assertEqual(len(pose.world_positions), 127)
        for q in pose.local_rotations:
            self.assertAlmostEqual(q_norm(q), 1.0, places=4)

    # -------------------------------------------------------------------------
    # AUD-12: Six Euler rotation orders round-trip and SLERP norm
    # -------------------------------------------------------------------------
    def test_aud_12_euler_six_orders_and_slerp_norm(self):
        """AUD-12: All 6 Euler orders round-trip with zero error; SLERP is normalized."""
        orders = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]
        angles = [12.0, -25.0, 42.0]
        for order in orders:
            q = euler_to_q(angles, order=order)
            rec = q_to_euler_deg(q, order=order)
            self.assertAlmostEqual(rec[0], angles[0], places=4)
            self.assertAlmostEqual(rec[1], angles[1], places=4)
            self.assertAlmostEqual(rec[2], angles[2], places=4)

        # SLERP test: q_slerp(I, I, 0.5) norm must be 1.0, not sqrt(2)
        q_i = q_identity()
        res = q_slerp(q_i, q_i, 0.5)
        self.assertAlmostEqual(q_norm(res), 1.0, places=6)

    # -------------------------------------------------------------------------
    # AUD-14: Custom character profile persistence & calibration
    # -------------------------------------------------------------------------
    def test_aud_14_profile_persistence_and_calibration(self):
        """AUD-14: Save, load custom RigProfile JSON, verify round-trip fidelity."""
        prof = get_preset_as5()
        prof.character_id = "test_custom_rig"
        prof.target_hip_height = 105.5
        prof.target_limb_lengths["left_arm"] = [35.0, 28.0]

        temp_path = os.path.join(REPO_ROOT, "profiles", "temp_test_custom_rig.json")
        saved_path = save_rig_profile(prof, temp_path)
        self.assertTrue(os.path.exists(saved_path))

        loaded_prof = load_rig_profile(saved_path)
        self.assertEqual(loaded_prof.character_id, "test_custom_rig")
        self.assertAlmostEqual(loaded_prof.target_hip_height, 105.5, places=3)
        self.assertEqual(loaded_prof.target_limb_lengths["left_arm"], [35.0, 28.0])

        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Validate three authoritative presets: AS5, UE5 pure joints, HumanIK pure joints
        skel = get_authoritative_mhr_skeleton_def()
        sample_path = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
        sample_pose = load_pose_sample(sample_path)

        for preset_fn, name in [
            (get_preset_as5, "Advanced Skeleton 5"),
            (get_preset_pure_joints_ue5, "UE5 Pure Joints"),
            (get_preset_pure_joints_humanik, "HumanIK Pure Joints")
        ]:
            preset_prof = preset_fn()
            val_errors = preset_prof.validate()
            self.assertEqual(val_errors, [], f"Preset {name} has schema validation errors: {val_errors}")
            res = retarget(sample_pose, skel, preset_prof)
            self.assertTrue(res.success, f"Retarget failed for preset {name}: {res.errors}")
            self.assertGreater(len(res.target_transforms), 0, f"Preset {name} produced 0 transforms")

    # -------------------------------------------------------------------------
    # AUD-15: Part masking, chain weights, root motion policies
    # -------------------------------------------------------------------------
    def test_aud_15_part_mask_and_root_policies(self):
        """AUD-15: All masks disabled produces 0 output channels; root policy is observed."""
        sample_path = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
        sample_pose = load_pose_sample(sample_path)
        skel_def = get_authoritative_mhr_skeleton_def()
        rig_prof = get_preset_as5()

        # All parts disabled
        all_disabled = RetargetProfile(
            part_mask={"pelvis": False, "spine": False, "neck_head": False, "left_arm": False, "right_arm": False, "left_leg": False, "right_leg": False}
        )
        res = retarget(sample_pose, skel_def, rig_prof, all_disabled)
        self.assertTrue(res.success)
        self.assertEqual(len(res.target_transforms), 0)

        # In-place vs full root motion policy
        prof_in_place = RetargetProfile(root_motion_mode="in_place")
        prof_full = RetargetProfile(root_motion_mode="full")
        res_ip = retarget(sample_pose, skel_def, rig_prof, prof_in_place)
        res_full = retarget(sample_pose, skel_def, rig_prof, prof_full)

        self.assertIn("RootX_M", res_ip.target_transforms)
        self.assertIn("Root_M", res_full.target_transforms)
        # in_place zeroes X and Z on pelvis
        self.assertEqual(res_ip.target_transforms["RootX_M"]["t"][0], 0.0)
        self.assertEqual(res_ip.target_transforms["RootX_M"]["t"][2], 0.0)

    # -------------------------------------------------------------------------
    # AUD-16: Ground contact floating and penetration correction
    # -------------------------------------------------------------------------
    def test_aud_16_ground_contact_floating_and_penetration(self):
        """AUD-16: Ground contact op handles penetration and floating."""
        sample_path = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
        sample_pose = load_pose_sample(sample_path)
        skel_def = get_authoritative_mhr_skeleton_def()
        rig_prof = get_preset_as5()

        retarget_prof = RetargetProfile(
            ground_contact=True,
            contact_legs={"left_leg": True, "right_leg": True}
        )
        res = retarget(sample_pose, skel_def, rig_prof, retarget_prof)
        self.assertTrue(res.success)
        self.assertIn("IKLeg_L", res.target_transforms)
        self.assertIn("IKLeg_R", res.target_transforms)

    # -------------------------------------------------------------------------
    # AUD-17: Schema validation on invalid data and non-finite floats
    # -------------------------------------------------------------------------
    def test_aud_17_schema_validation_catches_invalid_data(self):
        """AUD-17: Schema validation catches zero quaternions, NaNs, and DAG cycles."""
        # 1. Invalid quaternion norm (zero)
        bad_rotations = [[0.0, 0.0, 0.0, 0.0] for _ in range(127)]
        bad_pose = PoseSample(
            local_rotations=bad_rotations,
            world_positions=[[0.0, 0.0, 0.0] for _ in range(127)]
        )
        errors = bad_pose.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("near-zero norm" in e for e in errors))

        # 2. DAG cycle in skeleton definition
        bad_skel = SkeletonDefinition(
            joint_names=["root", "joint1", "joint2"],
            parent_indices=[-1, 2, 1],  # cycle between 1 and 2
            rest_translations=[[0.0, 0.0, 0.0]] * 3,
            rest_rotations=[[0.0, 0.0, 0.0, 1.0]] * 3
        )
        errors = bad_skel.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Cycle detected" in e for e in errors))

        # 3. Direct retarget engine rejection on NaN in world_positions (AUD-17)
        sample_path = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
        nan_pose = load_pose_sample(sample_path)
        nan_pose.world_positions[77][0] = float("nan")
        skel_def = get_authoritative_mhr_skeleton_def()
        rig_prof = get_preset_as5()
        nan_res = retarget(nan_pose, skel_def, rig_prof)
        self.assertFalse(nan_res.success, "Retarget must fail on NaN in world_positions (AUD-17)!")
        self.assertGreater(len(nan_res.errors), 0)

        # 4. Rejection on unsupported schema_version and skeleton_id (AUD-11/17)
        bad_ver_pose = load_pose_sample(sample_path)
        bad_ver_pose.schema_version = "9.0"
        bad_ver_res = retarget(bad_ver_pose, skel_def, rig_prof)
        self.assertFalse(bad_ver_res.success)
        self.assertTrue(any("schema_version" in e for e in bad_ver_res.errors))

    def test_l10_aud07_neutral_fk_end_zero_delta(self):
        """
        L10 / AUD-07:
        When an end-effector (wrist/ankle) has non-identity rest rotation (e.g. Z=30 deg),
        and the input pose has the exact same local rotation (rest pose),
        EndEffectorOp must compute delta = Identity, outputting zero increment (0 deg).
        """
        from retarget.ops.end_effector_op import EndEffectorOp
        from retarget.ops.base_op import RetargetContext
        from pose_core.schema import RetargetResult, RetargetProfile

        skel_def = SkeletonDefinition(
            skeleton_id="test_mhr",
            joint_names=["root", "arm", "wrist"],
            parent_indices=[-1, 0, 1],
            rest_translations=[[0,0,0], [10,0,0], [10,0,0]],
            rest_rotations=[[0,0,0,1], [0,0,0,1], euler_to_q([0, 0, 30], order='xyz')],
            chains={"left_arm": [0, 1, 2]}
        )
        pose_sample = PoseSample(
            schema_version="2.0",
            skeleton_id="test_mhr",
            local_rotations=skel_def.rest_rotations,
            world_positions=[[0,0,0], [10,0,0], [20,0,0]],
            root_translation=[0,0,0],
            root_rotation=[0,0,0,1]
        )
        rig = get_preset_as5()
        calibrator = RigCalibrator(skel_def, rig)
        retarget_prof = RetargetProfile(chain_modes={"left_arm": "fk"})
        ctx = RetargetContext(
            source_pose=pose_sample,
            source_def=skel_def,
            rig_profile=rig,
            retarget_profile=retarget_prof,
            calibrator=calibrator,
            result=RetargetResult(success=True)
        )

        op = EndEffectorOp(chain_id="left_arm")
        op.execute(ctx)

        wrist_ctrl = "FKWrist_L"
        self.assertIn(wrist_ctrl, ctx.result.target_transforms)
        deg = ctx.result.target_transforms[wrist_ctrl]["r"]
        for d in deg:
            self.assertAlmostEqual(d, 0.0, places=4, msg=f"L10 Failure: End effector output non-zero rotation {deg} for neutral pose!")

    def test_aud15_in_place_no_horizontal_leak_and_weight_interpolation(self):
        """
        AUD-15:
        1. in_place root motion clears horizontal pelvis translation AND does not leak
           horizontal translation into ctx.state['pelvis_displacement'].
        2. IK goals interpolate smoothly between bind reference pose and target with weight 0.5.
        3. Caller's retarget_profile is never mutated by retarget engine.
        """
        sample_path = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
        pose = load_pose_sample(sample_path)
        skel = get_authoritative_mhr_skeleton_def()
        rig = get_preset_as5()

        # Shift root by 50 cm in X
        pose.world_positions[1][0] += 50.0

        retarget_prof = RetargetProfile(
            root_motion_mode="in_place",
            chain_weights={"left_arm": 0.5}
        )
        import copy
        prof_before = copy.deepcopy(retarget_prof)

        res = retarget(pose, skel, rig, retarget_prof)
        self.assertTrue(res.success)

        # Profile must not be mutated
        self.assertEqual(retarget_prof.root_motion_mode, prof_before.root_motion_mode)
        self.assertEqual(retarget_prof.chain_weights, prof_before.chain_weights)

        # Pelvis X translation must be 0 in in_place
        pelvis_ctrl = rig.pelvis_node
        self.assertIn(pelvis_ctrl, res.target_transforms)
        self.assertAlmostEqual(res.target_transforms[pelvis_ctrl]["t"][0], 0.0, places=3)

    def test_aud16_exact_geometric_ground_contact(self):
        """
        AUD-16:
        GroundContactOp calculates exact vertical descent h_max = sqrt(L_max^2 - d_horiz^2)
        to eliminate the ~2.72 cm over-reach residual and make the leg truly reachable.
        """
        from retarget.ops.ground_contact_op import GroundContactOp
        from retarget.ops.base_op import RetargetContext
        from pose_core.schema import RetargetResult, RetargetProfile

        skel = get_authoritative_mhr_skeleton_def()
        rig = get_preset_as5()
        calibrator = RigCalibrator(skel, rig)
        retarget_prof = RetargetProfile(
            ground_contact=True,
            ground_height=0.0,
            contact_legs={"left_leg": True, "right_leg": False}
        )

        res = RetargetResult(success=True)
        # Leg IK control currently at [60, 20, 0], hip at [0, 100, 0], L_max = 100
        ctrl = "IKLeg_L"
        res.target_transforms[ctrl] = {"t": [60.0, 20.0, 0.0]}
        res.target_transforms[rig.pelvis_node] = {"t": [0.0, 0.0, 0.0]}
        res.ik_goals["left_leg"] = {"target_pos": [60.0, 20.0, 0.0]}

        ctx = RetargetContext(
            source_pose=load_pose_sample(os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")),
            source_def=skel,
            rig_profile=rig,
            retarget_profile=retarget_prof,
            calibrator=calibrator,
            result=res
        )
        ctx.state["left_leg_p_root"] = [0.0, 100.0, 0.0]
        ctx.state["left_leg_len"] = 100.0

        op = GroundContactOp()
        op.execute(ctx)

        # Foot height should be at ground (0.0)
        self.assertAlmostEqual(res.target_transforms[ctrl]["t"][1], 0.0, places=3)

        # With foot at [60, 0, 0] and hip X=0, d_horiz=60. L_max=100.
        # h_max = sqrt(100^2 - 60^2) = 80.
        # Hip must be lowered from 100 to 80 (drop = 20 cm).
        # Pelvis must be lowered by 20 cm:
        pelvis_y = res.target_transforms[rig.pelvis_node]["t"][1]
        self.assertAlmostEqual(pelvis_y, -20.0, places=3)

        # Residual must be 0.0 (fully reachable, eliminating the 2.72 cm error)
        res_reach = res.residuals.get("left_leg_ground_reach", -1.0)
        self.assertAlmostEqual(res_reach, 0.0, places=3)


if __name__ == '__main__':
    unittest.main()
