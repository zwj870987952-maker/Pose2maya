"""
pose_retarget_ui.py
===================
Autodesk Maya GUI for Universal 3D Pose DCC Skeleton & Retargeter (v2).
Provides:
1. Universal DCC Standard Skeleton generation & FBX export
2. Character Rig Retargeting with Profile selection, FK/IK toggle, and Part Masking
3. Safe Transaction control: Preview, Cancel/Restore, and Single-Chunk Commit
4. Benchmark poses & Custom JSON / Image inference execution
5. Rig calibration & custom profile persistence
"""

import os
import json
from typing import Optional

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None

from dcc_skeleton_builder import DCCSkeletonBuilder
from pose_retargeter import PoseRetargeter, retarget_sample_pose
from maya_scripts.rig_inspector import auto_detect_character_namespace, inspect_scene_character, calibrate_profile_from_scene
from maya_scripts.rig_adapter import prepare_write_plan
from maya_scripts.pose_session import PoseSession
from pose_core.mhr_adapter import load_pose_sample, get_authoritative_mhr_skeleton_def
from pose_core.schema import RetargetProfile, RigProfile
from retarget.engine import retarget
from retarget.profiles import (
    get_preset_as5, get_preset_pure_joints_ue5, get_preset_pure_joints_humanik,
    save_rig_profile, load_rig_profile
)

WINDOW_NAME = "UniversalPoseDCCUI_v2"
GLOBAL_SESSION = PoseSession()
CURRENT_PREVIEW_PLAN = None
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Active Pose state
CURRENT_LOADED_SAMPLE_IDX = 1
CURRENT_LOADED_POSE_PATH = os.path.join(REPO_ROOT, "data", "sample_poses", "01_human_standard_skeleton.json")
CUSTOM_RIG_PROFILE: Optional[RigProfile] = None


def get_target_ns():
    if cmds and cmds.textField("tgt_ns_field", exists=True):
        return cmds.textField("tgt_ns_field", q=True, text=True).strip()
    return ""


def get_use_ik():
    if cmds and cmds.checkBox("cb_use_ik", exists=True):
        return cmds.checkBox("cb_use_ik", q=True, value=True)
    return True


def should_keyframe():
    if cmds and cmds.checkBox("cb_keyframe", exists=True):
        return cmds.checkBox("cb_keyframe", q=True, value=True)
    return True


def get_part_mask():
    mask = {}
    parts = [
        ("pelvis", "cb_part_pelvis"),
        ("spine", "cb_part_spine"),
        ("neck_head", "cb_part_neck"),
        ("left_arm", "cb_part_arm_l"),
        ("right_arm", "cb_part_arm_r"),
        ("left_leg", "cb_part_leg_l"),
        ("right_leg", "cb_part_leg_r"),
    ]
    if cmds:
        for part, cb_name in parts:
            if cmds.checkBox(cb_name, exists=True):
                mask[part] = cmds.checkBox(cb_name, q=True, value=True)
            else:
                mask[part] = True
    else:
        mask = {p: True for p, _ in parts}
    return mask


def get_root_motion_policy():
    if cmds and cmds.optionMenu("om_root_policy", exists=True):
        val = cmds.optionMenu("om_root_policy", q=True, value=True)
        if "in_place" in val:
            return "in_place"
        elif "full" in val:
            return "full"
        else:
            return "pelvis_only"
    return "pelvis_only"


def get_ground_contact():
    if cmds and cmds.checkBox("cb_ground_contact", exists=True):
        return cmds.checkBox("cb_ground_contact", q=True, value=True)
    return False


def get_contact_legs():
    if cmds and cmds.optionMenu("om_contact_legs", exists=True):
        val = cmds.optionMenu("om_contact_legs", q=True, value=True)
        if "Left" in val or "左" in val:
            return "left"
        elif "Right" in val or "右" in val:
            return "right"
        return "both"
    return "both"


def get_selected_rig_profile() -> RigProfile:
    global CUSTOM_RIG_PROFILE
    choice = "Advanced Skeleton 5"
    if cmds and cmds.optionMenu("om_rig_profile", exists=True):
        choice = cmds.optionMenu("om_rig_profile", q=True, value=True)

    if "Custom" in choice or "自定义" in choice:
        if CUSTOM_RIG_PROFILE is not None:
            return CUSTOM_RIG_PROFILE
        return get_preset_as5()
    elif "UE5" in choice:
        return get_preset_pure_joints_ue5()
    elif "HumanIK" in choice:
        return get_preset_pure_joints_humanik()
    else:
        return get_preset_as5()


def resolve_sample_path(sample_idx):
    sample_names = {
        1: "01_human_standard_skeleton.json",
        2: "02_human_dancing_skeleton.json",
        3: "03_game_3d_ironman_skeleton.json",
        4: "04_anime_illustration_skeleton.json",
        5: "05_strong_perspective_skeleton.json",
        6: "06_limb_occlusion_skeleton.json"
    }
    fname = sample_names.get(sample_idx, "01_human_standard_skeleton.json")
    p1 = os.path.join(REPO_ROOT, "data", "sample_poses", fname)
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(r"D:\sam-3d-body\outputs\benchmark_results", fname)
    return p2


def _update_pose_label():
    if cmds and cmds.text("txt_current_pose", exists=True):
        name = os.path.basename(CURRENT_LOADED_POSE_PATH) if CURRENT_LOADED_POSE_PATH else "未载入"
        cmds.text("txt_current_pose", edit=True, label=f"当前姿态: {name}")


def execute_retarget_workflow(json_path, action="commit"):
    global CURRENT_PREVIEW_PLAN

    if not cmds:
        print("[PoseRetargetUI] cmds not available.")
        return

    ns = get_target_ns()
    use_ik = get_use_ik()
    part_mask = get_part_mask()
    rig_prof = get_selected_rig_profile()
    auto_key = should_keyframe()
    kf = cmds.currentTime(q=True) if auto_key else None

    # Check if all part masks are disabled
    if not any(part_mask.values()):
        cmds.warning("所有重定向部位已关闭 (part_mask 为空)，未产生任何修改。")
        return

    # 1. Parse Pose
    try:
        sample_pose = load_pose_sample(json_path)
    except Exception as e:
        cmds.warning(f"Failed parsing pose JSON: {e}")
        return

    # Auto fallback check for pure FK rigs
    has_ik = any(bool(c.ik_control) for c in rig_prof.chains.values())
    if use_ik and not has_ik:
        print("[PoseRetargetUI] Rig has no IK controllers; automatically retargeting in FK mode.")

    # 2. Retarget Profile
    mode_val = "ik" if (use_ik and has_ik) else "fk"
    retarget_prof = RetargetProfile(
        chain_modes={
            "spine": "fk",
            "neck_head": "fk",
            "left_arm": mode_val,
            "right_arm": mode_val,
            "left_leg": mode_val,
            "right_leg": mode_val
        },
        part_mask=part_mask,
        root_motion_mode=get_root_motion_policy(),
        ground_contact=get_ground_contact(),
        contact_legs={
            "left_leg": get_contact_legs() in ["both", "left"],
            "right_leg": get_contact_legs() in ["both", "right"],
        }
    )

    # 3. Solve Engine
    skel_def = get_authoritative_mhr_skeleton_def()
    res = retarget(sample_pose, skel_def, rig_prof, retarget_prof)
    if not res.success:
        cmds.warning(f"Engine failed: {'; '.join(res.errors)}")
        return

    # 4. Prepare WritePlan
    plan = prepare_write_plan(res, namespace=ns, auto_key=auto_key)
    if not plan.can_apply:
        cmds.warning(f"Application blocked: {'; '.join(plan.blockers)}")
        return

    CURRENT_PREVIEW_PLAN = plan

    # 5. Dispatch Action
    if action == "preview":
        rep = GLOBAL_SESSION.preview(plan)
        cmds.inViewMessage(amg=f"<hl>已进入姿态预览</hl> ({rep.channels_modified} 个通道受影响，可点【取消恢复】撤销)", pos='topCenter', fade=True)
    elif action == "cancel":
        rep = GLOBAL_SESSION.cancel()
        cmds.inViewMessage(amg="<hl>已取消预览并恢复原始姿态</hl>", pos='topCenter', fade=True)
    else:  # commit
        rep = GLOBAL_SESSION.commit(plan, keyframe=kf)
        if rep.status == "success":
            cmds.inViewMessage(amg=f"<hl>姿态应用成功！</hl> ({rep.channels_modified} 通道写入, 关键帧={kf})", pos='topCenter', fade=True)
        else:
            cmds.warning(f"Commit failed: {'; '.join(rep.messages)}")


def ui_select_sample(idx, execute_action=None):
    global CURRENT_LOADED_SAMPLE_IDX, CURRENT_LOADED_POSE_PATH
    CURRENT_LOADED_SAMPLE_IDX = idx
    CURRENT_LOADED_POSE_PATH = resolve_sample_path(idx)
    _update_pose_label()
    if execute_action:
        execute_retarget_workflow(CURRENT_LOADED_POSE_PATH, action=execute_action)


def ui_run_preview():
    global CURRENT_LOADED_POSE_PATH
    if not CURRENT_LOADED_POSE_PATH or not os.path.exists(CURRENT_LOADED_POSE_PATH):
        if cmds:
            cmds.warning(f"当前未加载有效姿态文件: {CURRENT_LOADED_POSE_PATH}")
        return
    execute_retarget_workflow(CURRENT_LOADED_POSE_PATH, action="preview")


def ui_run_commit():
    global CURRENT_LOADED_POSE_PATH
    if not CURRENT_LOADED_POSE_PATH or not os.path.exists(CURRENT_LOADED_POSE_PATH):
        if cmds:
            cmds.warning(f"当前未加载有效姿态文件: {CURRENT_LOADED_POSE_PATH}")
        return
    execute_retarget_workflow(CURRENT_LOADED_POSE_PATH, action="commit")


def ui_run_cancel():
    GLOBAL_SESSION.cancel()
    if cmds:
        cmds.inViewMessage(amg="<hl>已恢复场景初始姿态</hl>", pos='topCenter', fade=True)


def ui_load_custom_profile():
    global CUSTOM_RIG_PROFILE
    if not cmds: return
    res = cmds.fileDialog2(fileMode=1, caption="载入角色 RigProfile JSON", fileFilter="JSON Files (*.json)")
    if res and len(res) > 0:
        try:
            prof = load_rig_profile(res[0])
            CUSTOM_RIG_PROFILE = prof
            if cmds.optionMenu("om_rig_profile", exists=True):
                cmds.optionMenu("om_rig_profile", edit=True, value="自定义角色配置 (Custom Profile)")
            cmds.inViewMessage(amg=f"<hl>已成功载入配置: {prof.name}</hl>", pos='topCenter', fade=True)
        except Exception as e:
            cmds.warning(f"载入 RigProfile 失败: {e}")


def ui_save_current_profile():
    if not cmds: return
    prof = get_selected_rig_profile()
    res = cmds.fileDialog2(fileMode=0, caption="保存当前 RigProfile JSON", fileFilter="JSON Files (*.json)")
    if res and len(res) > 0:
        path = res[0]
        if not path.endswith(".json"):
            path += ".json"
        try:
            save_rig_profile(prof, path)
            cmds.inViewMessage(amg=f"<hl>配置已保存至: {os.path.basename(path)}</hl>", pos='topCenter', fade=True)
        except Exception as e:
            cmds.warning(f"保存 RigProfile 失败: {e}")


def ui_calibrate_from_scene():
    global CUSTOM_RIG_PROFILE
    if not cmds: return
    ns = get_target_ns()
    prof = get_selected_rig_profile()
    calibrated_prof, captured = calibrate_profile_from_scene(prof, ns)
    CUSTOM_RIG_PROFILE = calibrated_prof
    if cmds.optionMenu("om_rig_profile", exists=True):
        cmds.optionMenu("om_rig_profile", edit=True, value="自定义角色配置 (Custom Profile)")
    msg = f"已从场景校准: {len(captured)} 项数据"
    cmds.inViewMessage(amg=f"<hl>{msg}</hl>", pos='topCenter', fade=True)
    print(f"[PoseRetargetUI] Calibrated profile details: {captured}")


def create_ui():
    if not cmds:
        print("[PoseRetargetUI] Maya not detected.")
        return

    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    win = cmds.window(
        WINDOW_NAME,
        title="Universal 3D Pose DCC Skeleton & Retargeter (v2.0)",
        widthHeight=(500, 720),
        resizeToFitChildren=True
    )
    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAttach=('both', 15))

    cmds.text(label="3D 姿态通用 DCC 骨架生成与重定向系统 (v2.0)", font="boldLabelFont", height=32)
    cmds.separator(height=10, style='in')

    # ---------------------------------------------------------------------------
    # Module 1: Universal DCC Skeleton Generator
    # ---------------------------------------------------------------------------
    cmds.frameLayout(label="【第 1 步】生成通用 DCC 标准骨架 (Universal Source Skeleton)", collapsable=True, collapse=False, marginWidth=5, marginHeight=5)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 300], adjustableColumn=2)
    cmds.text(label="骨架命名规范:")
    cmds.optionMenu("om_naming")
    cmds.menuItem(label="UE5 官方规范 (root, pelvis, thigh_l...)")
    cmds.menuItem(label="HumanIK / Mixamo 规范 (Hips, LeftUpLeg...)")
    cmds.setParent('..')

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 300], adjustableColumn=2)
    cmds.text(label="骨骼复杂度模式:")
    cmds.optionMenu("om_mode")
    cmds.menuItem(label="核心人形骨架 (Core 54骨，含主干与主指)")
    cmds.menuItem(label="全精度骨架 (Full 127骨，含全部指节、面部与扭转骨)")
    cmds.setParent('..')

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 300], adjustableColumn=2)
    cmds.text(label="骨架缩放系数 (Scale):")
    cmds.floatField("ff_scale", value=100.0, precision=1)
    cmds.setParent('..')

    cmds.button(label="★ 一键生成/更新当前标准 DCC 骨架", height=32, backgroundColor=[0.22, 0.42, 0.32], command=lambda x: ui_build_dcc_skeleton())
    cmds.setParent('..')
    cmds.setParent('..')

    # ---------------------------------------------------------------------------
    # Module 2: Retarget to Target Rig
    # ---------------------------------------------------------------------------
    cmds.frameLayout(label="【第 2 步】姿态重定向至场景目标角色 (Target Character)", collapsable=True, collapse=False, marginWidth=5, marginHeight=5)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 300], adjustableColumn=2)
    cmds.text(label="目标角色 Namespace:")
    default_ns = auto_detect_character_namespace()
    cmds.textField("tgt_ns_field", text=default_ns)
    cmds.setParent('..')

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 300], adjustableColumn=2)
    cmds.text(label="角色绑定配置 (Profile):")
    cmds.optionMenu("om_rig_profile")
    cmds.menuItem(label="Advanced Skeleton 5 (AS5 风格绑定)")
    cmds.menuItem(label="UE5 Mannequin (纯变形骨架)")
    cmds.menuItem(label="HumanIK / Mixamo (纯变形骨架)")
    cmds.menuItem(label="自定义角色配置 (Custom Profile)")
    cmds.setParent('..')

    # Profile actions
    cmds.rowLayout(numberOfColumns=3, columnWidth3=[140, 150, 150])
    cmds.button(label="🎯 从场景测量校准", height=26, backgroundColor=[0.3, 0.4, 0.5], command=lambda x: ui_calibrate_from_scene())
    cmds.button(label="📁 载入配置 JSON", height=26, command=lambda x: ui_load_custom_profile())
    cmds.button(label="💾 保存配置 JSON", height=26, command=lambda x: ui_save_current_profile())
    cmds.setParent('..')

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[220, 220])
    cmds.checkBox("cb_keyframe", label="自动打关键帧(时间线)", value=True)
    cmds.checkBox("cb_use_ik", label="四肢优先使用 IK 控制器", value=True)
    cmds.setParent('..')

    # Root Motion Policy
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[140, 300], adjustableColumn=2)
    cmds.text(label="根运动策略 (Root Policy):")
    cmds.optionMenu("om_root_policy")
    cmds.menuItem(label="pelvis_only (仅骨盆位移)")
    cmds.menuItem(label="in_place (原地锁死 X/Z)")
    cmds.menuItem(label="full (完整 X/Z 根位移 + Y 骨盆)")
    cmds.setParent('..')

    # Ground Contact
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[200, 240])
    cmds.checkBox("cb_ground_contact", label="启用地面接触校准", value=False)
    cmds.optionMenu("om_contact_legs")
    cmds.menuItem(label="双脚接触 (Both Legs)")
    cmds.menuItem(label="仅左脚 (Left Leg Only)")
    cmds.menuItem(label="仅右脚 (Right Leg Only)")
    cmds.setParent('..')

    cmds.text(label="重定向部位开关 (Part Mask):", font="smallBoldLabelFont")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=[110, 110, 110, 110])
    cmds.checkBox("cb_part_pelvis", label="骨盆盆骨", value=True)
    cmds.checkBox("cb_part_spine", label="躯干脊柱", value=True)
    cmds.checkBox("cb_part_neck", label="颈部头部", value=True)
    cmds.checkBox("cb_part_arm_l", label="左手臂", value=True)
    cmds.setParent('..')
    cmds.rowLayout(numberOfColumns=3, columnWidth3=[110, 110, 110])
    cmds.checkBox("cb_part_arm_r", label="右手臂", value=True)
    cmds.checkBox("cb_part_leg_l", label="左腿部", value=True)
    cmds.checkBox("cb_part_leg_r", label="右腿部", value=True)
    cmds.setParent('..')

    # Status of current pose
    cmds.separator(height=6, style='none')
    init_pose_name = os.path.basename(CURRENT_LOADED_POSE_PATH) if CURRENT_LOADED_POSE_PATH else "未载入"
    cmds.text("txt_current_pose", label=f"当前姿态: {init_pose_name}", font="boldLabelFont", align='center')

    # Safe Transaction Buttons
    cmds.rowLayout(numberOfColumns=3, columnWidth3=[150, 150, 150])
    cmds.button(label="👁 临时预览 (Preview)", height=34, backgroundColor=[0.35, 0.45, 0.35], command=lambda x: ui_run_preview())
    cmds.button(label="✔ 提交应用 (Commit)", height=34, backgroundColor=[0.25, 0.45, 0.35], command=lambda x: ui_run_commit())
    cmds.button(label="↩ 取消恢复 (Cancel)", height=34, backgroundColor=[0.45, 0.35, 0.35], command=lambda x: ui_run_cancel())
    cmds.setParent('..')

    cmds.separator(height=6, style='none')
    cmds.text(label="基准姿态测试 (Benchmark Poses):", font="smallBoldLabelFont")
    cmds.rowLayout(numberOfColumns=3, columnWidth3=[145, 145, 145])
    cmds.button(label="1. 标准站姿", height=28, command=lambda x: ui_select_sample(1, "preview"))
    cmds.button(label="2. 高难度跳舞", height=28, command=lambda x: ui_select_sample(2, "preview"))
    cmds.button(label="3. 3D机甲姿态", height=28, command=lambda x: ui_select_sample(3, "preview"))
    cmds.setParent('..')
    cmds.rowLayout(numberOfColumns=3, columnWidth3=[145, 145, 145])
    cmds.button(label="4. 动漫立绘", height=28, command=lambda x: ui_select_sample(4, "preview"))
    cmds.button(label="5. 强透视俯冲", height=28, command=lambda x: ui_select_sample(5, "preview"))
    cmds.button(label="6. 肢体倒地遮挡", height=28, command=lambda x: ui_select_sample(6, "preview"))
    cmds.setParent('..')

    cmds.separator(height=6, style='none')
    cmds.button(label="★ 一键烘焙全部 6 组姿态到时间线 (帧 1 ~ 50)", height=34, backgroundColor=[0.25, 0.45, 0.65], command=lambda x: ui_run_batch_all())

    cmds.setParent('..')
    cmds.setParent('..')

    # ---------------------------------------------------------------------------
    # Module 3: Custom JSON Loading
    # ---------------------------------------------------------------------------
    cmds.frameLayout(label="【自定义】载入图片姿态 JSON 文件", collapsable=True, collapse=True, marginWidth=5, marginHeight=5)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
    cmds.button(label="浏览并导入自定义 3D 姿态 JSON (*_skeleton.json)...", height=34, backgroundColor=[0.3, 0.3, 0.3], command=lambda x: ui_open_file_dialog())
    cmds.setParent('..')
    cmds.setParent('..')

    # ---------------------------------------------------------------------------
    # Module 4: AI Inference from Single Image (AUD-10)
    # ---------------------------------------------------------------------------
    cmds.frameLayout(label="【AI 推理】从单张图片生成并应用姿态", collapsable=True, collapse=False, marginWidth=5, marginHeight=5)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

    cmds.rowLayout(numberOfColumns=3, columnWidth3=[70, 260, 60], adjustableColumn=2)
    cmds.text(label="服务地址:")
    cmds.textField("tf_service_host", text="http://127.0.0.1:7860")
    cmds.button(label="测连接", command=lambda x: ui_check_service_health())
    cmds.setParent('..')

    cmds.rowLayout(numberOfColumns=3, columnWidth3=[70, 260, 60], adjustableColumn=2)
    cmds.text(label="图片路径:")
    cmds.textField("tf_image_path", text="")
    cmds.button(label="浏览...", command=lambda x: ui_browse_image_file())
    cmds.setParent('..')

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[200, 200], adjustableColumn=1)
    cmds.button(label="提交推理并应用 (当前帧)", height=32, backgroundColor=[0.18, 0.55, 0.34], command=lambda x: ui_submit_image_inference())
    cmds.text("txt_inference_status", label="状态: 就绪", align="left")
    cmds.setParent('..')

    cmds.setParent('..')
    cmds.setParent('..')

    cmds.showWindow(win)


def ui_build_dcc_skeleton():
    if not cmds: return
    naming_val = cmds.optionMenu("om_naming", q=True, v=True)
    naming_style = "ue5" if "UE5" in naming_val else "humanik"
    mode_val = cmds.optionMenu("om_mode", q=True, v=True)
    mode = "core" if "Core" in mode_val or "核心" in mode_val else "full"
    prefix = "UE5_" if naming_style == "ue5" else "HIK_"
    scale = cmds.floatField("ff_scale", q=True, v=True) if cmds.floatField("ff_scale", exists=True) else 100.0

    builder = DCCSkeletonBuilder(naming_style=naming_style, mode=mode, prefix=prefix)
    sample_path = resolve_sample_path(1)
    joints = builder.build_skeleton(sample_path, scale=scale)
    cmds.inViewMessage(amg=f"<hl>DCC 标准骨架已成功生成！</hl> ({len(joints)} 根骨骼, {naming_style.upper()})", pos='topCenter', fade=True)


def ui_run_batch_all():
    benchmarks = [(1, 1), (10, 2), (20, 3), (30, 4), (40, 5), (50, 6)]
    if cmds:
        cmds.playbackOptions(min=1, max=60, animationStartTime=1, animationEndTime=60)
        for frame, idx in benchmarks:
            cmds.currentTime(frame, update=True)
            ui_select_sample(idx, execute_action="commit")
        cmds.currentTime(10, update=True)
        cmds.inViewMessage(amg="<hl>全部 6 组姿态已成功烘焙至时间线 (帧 1 ~ 50)！</hl>", pos='topCenter', fade=True)


def ui_open_file_dialog():
    global CURRENT_LOADED_SAMPLE_IDX, CURRENT_LOADED_POSE_PATH
    if not cmds: return
    res = cmds.fileDialog2(fileMode=1, caption="选择 3D 姿态 JSON", fileFilter="JSON Files (*.json)")
    if res and len(res) > 0:
        CURRENT_LOADED_SAMPLE_IDX = None
        CURRENT_LOADED_POSE_PATH = res[0]
        _update_pose_label()
        execute_retarget_workflow(CURRENT_LOADED_POSE_PATH, action="preview")


def ui_check_service_health():
    if not cmds: return
    host = cmds.textField("tf_service_host", q=True, text=True) if cmds.textField("tf_service_host", exists=True) else "http://127.0.0.1:7860"
    from maya_scripts.service_client import InferenceServiceClient
    client = InferenceServiceClient(host=host)
    ok = client.check_health()
    msg = "<hl>服务在线！</hl> 已成功连接到 Pose2maya 推理服务。" if ok else "<hl>连接失败！</hl> 无法连接到服务，请确认 start_webui.py 已启动。"
    cmds.inViewMessage(amg=msg, pos='topCenter', fade=True)
    if cmds.text("txt_inference_status", exists=True):
        cmds.text("txt_inference_status", edit=True, label="状态: 服务在线" if ok else "状态: 服务不可用")


def ui_browse_image_file():
    if not cmds: return
    res = cmds.fileDialog2(fileMode=1, caption="选择人体照片", fileFilter="Images (*.jpg *.jpeg *.png *.webp)")
    if res and len(res) > 0:
        cmds.textField("tf_image_path", edit=True, text=res[0])


def ui_submit_image_inference():
    if not cmds: return
    img_path = cmds.textField("tf_image_path", q=True, text=True) if cmds.textField("tf_image_path", exists=True) else ""
    if not img_path or not os.path.exists(img_path):
        cmds.warning("请选择有效的图片文件！")
        return
    host = cmds.textField("tf_service_host", q=True, text=True) if cmds.textField("tf_service_host", exists=True) else "http://127.0.0.1:7860"
    ns = cmds.textField("tf_namespace", q=True, text=True) if cmds.textField("tf_namespace", exists=True) else ""
    use_ik = cmds.checkBox("cb_use_ik", q=True, v=True) if cmds.checkBox("cb_use_ik", exists=True) else True
    auto_key = cmds.checkBox("cb_auto_key", q=True, v=True) if cmds.checkBox("cb_auto_key", exists=True) else True

    from maya_scripts.service_client import InferenceServiceClient
    client = InferenceServiceClient(host=host)

    if cmds.text("txt_inference_status", exists=True):
        cmds.text("txt_inference_status", edit=True, label="状态: 推理中...")

    def on_ok(res):
        if cmds.text("txt_inference_status", exists=True):
            cmds.text("txt_inference_status", edit=True, label="状态: 应用成功！")
        cmds.inViewMessage(amg="<hl>AI 姿态推理并应用成功！</hl>", pos='topCenter', fade=True)

    def on_err(err):
        if cmds.text("txt_inference_status", exists=True):
            cmds.text("txt_inference_status", edit=True, label="状态: 失败")
        cmds.warning(f"AI 推理失败: {err}")

    client.submit_and_apply_async(
        image_path=img_path,
        target_namespace=ns,
        use_ik=use_ik,
        auto_key=auto_key,
        on_success=on_ok,
        on_error=on_err
    )


if __name__ == '__main__':
    create_ui()
