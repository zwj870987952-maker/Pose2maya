"""
Maya GUI for Universal 3D Pose DCC Skeleton & Retargeter
Provides:
1. Universal DCC Standard Skeleton generation (UE5 Mannequin or HumanIK/Mixamo conventions, Core vs Full 127 bones)
2. Direct FBX export for Unreal Engine 5 / Blender
3. High-precision retargeting to Target Character A (e.g. sk_test.ma or Advanced Skeleton rigs)
"""

import os
import maya.cmds as cmds
from dcc_skeleton_builder import DCCSkeletonBuilder
from pose_retargeter import PoseRetargeter, retarget_sample_pose

WINDOW_NAME = "UniversalPoseDCCUI"

def auto_detect_namespace():
    if cmds.objExists("Root_M") or cmds.objExists("RootX_M"):
        return ""
    for ns in cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []:
        if cmds.objExists(f"{ns}:Root_M") or cmds.objExists(f"{ns}:RootX_M"):
            return f"{ns}:"
    return ""

def create_ui():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    win = cmds.window(WINDOW_NAME, title="Universal 3D Pose DCC Skeleton & Retargeter", widthHeight=(460, 560), resizeToFitChildren=True)
    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAttach=('both', 15))

    cmds.text(label="3D 姿态通用 DCC 骨架生成与重定向系统", font="boldLabelFont", height=32)
    cmds.separator(height=10, style='in')

    # ---------------------------------------------------------------------------
    # Module 1: Universal DCC Skeleton Generator (骨架生成与标准化)
    # ---------------------------------------------------------------------------
    cmds.frameLayout(label="【第 1 步】生成通用 DCC 标准骨架 (Universal Source Skeleton)", collapsable=True, collapse=False, marginWidth=5, marginHeight=5)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

    # Naming convention & Mode
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 260], adjustableColumn=2)
    cmds.text(label="骨架命名规范:")
    cmds.optionMenu("om_naming")
    cmds.menuItem(label="UE5 官方规范 (root, pelvis, thigh_l...)")
    cmds.menuItem(label="HumanIK / Mixamo 规范 (Hips, LeftUpLeg...)")
    cmds.setParent('..')

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 260], adjustableColumn=2)
    cmds.text(label="骨骼复杂度模式:")
    cmds.optionMenu("om_mode")
    cmds.menuItem(label="核心人形骨架 (Core 54骨，含主干与主指)")
    cmds.menuItem(label="全精度骨架 (Full 127骨，含全部指节、面部与扭转骨)")
    cmds.setParent('..')

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 260], adjustableColumn=2)
    cmds.text(label="世界坐标偏移 X/Y/Z:")
    cmds.textField("tf_offset", text="180.0, 0.0, 0.0")
    cmds.setParent('..')

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 260], adjustableColumn=2)
    cmds.text(label="骨架缩放系数 (Scale):")
    cmds.floatField("ff_scale", value=100.0, precision=1)
    cmds.setParent('..')

    cmds.button(label="★ 一键生成/更新当前标准 DCC 骨架", height=34, backgroundColor=[0.22, 0.42, 0.32], command=ui_build_dcc_skeleton)
    cmds.button(label="烘焙 1~6 组基准动作至标准骨架时间线", height=30, backgroundColor=[0.25, 0.35, 0.50], command=ui_bake_dcc_animation)
    cmds.button(label="导出标准骨架及动画为 FBX 文件...", height=30, backgroundColor=[0.38, 0.30, 0.45], command=ui_export_dcc_fbx)

    cmds.setParent('..')
    cmds.setParent('..')

    # ---------------------------------------------------------------------------
    # Module 2: Retarget to Target Rig (重定向到场景目标角色)
    # ---------------------------------------------------------------------------
    cmds.frameLayout(label="【第 2 步】姿态重定向至场景目标角色 (Target Character)", collapsable=True, collapse=False, marginWidth=5, marginHeight=5)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 260], adjustableColumn=2)
    cmds.text(label="目标角色 Namespace:")
    default_ns = auto_detect_namespace()
    cmds.textField("tgt_ns_field", text=default_ns)
    cmds.setParent('..')

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[200, 200])
    cmds.checkBox("cb_keyframe", label="自动打关键帧(时间线)", value=True)
    cmds.checkBox("cb_use_ik", label="优先使用 IK 控制器", value=True)
    cmds.setParent('..')

    cmds.text(label="基准姿态测试 (Benchmark Poses):", align="left", font="smallBoldLabelFont")
    cmds.rowLayout(numberOfColumns=3, columnWidth3=[130, 130, 130])
    cmds.button(label="1. 标准站姿", height=30, command=lambda x: run_sample(1))
    cmds.button(label="2. 高难度跳舞", height=30, command=lambda x: run_sample(2))
    cmds.button(label="3. 3D机甲姿态", height=30, command=lambda x: run_sample(3))
    cmds.setParent('..')

    cmds.rowLayout(numberOfColumns=3, columnWidth3=[130, 130, 130])
    cmds.button(label="4. 动漫立绘", height=30, command=lambda x: run_sample(4))
    cmds.button(label="5. 强透视俯冲", height=30, command=lambda x: run_sample(5))
    cmds.button(label="6. 肢体倒地遮挡", height=30, command=lambda x: run_sample(6))
    cmds.setParent('..')

    cmds.button(label="★ 一键重定向全部 6 组姿态到目标角色时间线 (帧 1 ~ 50)", height=34, backgroundColor=[0.25, 0.45, 0.65], command=run_batch_all)

    cmds.setParent('..')
    cmds.setParent('..')

    # ---------------------------------------------------------------------------
    # Module 3: Custom JSON Loading
    # ---------------------------------------------------------------------------
    cmds.frameLayout(label="【自定义】载入图片姿态 JSON 文件", collapsable=True, collapse=True, marginWidth=5, marginHeight=5)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
    cmds.button(label="浏览并导入自定义 3D 姿态 JSON (*_skeleton.json)...", height=36, backgroundColor=[0.3, 0.3, 0.3], command=open_file_dialog)
    cmds.setParent('..')
    cmds.setParent('..')

    cmds.showWindow(win)

# Helper functions
def get_builder_params():
    naming_val = cmds.optionMenu("om_naming", q=True, v=True) if cmds.optionMenu("om_naming", exists=True) else "UE5"
    naming_style = "ue5" if "UE5" in naming_val else "humanik"

    mode_val = cmds.optionMenu("om_mode", q=True, v=True) if cmds.optionMenu("om_mode", exists=True) else "Core"
    mode = "core" if "Core" in mode_val or "核心" in mode_val else "full"

    prefix = "UE5_" if naming_style == "ue5" else "HIK_"

    scale = cmds.floatField("ff_scale", q=True, v=True) if cmds.floatField("ff_scale", exists=True) else 100.0

    offset_str = cmds.textField("tf_offset", q=True, text=True) if cmds.textField("tf_offset", exists=True) else "180.0, 0.0, 0.0"
    try:
        offset = [float(x.strip()) for x in offset_str.split(",")]
    except Exception:
        offset = [180.0, 0.0, 0.0]

    return naming_style, mode, prefix, scale, offset

def ui_build_dcc_skeleton(*args):
    naming_style, mode, prefix, scale, offset = get_builder_params()
    builder = DCCSkeletonBuilder(naming_style=naming_style, mode=mode, prefix=prefix)
    json_path = r"D:\sam-3d-body\outputs\benchmark_results\01_human_standard_skeleton.json"
    joints = builder.build_skeleton(json_path, scale=scale, world_offset=offset)
    cmds.inViewMessage(amg=f"<hl>通用 DCC 骨架已成功生成！</hl> ({len(joints)} 根骨骼, {naming_style.upper()} 规范)", pos='topCenter', fade=True)

def ui_bake_dcc_animation(*args):
    naming_style, mode, prefix, scale, offset = get_builder_params()
    builder = DCCSkeletonBuilder(naming_style=naming_style, mode=mode, prefix=prefix)
    benchmarks = [
        (1, r"D:\sam-3d-body\outputs\benchmark_results\01_human_standard_skeleton.json"),
        (10, r"D:\sam-3d-body\outputs\benchmark_results\02_human_dancing_skeleton.json"),
        (20, r"D:\sam-3d-body\outputs\benchmark_results\03_game_3d_ironman_skeleton.json"),
        (30, r"D:\sam-3d-body\outputs\benchmark_results\04_anime_illustration_skeleton.json"),
        (40, r"D:\sam-3d-body\outputs\benchmark_results\05_strong_perspective_skeleton.json"),
        (50, r"D:\sam-3d-body\outputs\benchmark_results\06_limb_occlusion_skeleton.json")
    ]
    cmds.playbackOptions(min=1, max=60, animationStartTime=1, animationEndTime=60)
    for frame, path in benchmarks:
        if os.path.exists(path):
            builder.apply_pose(path, scale=scale, world_offset=offset, keyframe=frame)
    cmds.currentTime(10, update=True)
    cmds.inViewMessage(amg="<hl>6 组基准动作已成功烘焙至标准骨架！</hl>", pos='topCenter', fade=True)

def ui_export_dcc_fbx(*args):
    naming_style, mode, prefix, scale, offset = get_builder_params()
    builder = DCCSkeletonBuilder(naming_style=naming_style, mode=mode, prefix=prefix)
    fbx_path = cmds.fileDialog2(fileMode=0, caption="导出标准骨架 FBX", fileFilter="FBX (*.fbx)")
    if fbx_path and len(fbx_path) > 0:
        builder.export_fbx(fbx_path[0], start_frame=1, end_frame=50)
        cmds.inViewMessage(amg=f"<hl>已成功导出 FBX 至:</hl> {os.path.basename(fbx_path[0])}", pos='topCenter', fade=True)

def get_target_ns():
    if cmds.textField("tgt_ns_field", exists=True):
        return cmds.textField("tgt_ns_field", q=True, text=True).strip()
    return ""

def should_keyframe():
    if cmds.checkBox("cb_keyframe", exists=True):
        return cmds.checkBox("cb_keyframe", q=True, value=True)
    return True

def run_sample(idx):
    ns = get_target_ns()
    kf = cmds.currentTime(q=True) if should_keyframe() else None
    retarget_sample_pose(sample_idx=idx, target_namespace=ns, create_template=False, keyframe=kf)
    cmds.inViewMessage(amg=f"<hl>姿态 {idx}</hl> 已成功重定向至 {ns or '当前角色'}！", pos='topCenter', fade=True)

def run_batch_all(*args):
    ns = get_target_ns()
    benchmarks = [(1, 1), (10, 2), (20, 3), (30, 4), (40, 5), (50, 6)]
    cmds.playbackOptions(min=1, max=60, animationStartTime=1, animationEndTime=60)
    for frame, idx in benchmarks:
        cmds.currentTime(frame, update=True)
        retarget_sample_pose(sample_idx=idx, target_namespace=ns, create_template=False, keyframe=frame)
    cmds.currentTime(10, update=True)
    cmds.inViewMessage(amg=f"<hl>全部 6 组姿态已成功烘焙至时间线 (帧 1 ~ 50)！</hl>", pos='topCenter', fade=True)

def open_file_dialog(*args):
    json_path = cmds.fileDialog2(fileMode=1, caption="选择 SAM 3D 姿态 JSON", fileFilter="JSON Files (*.json)")
    if json_path and len(json_path) > 0:
        ns = get_target_ns()
        retargeter = PoseRetargeter(target_prefix=ns)
        kf = cmds.currentTime(q=True) if should_keyframe() else None
        retargeter.retarget_pose(json_path[0], use_ik=True, keyframe=kf)
        cmds.inViewMessage(amg=f"自定义姿态已成功重定向至 {ns or '当前角色'}！", pos='topCenter', fade=True)

if __name__ == '__main__':
    create_ui()
