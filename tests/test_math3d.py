"""
Unit tests for pose_core.math3d
"""

import math
import unittest
from pose_core.math3d import (
    v_add, v_sub, v_scale, v_dot, v_cross, v_length, v_norm, v_dist,
    q_identity, q_norm, q_normalize, q_inverse, q_multiply, q_rotate_vector,
    q_from_axis_angle, q_from_two_vectors, q_slerp, q_angle_between,
    q_to_mat3, mat3_to_q, euler_to_q, q_to_euler_deg,
    cam_pos_to_maya, maya_pos_to_cam, cam_rot_to_maya_rot,
    fk_reconstruct
)


class TestMath3D(unittest.TestCase):

    def test_vector_ops(self):
        v1 = [1.0, 2.0, 3.0]
        v2 = [4.0, 5.0, 6.0]
        self.assertEqual(v_add(v1, v2), [5.0, 7.0, 9.0])
        self.assertEqual(v_sub(v2, v1), [3.0, 3.0, 3.0])
        self.assertEqual(v_scale(v1, 2.0), [2.0, 4.0, 6.0])
        self.assertAlmostEqual(v_dot(v1, v2), 32.0)
        self.assertEqual(v_cross([1, 0, 0], [0, 1, 0]), [0, 0, 1])
        self.assertAlmostEqual(v_length([3.0, 4.0, 0.0]), 5.0)
        nv = v_norm([0.0, 10.0, 0.0])
        self.assertAlmostEqual(nv[1], 1.0)
        self.assertAlmostEqual(v_dist([0, 0, 0], [1, 1, 1]), math.sqrt(3))

    def test_quaternion_ops(self):
        qi = q_identity()
        self.assertEqual(qi, [0.0, 0.0, 0.0, 1.0])
        self.assertAlmostEqual(q_norm(qi), 1.0)

        # 90 deg rotation around Y
        q_y90 = q_from_axis_angle([0.0, 1.0, 0.0], math.radians(90.0))
        # Rotate [1, 0, 0] by 90 deg around Y -> should be [0, 0, -1] in right-handed system
        v_rot = q_rotate_vector(q_y90, [1.0, 0.0, 0.0])
        self.assertAlmostEqual(v_rot[0], 0.0, places=5)
        self.assertAlmostEqual(v_rot[1], 0.0, places=5)
        self.assertAlmostEqual(v_rot[2], -1.0, places=5)

        # Inverse
        q_inv = q_inverse(q_y90)
        v_back = q_rotate_vector(q_inv, v_rot)
        self.assertAlmostEqual(v_back[0], 1.0, places=5)
        self.assertAlmostEqual(v_back[1], 0.0, places=5)
        self.assertAlmostEqual(v_back[2], 0.0, places=5)

    def test_shortest_arc(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        q = q_from_two_vectors(v1, v2)
        v_out = q_rotate_vector(q, v1)
        self.assertAlmostEqual(v_out[0], 0.0, places=5)
        self.assertAlmostEqual(v_out[1], 1.0, places=5)
        self.assertAlmostEqual(v_out[2], 0.0, places=5)

        # Anti-parallel
        v_opp = [-1.0, 0.0, 0.0]
        q_opp = q_from_two_vectors(v1, v_opp)
        v_opp_out = q_rotate_vector(q_opp, v1)
        self.assertAlmostEqual(v_opp_out[0], -1.0, places=5)
        self.assertAlmostEqual(v_opp_out[1], 0.0, places=5)

    def test_slerp(self):
        q1 = q_identity()
        q2 = q_from_axis_angle([0, 1, 0], math.radians(90))
        q_mid = q_slerp(q1, q2, 0.5)
        ang = q_angle_between(q1, q_mid)
        self.assertAlmostEqual(math.degrees(ang), 45.0, places=4)

    def test_mat3_and_euler_roundtrip(self):
        q_orig = q_normalize([0.1, 0.2, 0.3, 0.9])
        m = q_to_mat3(q_orig)
        q_recon = mat3_to_q(m)
        self.assertAlmostEqual(q_angle_between(q_orig, q_recon), 0.0, places=5)

        euler = [20.0, -35.0, 50.0]
        q_e = euler_to_q(euler, 'xyz')
        euler_recon = q_to_euler_deg(q_e, 'xyz')
        self.assertAlmostEqual(euler[0], euler_recon[0], places=3)
        self.assertAlmostEqual(euler[1], euler_recon[1], places=3)
        self.assertAlmostEqual(euler[2], euler_recon[2], places=3)

    def test_coordinate_transforms(self):
        # Camera coords [1.0 m, 2.0 m, 3.0 m] (X-right, Y-down, Z-forward)
        # Maya coords [100.0 cm, -200.0 cm, -300.0 cm] (X-right, Y-up, Z-depth)
        pos_cam = [1.0, 2.0, 3.0]
        pos_maya = cam_pos_to_maya(pos_cam)
        self.assertEqual(pos_maya, [100.0, -200.0, -300.0])
        pos_back = maya_pos_to_cam(pos_maya)
        self.assertAlmostEqual(pos_back[0], 1.0)
        self.assertAlmostEqual(pos_back[1], 2.0)
        self.assertAlmostEqual(pos_back[2], 3.0)

        # Rotation basis equivalence: R_maya = P @ R_cam @ P
        # Rotate vector in cam frame: v_cam_rot = R_cam @ v_cam
        # In maya frame: v_maya_rot = R_maya @ v_maya
        q_cam = q_from_axis_angle([0, 1, 0], math.radians(45.0))
        q_maya = cam_rot_to_maya_rot(q_cam)
        v_cam = [1.0, 0.5, -0.8]
        v_maya = cam_pos_to_maya(v_cam)
        v_cam_rot = q_rotate_vector(q_cam, v_cam)
        v_maya_rot = q_rotate_vector(q_maya, v_maya)
        expected_maya = cam_pos_to_maya(v_cam_rot)
        self.assertAlmostEqual(v_maya_rot[0], expected_maya[0], places=4)
        self.assertAlmostEqual(v_maya_rot[1], expected_maya[1], places=4)
        self.assertAlmostEqual(v_maya_rot[2], expected_maya[2], places=4)

    def test_forward_kinematics(self):
        # 3-bone chain along Y
        parents = [-1, 0, 1]
        offsets = [[0, 0, 0], [0, 50, 0], [0, 50, 0]]
        rotations = [q_identity(), q_identity(), q_identity()]
        w_pos, w_rot = fk_reconstruct(parents, offsets, rotations)
        self.assertEqual(w_pos[0], [0, 0, 0])
        self.assertEqual(w_pos[1], [0, 50, 0])
        self.assertEqual(w_pos[2], [0, 100, 0])


if __name__ == '__main__':
    unittest.main()
