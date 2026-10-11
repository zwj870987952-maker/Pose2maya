import bpy
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
