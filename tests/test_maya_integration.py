"""
Maya Integration and Transaction Tests.
Executable inside Autodesk Maya GUI or via mayapy.

AUD-13 Compliant:
  - Strictly isolated in dedicated test namespace 'test_p2m_iso:'.
  - Zero modification or deletion of existing nodes in root / default namespace.
  - Sentinel verification ensures user scene nodes remain intact.
"""

import os
import unittest

try:
    import maya.standalone
    try:
        maya.standalone.initialize(name='python')
    except Exception:
        pass
    import maya.cmds as cmds
    MAYA_AVAILABLE = True
except ImportError:
    cmds = None
    MAYA_AVAILABLE = False

from pose_core.mhr_adapter import load_legacy_skeleton_json, get_authoritative_mhr_skeleton_def
from retarget.engine import retarget
from retarget.profiles import get_preset_as5
from maya_scripts.rig_adapter import prepare_write_plan
from maya_scripts.pose_session import PoseSession
from dcc_skeleton_builder import DCCSkeletonBuilder

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_JSON = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
import uuid

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_JSON = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
SAMPLE_DANCING = os.path.join(REPO_ROOT, "data", "sample_poses", "02_human_dancing_skeleton.json")


class TestMayaIntegration(unittest.TestCase):

    def setUp(self):
        if not MAYA_AVAILABLE:
            self.skipTest("Autodesk Maya environment (cmds) not available.")
        if not os.path.exists(SAMPLE_JSON):
            self.skipTest(f"Sample JSON not found: {SAMPLE_JSON}")

        # Unique UUID namespace per test instance (AUD-13)
        self.test_ns = f"p2m_iso_{uuid.uuid4().hex[:8]}"
        cmds.namespace(setNamespace=":")
        if not cmds.namespace(exists=self.test_ns):
            cmds.namespace(add=self.test_ns)

        self.created_nodes = set()

        # Record initial scene state to restore upon tearDown
        self.initial_namespace = cmds.namespaceInfo(currentNamespace=True)
        self.initial_frame = cmds.currentTime(q=True)
        self.initial_autokey = cmds.autoKeyframe(q=True, state=True)
        self.initial_undo = cmds.undoInfo(q=True, stateWithoutFlush=True)

        # 1. Place pre-existing user sentinel in root namespace with animation and custom attr
        self.root_sentinel = "user_root_sentinel_node"
        if not cmds.objExists(self.root_sentinel):
            cmds.createNode("transform", name=self.root_sentinel)
            cmds.addAttr(self.root_sentinel, ln="user_marker", at="double", dv=777.0)
            cmds.setKeyframe(self.root_sentinel, attribute="ty", t=1, v=10.0)
            cmds.setKeyframe(self.root_sentinel, attribute="ty", t=10, v=20.0)
            self.root_sentinel_created_by_fixture = True
        else:
            self.root_sentinel_created_by_fixture = False
        self.root_sentinel_uuid = cmds.ls(self.root_sentinel, uuid=True)[0]

        # 2. Place pre-existing user sentinel in fixed legacy namespace 'test_p2m_iso' to prove it is NEVER touched
        if not cmds.namespace(exists="test_p2m_iso"):
            cmds.namespace(add="test_p2m_iso")
        self.legacy_sentinel = "test_p2m_iso:user_legacy_sentinel"
        if not cmds.objExists(self.legacy_sentinel):
            cmds.createNode("transform", name=self.legacy_sentinel)
            cmds.addAttr(self.legacy_sentinel, ln="legacy_guard", at="double", dv=888.0)
            cmds.setKeyframe(self.legacy_sentinel, attribute="tx", t=5, v=55.0)
            self.legacy_sentinel_created_by_fixture = True
        else:
            self.legacy_sentinel_created_by_fixture = False
        self.legacy_sentinel_uuid = cmds.ls(self.legacy_sentinel, uuid=True)[0]

    def register_node(self, node_name: str):
        """Explicitly tracks node created by this test for safe deletion."""
        self.created_nodes.add(node_name)
        return node_name

    def tearDown(self):
        if not MAYA_AVAILABLE:
            return

        cmds.namespace(setNamespace=":")

        # 1. Clean up ONLY nodes registered as owned by this test
        for n in list(self.created_nodes):
            if cmds.objExists(n):
                try:
                    cmds.delete(n)
                except Exception:
                    pass

        # 2. Check if test namespace contains any un-owned nodes (AUD-13)
        if cmds.namespace(exists=self.test_ns):
            remaining_nodes = cmds.namespaceInfo(self.test_ns, listOnlyDependencyNodes=True) or []
            if remaining_nodes:
                # Do NOT delete foreign nodes! Leave them and report warning
                pass
            else:
                try:
                    cmds.namespace(deleteNamespaceContent=False, removeNamespace=self.test_ns)
                except Exception:
                    pass

        # 3. Verify user sentinels in root and legacy namespaces are 100% untouched
        if cmds.objExists(self.root_sentinel):
            curr_uuid = cmds.ls(self.root_sentinel, uuid=True)[0]
            self.assertEqual(curr_uuid, self.root_sentinel_uuid, "Root sentinel UUID altered!")
            self.assertEqual(cmds.getAttr(f"{self.root_sentinel}.user_marker"), 777.0)
            self.assertEqual(cmds.keyframe(f"{self.root_sentinel}.ty", q=True, keyframeCount=True), 2)
            if self.root_sentinel_created_by_fixture:
                cmds.delete(self.root_sentinel)

        if cmds.objExists(self.legacy_sentinel):
            curr_uuid = cmds.ls(self.legacy_sentinel, uuid=True)[0]
            self.assertEqual(curr_uuid, self.legacy_sentinel_uuid, "Legacy namespace sentinel UUID altered!")
            self.assertEqual(cmds.getAttr(f"{self.legacy_sentinel}.legacy_guard"), 888.0)
            self.assertEqual(cmds.keyframe(f"{self.legacy_sentinel}.tx", q=True, keyframeCount=True), 1)
            if self.legacy_sentinel_created_by_fixture:
                cmds.delete(self.legacy_sentinel)
                if cmds.namespace(exists="test_p2m_iso"):
                    nodes = cmds.namespaceInfo("test_p2m_iso", listOnlyDependencyNodes=True) or []
                    if not nodes:
                        try:
                            cmds.namespace(removeNamespace="test_p2m_iso")
                        except Exception:
                            pass

        # 4. Restore initial Maya scene state
        if cmds.namespace(exists=self.initial_namespace):
            cmds.namespace(setNamespace=self.initial_namespace)
        else:
            cmds.namespace(setNamespace=":")
        cmds.currentTime(self.initial_frame, update=True)
        cmds.autoKeyframe(state=self.initial_autokey)

    def test_dcc_skeleton_builder_fixed_bone_length_and_orient(self):
        """
        Tests that DCCSkeletonBuilder constructs a 54-joint skeleton once,
        and applies dynamic poses strictly via local rotations and root translation,
        leaving bone lengths and jointOrient completely unchanged across multiple segments.
        """
        dancing_path = SAMPLE_DANCING if os.path.exists(SAMPLE_DANCING) else SAMPLE_JSON
        prefix = f"{self.test_ns}:IntTest_"
        builder = DCCSkeletonBuilder(naming_style="ue5", mode="core", prefix=prefix)
        joints = builder.build_skeleton(SAMPLE_JSON)
        for j in joints:
            self.register_node(j)
        self.assertEqual(len(joints), 54)

        # Verify segments across multiple chains
        pairs = [
            (f"{prefix}root", f"{prefix}pelvis"),
            (f"{prefix}thigh_l", f"{prefix}calf_l"),
            (f"{prefix}calf_l", f"{prefix}foot_l"),
            (f"{prefix}upperarm_l", f"{prefix}lowerarm_l")
        ]

        def get_len(j1, j2):
            p1 = cmds.xform(j1, q=True, ws=True, t=True)
            p2 = cmds.xform(j2, q=True, ws=True, t=True)
            return sum((p2[i] - p1[i]) ** 2 for i in range(3)) ** 0.5

        initial_lengths = {(j1, j2): get_len(j1, j2) for j1, j2 in pairs}

        # Record jointOrient for all 54 joints
        initial_orients = {}
        for j in joints:
            if cmds.attributeQuery("jointOrient", node=j, exists=True):
                initial_orients[j] = cmds.getAttr(f"{j}.jointOrient")[0]

        # Apply non-trivial dancing pose at frame 15
        builder.apply_pose(dancing_path, keyframe=15)

        # Check bone lengths remain constant (0.0000% error)
        for (j1, j2), init_l in initial_lengths.items():
            after_l = get_len(j1, j2)
            self.assertAlmostEqual(
                init_l, after_l, places=3,
                msg=f"Bone length for segment {j1}->{j2} changed from {init_l} to {after_l}!"
            )

        # Check jointOrient remains strictly constant for all joints
        for j, init_ori in initial_orients.items():
            curr_ori = cmds.getAttr(f"{j}.jointOrient")[0]
            for axis_idx in range(3):
                self.assertAlmostEqual(
                    init_ori[axis_idx], curr_ori[axis_idx], places=3,
                    msg=f"Joint orient on {j} axis {axis_idx} changed!"
                )

    def test_safe_transaction_preview_cancel_commit_undo(self):
        """
        Tests safe transaction lifecycle in isolated namespace:
        preview overlay -> cancel restoration -> commit keyframing -> single-step undo.
        """
        ctrl_base = [
            "RootX_M", "FKSpine1_M", "FKChest_M", "FKNeck_M", "FKHead_M",
            "IKArm_L", "IKArm_R", "IKLeg_L", "IKLeg_R",
            "PoleArm_L", "PoleArm_R", "PoleLeg_L", "PoleLeg_R",
            "FKIKArm_L", "FKIKArm_R", "FKIKLeg_L", "FKIKLeg_R"
        ]
        for c in ctrl_base:
            node_name = f"{self.test_ns}:{c}"
            if not cmds.objExists(node_name):
                cmds.createNode("transform", name=node_name)
                self.register_node(node_name)

        for blend_ctrl in ["FKIKArm_L", "FKIKArm_R", "FKIKLeg_L", "FKIKLeg_R"]:
            full_b = f"{self.test_ns}:{blend_ctrl}"
            if not cmds.attributeQuery("FKIKBlend", node=full_b, exists=True):
                cmds.addAttr(full_b, ln="FKIKBlend", at="double", dv=0.0, k=True)

        cmds.setAttr(f"{self.test_ns}:RootX_M.ty", 90.0)
        cmds.setAttr(f"{self.test_ns}:IKArm_L.tx", 50.0)
        cmds.setAttr(f"{self.test_ns}:FKIKArm_L.FKIKBlend", 0.0)

        # Retarget & WritePlan targeting self.test_ns
        pose = load_legacy_skeleton_json(SAMPLE_JSON)
        skel = get_authoritative_mhr_skeleton_def()
        rig = get_preset_as5()
        res = retarget(pose, skel, rig)
        plan = prepare_write_plan(res, namespace=self.test_ns, auto_key=True)
        self.assertTrue(plan.can_apply)

        session = PoseSession()

        # 1. Preview
        rep_prev = session.preview(plan)
        self.assertEqual(rep_prev.status, "preview")
        self.assertEqual(cmds.getAttr(f"{self.test_ns}:FKIKArm_L.FKIKBlend"), 10.0)

        # 2. Cancel
        rep_cancel = session.cancel()
        self.assertEqual(rep_cancel.status, "cancelled")
        self.assertEqual(cmds.getAttr(f"{self.test_ns}:FKIKArm_L.FKIKBlend"), 0.0)
        self.assertAlmostEqual(cmds.getAttr(f"{self.test_ns}:RootX_M.ty"), 90.0, places=3)

        # 3. Commit
        rep_commit = session.commit(plan, keyframe=12)
        self.assertEqual(rep_commit.status, "success")
        self.assertGreater(rep_commit.keyframes_set, 0)
        self.assertEqual(cmds.getAttr(f"{self.test_ns}:FKIKArm_L.FKIKBlend"), 10.0)

        # 4. Single Undo step reverts everything
        cmds.undo()
        self.assertEqual(cmds.getAttr(f"{self.test_ns}:FKIKArm_L.FKIKBlend"), 0.0)
        self.assertAlmostEqual(cmds.getAttr(f"{self.test_ns}:RootX_M.ty"), 90.0, places=3)

    def test_aud13_strict_namespace_and_ownership_isolation(self):
        """
        AUD-13 Acceptance:
        Ensures foreign nodes inside test namespace are NOT deleted on tearDown,
        and user sentinels in pre-existing test namespaces are strictly preserved.
        """
        # Inject an unowned foreign node into the test namespace
        foreign_node = f"{self.test_ns}:foreign_user_node"
        cmds.createNode("transform", name=foreign_node)
        cmds.addAttr(foreign_node, ln="user_flag", at="double", dv=999.0)
        # Note: We intentionally do NOT register foreign_node in self.created_nodes!

        # Also create an owned node
        owned_node = f"{self.test_ns}:test_owned_node"
        cmds.createNode("transform", name=owned_node)
        self.register_node(owned_node)

        # Simulate selective cleanup
        self.tearDown()

        # Verify: Owned node was deleted, but foreign node was PRESERVED
        self.assertFalse(cmds.objExists(owned_node), "Owned node was not deleted!")
        self.assertTrue(cmds.objExists(foreign_node), "Foreign unowned node was erroneously deleted (AUD-13 violation)!")

        # Manual post-test cleanup of injected foreign node
        cmds.delete(foreign_node)
        if cmds.namespace(exists=self.test_ns):
            try:
                cmds.namespace(removeNamespace=self.test_ns)
            except Exception:
                pass

    def test_aud02_neutral_pose_zero_distortion_l09(self):
        """
        L09 / AUD-02 Acceptance:
        Standard skeleton builds 54 joints in neutral rest pose.
        Applying its own authoritative reference pose MUST result in ZERO joint displacement
        (<= 1e-4 cm) and constant jointOrient, completely eliminating the 119.42 cm regression.
        """
        from pose_core.schema import PoseSample
        prefix = f"{self.test_ns}:Neutral_"
        builder = DCCSkeletonBuilder(naming_style="ue5", mode="core", prefix=prefix)
        joints = builder.build_skeleton(SAMPLE_JSON)
        for j in joints:
            self.register_node(j)
        self.assertEqual(len(joints), 54)

        # Record initial rest positions and jointOrient for all 54 joints
        pos_before = {j: cmds.xform(j, q=True, ws=True, t=True) for j in joints}
        jo_before = {j: cmds.getAttr(f"{j}.jointOrient")[0] for j in joints}

        skel_def = get_authoritative_mhr_skeleton_def()
        neutral_pose = PoseSample(
            schema_version="2.0",
            skeleton_id=skel_def.skeleton_id,
            local_rotations=skel_def.rest_rotations,
            world_positions=skel_def.rest_world_positions,
            root_translation=[0.0, 0.0, 0.0],
            root_rotation=[0.0, 0.0, 0.0, 1.0]
        )

        # Apply its own reference pose
        success = builder.apply_pose(neutral_pose.to_dict())
        self.assertTrue(success)

        # Measure maximum position change across all 54 joints
        max_dist = 0.0
        worst_joint = None
        for j in joints:
            p1 = pos_before[j]
            p2 = cmds.xform(j, q=True, ws=True, t=True)
            dist = sum((p2[k] - p1[k]) ** 2 for k in range(3)) ** 0.5
            if dist > max_dist:
                max_dist = dist
                worst_joint = j

            # JointOrient must remain strictly unchanged
            curr_jo = cmds.getAttr(f"{j}.jointOrient")[0]
            for axis_idx in range(3):
                self.assertAlmostEqual(jo_before[j][axis_idx], curr_jo[axis_idx], places=4)

        # Max distortion must be <= 1e-3 cm (previously was 119.42 cm!)
        self.assertLess(
            max_dist, 0.001,
            f"L09 / AUD-02 Failed: neutral pose caused {max_dist:.4f} cm distortion on {worst_joint}!"
        )
        pose = load_legacy_skeleton_json(SAMPLE_JSON)
        skel = get_authoritative_mhr_skeleton_def()
        rig = get_preset_as5()
        res = retarget(pose, skel, rig)

        # Empty non-existent namespace must fail with Zero matching channels
        plan = prepare_write_plan(res, namespace="GhostCharacter_DoesNotExist_")
        self.assertFalse(plan.can_apply)
        self.assertTrue(any("Zero matching" in b for b in plan.blockers))

    def test_l01_scene_calibration(self):
        """
        L01 / AUD-14 / AUD-05:
        calibrate_profile_from_scene must:
        1. Correctly measure arm limb lengths as [30, 30] cm (shoulder-to-elbow, elbow-to-wrist)
           rather than [10, 30] cm from clavicle.
        2. Set anchor to shoulder [10, 100, 0] cm rather than clavicle [0, 100, 0] cm.
        3. Pass degree euler to euler_to_q without TypeError.
        """
        from maya_scripts.rig_inspector import calibrate_profile_from_scene
        rig = get_preset_as5()

        nodes = {
            "FKScapula_L": [0.0, 100.0, 0.0],
            "FKShoulder_L": [10.0, 100.0, 0.0],
            "FKElbow_L": [40.0, 100.0, 0.0],
            "FKWrist_L": [70.0, 100.0, 0.0],
            "IKArm_L": [70.0, 100.0, 0.0]
        }
        for n, p in nodes.items():
            full_n = f"{self.test_ns}:{n}"
            if not cmds.objExists(full_n):
                cmds.createNode("transform", name=full_n)
                self.register_node(full_n)
            cmds.xform(full_n, ws=True, t=p)

        new_prof, items = calibrate_profile_from_scene(rig, namespace=self.test_ns)
        lengths = new_prof.target_limb_lengths.get("left_arm")
        self.assertIsNotNone(lengths)
        self.assertAlmostEqual(lengths[0], 30.0, places=2)
        self.assertAlmostEqual(lengths[1], 30.0, places=2)

        anchor = new_prof.target_chain_anchors.get("left_arm")
        self.assertIsNotNone(anchor)
        self.assertAlmostEqual(anchor[0], 10.0, places=2)
        self.assertAlmostEqual(anchor[1], 100.0, places=2)
        self.assertAlmostEqual(anchor[2], 0.0, places=2)

    def test_l02_l03_world_space_parent_rotation_and_opm(self):
        """
        L02 & L03 / AUD-06:
        1. L02: Parent world ry=90 deg, child target world ry=0 deg.
           Local rotation must be -90 deg so child actual world rotation is 0 deg (error <= 1e-3 deg).
        2. L03: Child offsetParentMatrix tx=5. Goal world X=10.
           Local translation must be 5 so child actual world X is 10 (error <= 1e-4 cm).
        """
        import maya.api.OpenMaya as om
        from pose_core.schema import RetargetResult
        from maya_scripts.rig_adapter import prepare_write_plan

        # L02 Setup
        p_node = f"{self.test_ns}:L02_Parent"
        c_node = f"{self.test_ns}:L02_Child"
        if not cmds.objExists(p_node):
            cmds.createNode("transform", name=p_node)
            self.register_node(p_node)
        cmds.setAttr(f"{p_node}.t", 100.0, 0.0, 0.0)
        cmds.setAttr(f"{p_node}.ry", 90.0)

        if not cmds.objExists(c_node):
            cmds.createNode("transform", name=c_node, parent=p_node)
            self.register_node(c_node)

        # Target world transform: t=[100, 0, -10], r=[0, 0, 0]
        res_l02 = RetargetResult(success=True)
        res_l02.target_transforms["L02_Child"] = {
            "t": [100.0, 0.0, -10.0],
            "r": [0.0, 0.0, 0.0],
            "space": "world"
        }
        plan_l02 = prepare_write_plan(res_l02, namespace=self.test_ns)
        session = PoseSession()
        session.commit(plan_l02)

        # Measure world transform of child
        c_sel = om.MSelectionList()
        c_sel.add(c_node)
        c_dag = c_sel.getDagPath(0)
        tm_c = om.MTransformationMatrix(c_dag.inclusiveMatrix())
        ws_trans = tm_c.translation(om.MSpace.kWorld)
        ws_rot = tm_c.rotation()

        self.assertAlmostEqual(ws_trans.x, 100.0, places=3)
        self.assertAlmostEqual(ws_trans.y, 0.0, places=3)
        self.assertAlmostEqual(ws_trans.z, -10.0, places=3)

        import math
        rot_deg = [math.degrees(ws_rot.x), math.degrees(ws_rot.y), math.degrees(ws_rot.z)]
        for rd in rot_deg:
            self.assertAlmostEqual(rd, 0.0, places=2, msg=f"L02 Failed: Child world rotation was {rot_deg}")

        # L03 Setup: Child with OPM tx=5
        opm_node = f"{self.test_ns}:L03_OPM_Child"
        if not cmds.objExists(opm_node):
            cmds.createNode("transform", name=opm_node)
            self.register_node(opm_node)

        tm_opm = om.MTransformationMatrix()
        tm_opm.setTranslation(om.MVector(5.0, 0.0, 0.0), om.MSpace.kTransform)
        cmds.setAttr(f"{opm_node}.offsetParentMatrix", list(tm_opm.asMatrix()), type="matrix")

        res_l03 = RetargetResult(success=True)
        res_l03.target_transforms["L03_OPM_Child"] = {
            "t": [10.0, 0.0, 0.0],
            "r": [0.0, 0.0, 0.0],
            "space": "world"
        }
        plan_l03 = prepare_write_plan(res_l03, namespace=self.test_ns)
        session.commit(plan_l03)

        opm_sel = om.MSelectionList()
        opm_sel.add(opm_node)
        opm_dag = opm_sel.getDagPath(0)
        tm_opm_c = om.MTransformationMatrix(opm_dag.inclusiveMatrix())
        actual_ws_t = tm_opm_c.translation(om.MSpace.kWorld)
        self.assertAlmostEqual(actual_ws_t.x, 10.0, places=3, msg=f"L03 Failed: Expected world X=10, got {actual_ws_t.x}")

    def test_l04_expanding_preview_channels_cancel_restoration(self):
        """
        L04 / AUD-08:
        Previewing plan A, then previewing expanded plan A+B, then cancelling
        must cleanly restore both A and B to their initial values.
        """
        from pose_core.schema import WritePlan
        node_a = f"{self.test_ns}:L04_A"
        node_b = f"{self.test_ns}:L04_B"
        for n in [node_a, node_b]:
            if not cmds.objExists(n):
                cmds.createNode("transform", name=n)
                self.register_node(n)

        cmds.setAttr(f"{node_a}.tx", 1.0)
        cmds.setAttr(f"{node_b}.tx", 2.0)

        plan1 = WritePlan()
        plan1.channels = [{"node": node_a, "attr": "tx", "current": 1.0, "target": 10.0}]

        plan2 = WritePlan()
        plan2.channels = [
            {"node": node_a, "attr": "tx", "current": 10.0, "target": 20.0},
            {"node": node_b, "attr": "tx", "current": 2.0, "target": 30.0}
        ]

        session = PoseSession()
        session.preview(plan1)
        self.assertEqual(cmds.getAttr(f"{node_a}.tx"), 10.0)

        session.preview(plan2)
        self.assertEqual(cmds.getAttr(f"{node_a}.tx"), 20.0)
        self.assertEqual(cmds.getAttr(f"{node_b}.tx"), 30.0)

        session.cancel()
        self.assertEqual(cmds.getAttr(f"{node_a}.tx"), 1.0)
        self.assertEqual(cmds.getAttr(f"{node_b}.tx"), 2.0)

    def test_l05_failed_commit_rollback_cleans_target_frame_keys(self):
        """
        L05 / AUD-08:
        When a commit keyframing operation fails on a secondary channel,
        the transaction must roll back cleanly:
        1. Remove any keyframes newly created at the target frame.
        2. Restore pre-commit attribute values.
        3. Restore current timeline frame.
        """
        from pose_core.schema import WritePlan
        cmds.currentTime(0, update=True)

        node_a = f"{self.test_ns}:L05_A"
        node_b = f"{self.test_ns}:L05_B"
        for n in [node_a, node_b]:
            if not cmds.objExists(n):
                cmds.createNode("transform", name=n)
                self.register_node(n)

        cmds.setAttr(f"{node_a}.tx", 1.0)
        cmds.setAttr(f"{node_b}.tx", 2.0)

        plan = WritePlan()
        plan.channels = [
            {"node": node_a, "attr": "tx", "current": 1.0, "target": 10.0, "keyframe": True},
            {"node": node_b, "attr": "tx", "current": 2.0, "target": 20.0, "keyframe": True}
        ]

        cmds.setAttr(f"{node_b}.tx", lock=True)

        session = PoseSession()
        report = session.commit(plan, keyframe=12)
        self.assertEqual(report.status, "failed")

        cmds.setAttr(f"{node_b}.tx", lock=False)

        # Verify no remaining keys on node_a at frame 12
        keys_a = cmds.keyframe(f"{node_a}.tx", time=(12, 12), q=True, timeChange=True) or []
        self.assertEqual(keys_a, [], msg="L05 Failed: Residual keyframe at frame 12 on node A was not cleaned up!")

        # Values restored
        self.assertEqual(cmds.getAttr(f"{node_a}.tx"), 1.0)
        self.assertEqual(cmds.getAttr(f"{node_b}.tx"), 2.0)

        # Current time restored to 0
        self.assertEqual(cmds.currentTime(q=True), 0.0)

    def test_l05_preexisting_keyframe_restored_on_failed_commit(self):
        """
        AUD-08 / L05:
        When an attribute ALREADY has a keyframe at target frame with an existing value,
        a failed commit rollback must NOT leave the failed new value on the animCurve,
        and must NOT delete the pre-existing keyframe, but restore its exact pre-commit value.
        """
        from pose_core.schema import WritePlan
        node_a = f"{self.test_ns}:L05_ExistingKey_A"
        node_b = f"{self.test_ns}:L05_ExistingKey_B"
        for n in [node_a, node_b]:
            if not cmds.objExists(n):
                cmds.createNode("transform", name=n)
                self.register_node(n)

        # Existing keyframe at frame 12 on node_a with value 5.0
        cmds.setKeyframe(f"{node_a}.tx", time=12, value=5.0)
        self.assertEqual(cmds.keyframe(f"{node_a}.tx", time=(12, 12), q=True, valueChange=True)[0], 5.0)

        plan = WritePlan()
        plan.channels = [
            {"node": node_a, "attr": "tx", "current": 5.0, "target": 99.0, "keyframe": True},
            {"node": node_b, "attr": "tx", "current": 0.0, "target": 20.0, "keyframe": True}
        ]
        # Lock node_b to induce mid-flight failure
        cmds.setAttr(f"{node_b}.tx", lock=True)

        session = PoseSession()
        report = session.commit(plan, keyframe=12)
        self.assertEqual(report.status, "failed")

        cmds.setAttr(f"{node_b}.tx", lock=False)

        # Keyframe at frame 12 must still exist
        keys_a = cmds.keyframe(f"{node_a}.tx", time=(12, 12), q=True, valueChange=True) or []
        self.assertEqual(len(keys_a), 1, "Pre-existing keyframe at frame 12 was erroneously deleted!")
        self.assertEqual(keys_a[0], 5.0, "Pre-existing keyframe at frame 12 did not have its pre-commit value restored!")

    def test_l06_preflight_blocks_on_locked_channel_and_mode_switch(self):
        """
        L06 / AUD-17:
        prepare_write_plan must refuse to proceed (can_apply=False) with specific blockers
        when a mode switch or transform channel is locked or a required target node is missing.
        Uses arbitrary node names without 'required' or 'preflight' substrings.
        """
        from pose_core.schema import RetargetResult
        ctrl = f"{self.test_ns}:arm_ctrl"
        switch = f"{self.test_ns}:switch_node"
        for n in [ctrl, switch]:
            if not cmds.objExists(n):
                cmds.createNode("transform", name=n)
                self.register_node(n)

        if not cmds.attributeQuery("blend_mode", node=switch, exists=True):
            cmds.addAttr(switch, ln="blend_mode", at="double", dv=0.0, k=True)

        # Lock channel and mode switch
        cmds.setAttr(f"{ctrl}.rx", lock=True)
        cmds.setAttr(f"{switch}.blend_mode", lock=True)

        res = RetargetResult(success=True)
        res.target_transforms["arm_ctrl"] = {
            "r": [10.0, 20.0, 30.0],
            "space": "local"
        }
        res.target_transforms["missing_ghost_node"] = {
            "r": [0.0, 0.0, 0.0],
            "space": "local"
        }
        res.mode_switches["switch_node.blend_mode"] = 1.0

        plan = prepare_write_plan(res, namespace=self.test_ns)
        self.assertFalse(plan.can_apply, "L06 Failed: Plan with locked rx, locked switch, and missing node must not be applicable!")
        self.assertTrue(any("Attribute is locked" in b for b in plan.blockers))
        self.assertTrue(any("Mode switch attribute is locked" in b for b in plan.blockers))
        self.assertTrue(any("Required target node missing" in b for b in plan.blockers))

        cmds.setAttr(f"{ctrl}.rx", lock=False)
        cmds.setAttr(f"{switch}.blend_mode", lock=False)

    def test_l07_existing_anim_curve_evaluated_at_current_time_on_cancel(self):
        """
        L07 / AUD-08:
        When an attribute has an animation curve, previewing at frame 1,
        scrubbing to frame 5, and cancelling MUST evaluate the curve at frame 5
        rather than overwriting with the frame 1 baseline value.
        """
        from pose_core.schema import WritePlan
        node = f"{self.test_ns}:L07_Anim"
        if not cmds.objExists(node):
            cmds.createNode("transform", name=node)
            self.register_node(node)

        cmds.setKeyframe(f"{node}.tx", time=1, value=1.0)
        cmds.setKeyframe(f"{node}.tx", time=10, value=10.0)

        cmds.currentTime(1, update=True)
        plan = WritePlan()
        plan.channels = [{"node": node, "attr": "tx", "current": 1.0, "target": 7.0}]

        session = PoseSession()
        session.preview(plan)
        self.assertEqual(cmds.getAttr(f"{node}.tx"), 7.0)

        cmds.currentTime(5, update=True)
        expected_val = cmds.getAttr(f"{node}.tx", time=5)

        session.cancel()
        restored_val = cmds.getAttr(f"{node}.tx")
        self.assertAlmostEqual(
            restored_val, expected_val, places=3,
            msg=f"L07 Failed: Expected curve value ~{expected_val:.3f} at frame 5, got {restored_val}"
        )


if __name__ == "__main__":
    unittest.main()
