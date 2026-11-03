"""
pose_core.math3d
================
Clean, deterministic 3D mathematics module for Pose2maya.
Zero external heavy dependencies (uses Python standard library and optional numpy).
Follows standard right-handed convention:
  - Units: centimeters (cm)
  - Up axis: +Y
  - Character Forward axis: +Z
  - Quaternion format: [x, y, z, w] with w as scalar part.
"""

import math
from typing import List, Tuple, Sequence, Optional, Union

# Type aliases
Vec3 = List[float]
Quat = List[float]
Mat3 = List[List[float]]


# -----------------------------------------------------------------------------
# 1. Vector Operations
# -----------------------------------------------------------------------------

def v_create(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Vec3:
    return [float(x), float(y), float(z)]


def v_add(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def v_sub(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def v_scale(v: Sequence[float], s: float) -> Vec3:
    return [v[0] * s, v[1] * s, v[2] * s]


def v_dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]
    ]


def v_length_sq(v: Sequence[float]) -> float:
    return v[0] * v[0] + v[1] * v[1] + v[2] * v[2]


def v_length(v: Sequence[float]) -> float:
    return math.sqrt(v_length_sq(v))


def v_norm(v: Sequence[float], eps: float = 1e-8) -> Vec3:
    l = v_length(v)
    if l < eps:
        return [0.0, 0.0, 0.0]
    inv = 1.0 / l
    return [v[0] * inv, v[1] * inv, v[2] * inv]


def v_dist(a: Sequence[float], b: Sequence[float]) -> float:
    return v_length(v_sub(a, b))


def v_lerp(a: Sequence[float], b: Sequence[float], t: float) -> Vec3:
    return [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])]


def v_angle_between(a: Sequence[float], b: Sequence[float]) -> float:
    na = v_norm(a)
    nb = v_norm(b)
    d = max(-1.0, min(1.0, v_dot(na, nb)))
    return math.acos(d)


def v_project_to_plane(v: Sequence[float], plane_normal: Sequence[float]) -> Vec3:
    pn = v_norm(plane_normal)
    d = v_dot(v, pn)
    return [v[0] - d * pn[0], v[1] - d * pn[1], v[2] - d * pn[2]]


# -----------------------------------------------------------------------------
# 2. Quaternion Operations ([x, y, z, w])
# -----------------------------------------------------------------------------

def q_identity() -> Quat:
    return [0.0, 0.0, 0.0, 1.0]


def q_norm_sq(q: Sequence[float]) -> float:
    return q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]


def q_norm(q: Sequence[float]) -> float:
    return math.sqrt(q_norm_sq(q))


def q_normalize(q: Sequence[float], eps: float = 1e-8) -> Quat:
    l = q_norm(q)
    if l < eps:
        return [0.0, 0.0, 0.0, 1.0]
    inv = 1.0 / l
    return [q[0] * inv, q[1] * inv, q[2] * inv, q[3] * inv]


def q_inverse(q: Sequence[float]) -> Quat:
    l2 = q_norm_sq(q)
    if l2 < 1e-12:
        return [0.0, 0.0, 0.0, 1.0]
    inv = 1.0 / l2
    return [-q[0] * inv, -q[1] * inv, -q[2] * inv, q[3] * inv]


def q_multiply(q1: Sequence[float], q2: Sequence[float]) -> Quat:
    """Hamilton product q = q1 * q2"""
    x1, y1, z1, w1 = q1[0], q1[1], q1[2], q1[3]
    x2, y2, z2, w2 = q2[0], q2[1], q2[2], q2[3]
    return [
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    ]


def q_rotate_vector(q: Sequence[float], v: Sequence[float]) -> Vec3:
    """Rotate 3D vector v by unit quaternion q (v' = q * v * q^-1)"""
    x, y, z, w = q[0], q[1], q[2], q[3]
    vx, vy, vz = v[0], v[1], v[2]

    # t = 2 * cross(q.xyz, v)
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)

    # v' = v + w * t + cross(q.xyz, t)
    return [
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx)
    ]


def q_from_axis_angle(axis: Sequence[float], angle_rad: float) -> Quat:
    n_axis = v_norm(axis)
    half = angle_rad * 0.5
    s = math.sin(half)
    c = math.cos(half)
    return [n_axis[0] * s, n_axis[1] * s, n_axis[2] * s, c]


def q_to_axis_angle(q: Sequence[float]) -> Tuple[Vec3, float]:
    qn = q_normalize(q)
    w = max(-1.0, min(1.0, qn[3]))
    angle = 2.0 * math.acos(w)
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-6:
        return ([1.0, 0.0, 0.0], 0.0)
    inv = 1.0 / s
    return ([qn[0] * inv, qn[1] * inv, qn[2] * inv], angle)


def q_from_two_vectors(v_from: Sequence[float], v_to: Sequence[float]) -> Quat:
    """Shortest arc rotation quaternion aligning v_from to v_to."""
    u1 = v_norm(v_from)
    u2 = v_norm(v_to)
    dot = v_dot(u1, u2)

    if dot > 0.999999:
        return [0.0, 0.0, 0.0, 1.0]

    if dot < -0.999999:
        # Anti-parallel vectors: rotate 180 deg around any perpendicular axis
        ortho = v_cross(u1, [1.0, 0.0, 0.0])
        if v_length_sq(ortho) < 0.01:
            ortho = v_cross(u1, [0.0, 1.0, 0.0])
        ortho = v_norm(ortho)
        return [ortho[0], ortho[1], ortho[2], 0.0]

    # Half-angle quaternion formula
    cross = v_cross(u1, u2)
    w = math.sqrt(2.0 * (1.0 + dot))
    inv_w = 1.0 / w
    return q_normalize([cross[0] * inv_w, cross[1] * inv_w, cross[2] * inv_w, w * 0.5])


def q_dot(q1: Sequence[float], q2: Sequence[float]) -> float:
    """4D quaternion dot product."""
    return sum(float(q1[i]) * float(q2[i]) for i in range(4))


def q_slerp(q1: Sequence[float], q2: Sequence[float], t: float) -> Quat:
    qn1 = q_normalize(q1)
    qn2 = q_normalize(q2)
    dot = q_dot(qn1, qn2)

    if dot < 0.0:
        qn2 = [-qn2[0], -qn2[1], -qn2[2], -qn2[3]]
        dot = -dot

    if dot > 0.9995:
        # Linear interpolation for very close quaternions
        res = [qn1[i] + t * (qn2[i] - qn1[i]) for i in range(4)]
        return q_normalize(res)

    dot = max(-1.0, min(1.0, dot))
    theta_0 = math.acos(dot)
    sin_theta_0 = math.sin(theta_0)
    if sin_theta_0 < 1e-6:
        return q_normalize(qn1)

    theta = theta_0 * t
    s1 = math.sin((1.0 - t) * theta_0) / sin_theta_0
    s2 = math.sin(theta) / sin_theta_0

    res = [qn1[i] * s1 + qn2[i] * s2 for i in range(4)]
    return q_normalize(res)


def q_angle_between(q1: Sequence[float], q2: Sequence[float]) -> float:
    """Relative rotation angle in radians between q1 and q2."""
    diff = q_multiply(q_inverse(q1), q2)
    diff = q_normalize(diff)
    w = max(-1.0, min(1.0, diff[3]))
    return 2.0 * math.acos(abs(w))


# -----------------------------------------------------------------------------
# 3. Matrix & Euler Transformations
# -----------------------------------------------------------------------------

def q_to_mat3(q: Sequence[float]) -> Mat3:
    """Converts quaternion [x, y, z, w] to 3x3 rotation matrix (row-major)."""
    qn = q_normalize(q)
    x, y, z, w = qn[0], qn[1], qn[2], qn[3]
    x2 = x + x; y2 = y + y; z2 = z + z
    xx = x * x2; xy = x * y2; xz = x * z2
    yy = y * y2; yz = y * z2; zz = z * z2
    wx = w * x2; wy = w * y2; wz = w * z2

    return [
        [1.0 - (yy + zz), xy - wz, xz + wy],
        [xy + wz, 1.0 - (xx + zz), yz - wx],
        [xz - wy, yz + wx, 1.0 - (xx + yy)]
    ]


def mat3_to_q(m: Sequence[Sequence[float]]) -> Quat:
    """Shepperd's algorithm for converting 3x3 rotation matrix to quaternion."""
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        w = 0.25 * s
        x = (m[2][1] - m[1][2]) / s
        y = (m[0][2] - m[2][0]) / s
        z = (m[1][0] - m[0][1]) / s
    elif (m[0][0] > m[1][1]) and (m[0][0] > m[2][2]):
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0
        w = (m[2][1] - m[1][2]) / s
        x = 0.25 * s
        y = (m[0][1] + m[1][0]) / s
        z = (m[0][2] + m[2][0]) / s
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0
        w = (m[0][2] - m[2][0]) / s
        x = (m[0][1] + m[1][0]) / s
        y = 0.25 * s
        z = (m[1][2] + m[2][1]) / s
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0
        w = (m[1][0] - m[0][1]) / s
        x = (m[0][2] + m[2][0]) / s
        y = (m[1][2] + m[2][1]) / s
        z = 0.25 * s

    return q_normalize([x, y, z, w])


def mat3_multiply(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> Mat3:
    res = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    for i in range(3):
        for j in range(3):
            res[i][j] = a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j]
    return res


def mat3_transpose(m: Sequence[Sequence[float]]) -> Mat3:
    return [
        [m[0][0], m[1][0], m[2][0]],
        [m[0][1], m[1][1], m[2][1]],
        [m[0][2], m[1][2], m[2][2]]
    ]


def euler_to_q(euler_deg: Sequence[float], order: str = 'xyz') -> Quat:
    """Convert Euler angles (in degrees) to quaternion with given rotation order."""
    rx = math.radians(euler_deg[0])
    ry = math.radians(euler_deg[1])
    rz = math.radians(euler_deg[2])

    qx = q_from_axis_angle([1.0, 0.0, 0.0], rx)
    qy = q_from_axis_angle([0.0, 1.0, 0.0], ry)
    qz = q_from_axis_angle([0.0, 0.0, 1.0], rz)

    order_lower = order.lower()
    if order_lower == 'xyz':
        return q_multiply(qz, q_multiply(qy, qx))
    elif order_lower == 'yzx':
        return q_multiply(qx, q_multiply(qz, qy))
    elif order_lower == 'zxy':
        return q_multiply(qy, q_multiply(qx, qz))
    elif order_lower == 'xzy':
        return q_multiply(qy, q_multiply(qz, qx))
    elif order_lower == 'yxz':
        return q_multiply(qz, q_multiply(qx, qy))
    elif order_lower == 'zyx':
        return q_multiply(qx, q_multiply(qy, qz))
    else:
        raise ValueError(f"Unsupported rotation order '{order}'. Supported orders: xyz, yzx, zxy, xzy, yxz, zyx")


def q_to_euler_deg(q: Sequence[float], order: str = 'xyz') -> Vec3:
    """Convert quaternion to Euler angles in degrees for all 6 standard Maya rotation orders."""
    m = q_to_mat3(q)
    order_lower = order.lower()

    def clamp(v: float) -> float:
        return max(-1.0, min(1.0, v))

    if order_lower == 'xyz':
        # R = Rz * Ry * Rx
        y = math.asin(clamp(-m[2][0]))
        if abs(math.cos(y)) > 1e-6:
            x = math.atan2(m[2][1], m[2][2])
            z = math.atan2(m[1][0], m[0][0])
        else:
            z = 0.0
            x = math.atan2(-m[1][2], m[1][1])
    elif order_lower == 'yzx':
        # R = Rx * Rz * Ry
        z = math.asin(clamp(-m[0][1]))
        if abs(math.cos(z)) > 1e-6:
            x = math.atan2(m[2][1], m[1][1])
            y = math.atan2(m[0][2], m[0][0])
        else:
            x = 0.0
            y = math.atan2(-m[2][0], m[2][2])
    elif order_lower == 'zxy':
        # R = Ry * Rx * Rz
        x = math.asin(clamp(-m[1][2]))
        if abs(math.cos(x)) > 1e-6:
            y = math.atan2(m[0][2], m[2][2])
            z = math.atan2(m[1][0], m[1][1])
        else:
            y = 0.0
            z = math.atan2(-m[0][1], m[0][0])
    elif order_lower == 'xzy':
        # R = Ry * Rz * Rx
        z = math.asin(clamp(m[1][0]))
        if abs(math.cos(z)) > 1e-6:
            x = math.atan2(-m[1][2], m[1][1])
            y = math.atan2(-m[2][0], m[0][0])
        else:
            y = 0.0
            x = math.atan2(m[2][1], m[2][2])
    elif order_lower == 'yxz':
        # R = Rz * Rx * Ry
        x = math.asin(clamp(m[2][1]))
        if abs(math.cos(x)) > 1e-6:
            y = math.atan2(-m[2][0], m[2][2])
            z = math.atan2(-m[0][1], m[1][1])
        else:
            z = 0.0
            y = math.atan2(m[0][2], m[0][0])
    elif order_lower == 'zyx':
        # R = Rx * Ry * Rz
        y = math.asin(clamp(m[0][2]))
        if abs(math.cos(y)) > 1e-6:
            x = math.atan2(-m[1][2], m[2][2])
            z = math.atan2(-m[0][1], m[0][0])
        else:
            x = 0.0
            z = math.atan2(m[1][0], m[1][1])
    else:
        raise ValueError(f"Unsupported rotation order '{order}'. Supported orders: xyz, yzx, zxy, xzy, yxz, zyx")

    return [math.degrees(x), math.degrees(y), math.degrees(z)]


# -----------------------------------------------------------------------------
# 4. Coordinate Transformations: Camera Frame <-> Maya Standard
# -----------------------------------------------------------------------------

def cam_pos_to_maya(pos_meters: Sequence[float]) -> Vec3:
    """
    Convert SAM 3D camera frame position (meters, X-right, Y-down, Z-forward)
    to Maya World space (centimeters, X-right, Y-up, Z-depth/forward).
    X_maya = X_cam * 100.0
    Y_maya = -Y_cam * 100.0
    Z_maya = -Z_cam * 100.0
    """
    return [pos_meters[0] * 100.0, -pos_meters[1] * 100.0, -pos_meters[2] * 100.0]


def maya_pos_to_cam(pos_cm: Sequence[float]) -> Vec3:
    """Convert Maya position back to Camera space in meters."""
    return [pos_cm[0] * 0.01, -pos_cm[1] * 0.01, -pos_cm[2] * 0.01]


def cam_rot_to_maya_rot(q_cam: Sequence[float]) -> Quat:
    """
    Transforms rotation quaternion from Camera frame to Maya frame.
    Under coordinate basis transformation P = diag(1, -1, -1),
    R_maya = P * R_cam * P
    For quaternion [x, y, z, w], this corresponds to [x, -y, -z, w].
    """
    return q_normalize([q_cam[0], -q_cam[1], -q_cam[2], q_cam[3]])


def maya_rot_to_cam_rot(q_maya: Sequence[float]) -> Quat:
    """Inverse of cam_rot_to_maya_rot (since P = P^-1, identical operation)."""
    return q_normalize([q_maya[0], -q_maya[1], -q_maya[2], q_maya[3]])


# -----------------------------------------------------------------------------
# 5. Forward Kinematics (FK)
# -----------------------------------------------------------------------------

def fk_reconstruct(
    parent_indices: Sequence[int],
    local_translations: Sequence[Sequence[float]],
    local_rotations: Sequence[Sequence[float]],
    root_translation: Optional[Sequence[float]] = None,
    root_rotation: Optional[Sequence[float]] = None
) -> Tuple[List[Vec3], List[Quat]]:
    """
    Computes global world positions and global world rotations for a kinematic tree.
    Returns: (world_positions, world_rotations)
    """
    num_joints = len(parent_indices)
    world_positions: List[Vec3] = [[0.0, 0.0, 0.0] for _ in range(num_joints)]
    world_rotations: List[Quat] = [[0.0, 0.0, 0.0, 1.0] for _ in range(num_joints)]

    r_trans = list(root_translation) if root_translation is not None else [0.0, 0.0, 0.0]
    r_rot = q_normalize(root_rotation) if root_rotation is not None else [0.0, 0.0, 0.0, 1.0]

    for i in range(num_joints):
        p_idx = parent_indices[i]
        l_trans = local_translations[i]
        l_rot = q_normalize(local_rotations[i])

        if p_idx < 0:
            # Root joint
            w_rot = q_multiply(r_rot, l_rot)
            w_pos = v_add(r_trans, q_rotate_vector(r_rot, l_trans))
        else:
            p_pos = world_positions[p_idx]
            p_rot = world_rotations[p_idx]
            w_rot = q_multiply(p_rot, l_rot)
            offset_rotated = q_rotate_vector(p_rot, l_trans)
            w_pos = v_add(p_pos, offset_rotated)

        world_positions[i] = w_pos
        world_rotations[i] = w_rot

    return world_positions, world_rotations
