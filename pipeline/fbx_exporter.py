import os
import sys
import subprocess
import json

BLENDER_CANDIDATES = [
    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
]

MAYA_CANDIDATES = [
    r"C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe",
    r"C:\Program Files\Autodesk\Maya2024\bin\mayapy.exe",
    r"C:\Program Files\Autodesk\Maya2023\bin\mayapy.exe",
]

BLENDER_HELPER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_dcc_worker.py")

BLENDER_WORKER_CODE = """import bpy
import json
import sys
import os
import mathutils

argv = sys.argv
args = argv[argv.index('--') + 1:]
json_path = args[0]
fbx_path = args[1]

bpy.ops.wm.read_factory_settings(use_empty=True)

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

if 'skeleton' in data:
    skel = data['skeleton']
    names = skel['joint_names']
    parents = skel['parent_indices']
    positions = skel['world_positions']
else:
    joints = data['joints']
    names = [j['name'] for j in joints]
    parents = [j['parent_index'] for j in joints]
    positions = [j['world_position'] for j in joints]

arm_data = bpy.data.armatures.new('MHR_Skeleton')
arm_obj = bpy.data.objects.new('MHR_Armature', arm_data)
bpy.context.collection.objects.link(arm_obj)
bpy.context.view_layer.objects.active = arm_obj

bpy.ops.object.mode_set(mode='EDIT')
edit_bones = arm_data.edit_bones

root_x, root_y, root_z = positions[0]

created_bones = {}
for i in range(len(names)):
    b = edit_bones.new(names[i])
    rx, ry, rz = positions[i]
    bx = -(rx - root_x)
    by = -(rz - root_z)
    bz = -(ry - root_y)
    b.head = mathutils.Vector((bx, by, bz))
    created_bones[i] = b

for i in range(len(names)):
    b = created_bones[i]
    p_idx = parents[i]
    if p_idx >= 0 and p_idx in created_bones:
        b.parent = created_bones[p_idx]

    children = [created_bones[ci] for ci, pi in enumerate(parents) if pi == i]
    if children:
        b.tail = children[0].head
        if (b.tail - b.head).length < 0.005:
            b.tail = b.head + mathutils.Vector((0, 0, 0.02))
    else:
        if b.parent:
            diff = b.head - b.parent.head
            if diff.length > 0.005:
                b.tail = b.head + diff.normalized() * 0.03
            else:
                b.tail = b.head + mathutils.Vector((0, 0, 0.03))
        else:
            b.tail = b.head + mathutils.Vector((0, 0, 0.05))

bpy.ops.object.mode_set(mode='OBJECT')

# 1. Export FBX with axis_forward='Z', axis_up='Y' (Aligned with Three.js WebUI & Maya front view)
bpy.ops.export_scene.fbx(
    filepath=fbx_path,
    use_selection=False,
    object_types={'ARMATURE'},
    add_leaf_bones=False,
    armature_nodetype='NULL',
    bake_anim=False,
    axis_forward='Z',
    axis_up='Y'
)
print('SUCCESS_EXPORTED_FBX:', fbx_path)

# 2. Export BVH
bvh_path = os.path.splitext(fbx_path)[0] + '.bvh'
try:
    bpy.ops.export_anim.bvh(filepath=bvh_path, frame_start=1, frame_end=1, global_scale=1.0)
    print('SUCCESS_EXPORTED_BVH:', bvh_path)
except Exception as e:
    print('WARN_BVH_EXPORT_FAILED:', e)

# 3. Export GLB
glb_path = os.path.splitext(fbx_path)[0] + '.glb'
try:
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB')
    print('SUCCESS_EXPORTED_GLB:', glb_path)
except Exception as e:
    print('WARN_GLB_EXPORT_FAILED:', e)
"""

def find_blender_exe():
    for p in BLENDER_CANDIDATES:
        if os.path.exists(p):
            return p
    return None

def export_pure_python_bvh(json_path, bvh_path):
    """
    Pure Python BVH exporter as fallback with ZERO external software dependencies.
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        skel = data.get('skeleton', {})
        names = skel.get('joint_names', [])
        parents = skel.get('parent_indices', [])
        positions = skel.get('world_positions', [])
        if not positions:
            return None

        # Build children map
        children = {i: [] for i in range(len(names))}
        for i, p in enumerate(parents):
            if p >= 0:
                children[p].append(i)

        root_pos = positions[0]

        lines = ["HIERARCHY"]

        def write_node(i, indent=0):
            ind = "  " * indent
            name = names[i]
            p_idx = parents[i]
            if p_idx < 0:
                # Root
                lines.append(f"{ind}ROOT {name}")
                lines.append(f"{ind}{{")
                lines.append(f"{ind}  OFFSET 0.0 0.0 0.0")
                lines.append(f"{ind}  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation")
            else:
                lines.append(f"{ind}JOINT {name}")
                lines.append(f"{ind}{{")
                # Offset relative to parent in cm
                curr_p = positions[i]
                prev_p = positions[p_idx]
                ox = (curr_p[0] - prev_p[0]) * 100.0
                oy = -(curr_p[1] - prev_p[1]) * 100.0
                oz = -(curr_p[2] - prev_p[2]) * 100.0
                lines.append(f"{ind}  OFFSET {ox:.4f} {oy:.4f} {oz:.4f}")
                lines.append(f"{ind}  CHANNELS 3 Zrotation Xrotation Yrotation")

            ch_list = children.get(i, [])
            if ch_list:
                for c in ch_list:
                    write_node(c, indent + 1)
            else:
                # End Site
                lines.append(f"{ind}  End Site")
                lines.append(f"{ind}  {{")
                lines.append(f"{ind}    OFFSET 0.0 2.0 0.0")
                lines.append(f"{ind}  }}")

            lines.append(f"{ind}}}")

        write_node(0, 0)
        lines.append("MOTION")
        lines.append("Frames: 1")
        lines.append("Frame Time: 0.0333333")

        # Root position in cm + 0 rotations for all joints
        rx = 0.0
        ry = -(root_pos[1] - root_pos[1]) * 100.0
        rz = -(root_pos[2] - root_pos[2]) * 100.0
        motion_vals = [f"{rx:.4f}", f"{ry:.4f}", f"{rz:.4f}", "0.0", "0.0", "0.0"]
        for _ in range(len(names) - 1):
            motion_vals.extend(["0.0", "0.0", "0.0"])

        lines.append(" ".join(motion_vals))

        with open(bvh_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return bvh_path
    except Exception as e:
        print(f"[BVH Exporter] Pure Python export error: {e}")
        return None

def export_skeleton_json_to_fbx(skeleton_json_path, output_fbx_path):
    """
    Converts a standardized *_skeleton.json file to:
    1. *_skeleton.fbx (FBX binary, front-facing, aligned with WebUI)
    2. *_skeleton.bvh (BVH motion capture standard)
    3. *_skeleton.glb (GLTF binary standard)
    """
    out_dir = os.path.dirname(output_fbx_path)
    base = os.path.splitext(output_fbx_path)[0]
    bvh_path = f"{base}.bvh"
    glb_path = f"{base}.glb"

    blender_exe = find_blender_exe()
    if not blender_exe:
        print("[FBX Exporter] Warning: No Blender installation found. Falling back to Pure Python BVH exporter.")
        pure_bvh = export_pure_python_bvh(skeleton_json_path, bvh_path)
        return {
            "fbx": None,
            "bvh": pure_bvh,
            "glb": None
        }

    # Write helper worker script
    with open(BLENDER_HELPER_SCRIPT, "w", encoding="utf-8") as f:
        f.write(BLENDER_WORKER_CODE)

    cmd = [
        blender_exe,
        "--background",
        "--python", BLENDER_HELPER_SCRIPT,
        "--",
        os.path.abspath(skeleton_json_path),
        os.path.abspath(output_fbx_path)
    ]

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        res_fbx = output_fbx_path if os.path.exists(output_fbx_path) else None
        res_bvh = bvh_path if os.path.exists(bvh_path) else None
        res_glb = glb_path if os.path.exists(glb_path) else None

        # Fallback to pure python BVH if blender failed BVH
        if not res_bvh:
            res_bvh = export_pure_python_bvh(skeleton_json_path, bvh_path)

        return {
            "fbx": res_fbx,
            "bvh": res_bvh,
            "glb": res_glb
        }
    except Exception as e:
        print(f"[FBX Exporter] Error running export: {e}")
        pure_bvh = export_pure_python_bvh(skeleton_json_path, bvh_path)
        return {
            "fbx": None,
            "bvh": pure_bvh,
            "glb": None
        }
