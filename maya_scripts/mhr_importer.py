# -*- coding: utf-8 -*-
"""
Maya MHR Skeleton Importer (Phase 2 Starter Script)
在 Autodesk Maya 脚本编辑器 (Python) 中运行，读取 SAM 3D Body 导出的 *_skeleton.json 文件
并在 Maya 视口中自动生成标准的 127 关节 MHR 骨骼链结构。
"""
import os
import json

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None

def import_mhr_skeleton_to_maya(json_path):
    """
    读取标准化 skeleton.json，在 Maya 中重建骨骼
    """
    if cmds is None:
        print("[错误] 该脚本需要在 Autodesk Maya 环境下运行。")
        return

    if not os.path.exists(json_path):
        print(f"[错误] 未找到文件: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 解析骨骼列表
    joints = []
    if "joints" in data:
        joints = data["joints"]
    elif "skeleton" in data:
        skel = data["skeleton"]
        names = skel.get("joint_names", [])
        parents = skel.get("parent_indices", [])
        positions = skel.get("world_positions", [])
        for i in range(len(names)):
            joints.append({
                "id": i,
                "name": names[i],
                "parent_index": parents[i],
                "world_position": positions[i]
            })

    if not joints:
        print("[错误] JSON 文件中未找到有效的关节数据。")
        return

    # 清空当前选择
    cmds.select(clear=True)
    created_joints = {}

    # 按层级创建 Joint
    for j in joints:
        jid = j["id"]
        name = j["name"]
        raw_x, raw_y, raw_z = j["world_position"]

        # 单位换算：米 -> 厘米 (Maya 默认单位)
        # 坐标系换算：相机系 Y-down -> Maya 世界系 Y-up
        pos_maya = (raw_x * 100.0, -raw_y * 100.0, -raw_z * 100.0)

        p_idx = j["parent_index"]
        if p_idx >= 0 and p_idx in created_joints:
            cmds.select(created_joints[p_idx])
        else:
            cmds.select(clear=True)

        j_node = cmds.joint(name=name, position=pos_maya)
        created_joints[jid] = j_node

    print(f"[Pose2maya] 成功在 Maya 场景中创建 {len(created_joints)} 个 MHR 骨骼节点！")
