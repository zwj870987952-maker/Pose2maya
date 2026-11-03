"""
maya_scripts.service_client
===========================
Asynchronous HTTP client for Maya DCC to communicate with the InferenceService.
AUD-10 Compliant:
  - Supports multipart file upload for arbitrary local custom photos (spaces, non-ASCII paths).
  - Target scene, frame, and character integrity protection:
      - Validates scene file has not changed during async wait.
      - Guarantees keyframing writes to the intended start_frame rather than drifted current frame.
      - Verifies target character nodes still exist.
  - Safe main thread execution via maya.utils.executeInMainThreadWithResult.
"""

import os
import time
import json
import uuid
import threading
import urllib.request
import urllib.parse
from typing import Optional, Callable, Dict, Any, List, Tuple

try:
    import maya.cmds as cmds
    import maya.utils as mutils
except ImportError:
    cmds = None
    mutils = None

from pose_core.mhr_adapter import load_pose_sample, get_authoritative_mhr_skeleton_def
from retarget.engine import retarget
from retarget.profiles import load_rig_profile, load_retarget_profile
from maya_scripts.rig_adapter import prepare_write_plan
from maya_scripts.pose_session import PoseSession


def _encode_multipart(fields: Dict[str, str], files: Dict[str, Tuple[str, bytes, str]]) -> Tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    for name, (filename, file_bytes, content_type) in files.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8"))
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(file_bytes)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    content_type_hdr = f"multipart/form-data; boundary={boundary}"
    return bytes(body), content_type_hdr


class InferenceServiceClient:
    def __init__(self, host: str = "http://127.0.0.1:7860"):
        self.host = host.rstrip("/")

    def check_health(self) -> bool:
        try:
            url = f"{self.host}/api/health"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "ok"
        except Exception:
            return False

    def submit_and_apply_async(
        self,
        image_path: str,
        target_namespace: str = "",
        bbox: Optional[List[float]] = None,
        rig_id: str = "advanced_skeleton_5",
        use_ik: bool = True,
        auto_key: bool = True,
        on_success: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        """
        Submits image to inference service and applies result asynchronously to target character.
        Guarantees target scene/frame drift protection (AUD-10).
        """
        # Capture Maya scene baseline state and unique lifecycle token (AUD-10)
        start_scene = cmds.file(q=True, sceneName=True) if cmds else ""
        start_scene_token = cmds.ls("time1", uuid=True)[0] if (cmds and cmds.objExists("time1")) else ""
        start_frame = cmds.currentTime(q=True) if cmds else 1.0
        start_ns = target_namespace

        # Snapshot immutable profiles in main thread
        import copy
        rig_profile_snap = copy.deepcopy(load_rig_profile(rig_id))
        retarget_profile_snap = copy.deepcopy(load_retarget_profile("default_retarget"))
        if not use_ik:
            for k in retarget_profile_snap.chain_modes:
                retarget_profile_snap.chain_modes[k] = "fk"

        # Capture target node UUIDs
        target_node_uuids = {}
        if cmds:
            nodes_to_track = [rig_profile_snap.root_node, rig_profile_snap.pelvis_node]
            for chain in rig_profile_snap.chains.values():
                if chain.fk_controls:
                    nodes_to_track.extend(chain.fk_controls)
                if chain.ik_control:
                    nodes_to_track.append(chain.ik_control)
            for n in nodes_to_track:
                full_n = f"{start_ns.rstrip(':') + ':' if start_ns else ''}{n}"
                if cmds.objExists(full_n):
                    uuids = cmds.ls(full_n, uuid=True)
                    if uuids:
                        target_node_uuids[full_n] = uuids[0]

        def _worker():
            try:
                # 1. Prepare Request Data (AUD-10: Upload real file if local path)
                job_url = f"{self.host}/api/jobs"
                fields = {}
                files = {}

                if bbox:
                    fields["bbox"] = json.dumps(bbox)

                if os.path.exists(image_path) and os.path.isfile(image_path):
                    filename = os.path.basename(image_path)
                    ext = os.path.splitext(filename)[1].lower()
                    mime = "image/png" if ext == ".png" else "image/jpeg"
                    with open(image_path, "rb") as f:
                        file_bytes = f.read()
                    files["file"] = (filename, file_bytes, mime)
                else:
                    # Preset fallback ID
                    fields["preset_id"] = os.path.basename(image_path)

                if files:
                    body_bytes, content_type = _encode_multipart(fields, files)
                    req = urllib.request.Request(job_url, data=body_bytes, method="POST")
                    req.add_header("Content-Type", content_type)
                else:
                    encoded_data = urllib.parse.urlencode(fields).encode("utf-8")
                    req = urllib.request.Request(job_url, data=encoded_data, method="POST")

                try:
                    with urllib.request.urlopen(req, timeout=15.0) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        job_id = res["job_id"]
                except Exception as e:
                    err_msg = f"Cannot reach Pose2maya service at {self.host}: {e}"
                    if on_error:
                        if mutils: mutils.executeInMainThreadWithResult(on_error, err_msg)
                        else: on_error(err_msg)
                    return

                # 2. Poll job status
                poll_url = f"{self.host}/api/jobs/{job_id}"
                completed_data = None
                for _ in range(240):  # 120 seconds max
                    time.sleep(0.5)
                    poll_req = urllib.request.Request(poll_url, method="GET")
                    with urllib.request.urlopen(poll_req, timeout=5.0) as p_resp:
                        j_status = json.loads(p_resp.read().decode("utf-8"))
                        if j_status["status"] == "succeeded":
                            completed_data = j_status
                            break
                        elif j_status["status"] == "failed":
                            err_msg = f"Inference job failed: {j_status.get('error', 'Unknown error')}"
                            if on_error:
                                if mutils: mutils.executeInMainThreadWithResult(on_error, err_msg)
                                else: on_error(err_msg)
                            return

                if not completed_data or "skeleton" not in completed_data:
                    err_msg = "Inference job timed out or returned no skeleton data."
                    if on_error:
                        if mutils: mutils.executeInMainThreadWithResult(on_error, err_msg)
                        else: on_error(err_msg)
                    return

                # 3. Main thread application callback with state protection (AUD-10)
                def _main_thread_apply():
                    if cmds is not None:
                        cur_scene = cmds.file(q=True, sceneName=True)
                        cur_scene_token = cmds.ls("time1", uuid=True)[0] if cmds.objExists("time1") else ""
                        if cur_scene != start_scene or (start_scene_token and cur_scene_token != start_scene_token):
                            err = "Application aborted: Scene changed while inference was running in background."
                            if on_error: on_error(err)
                            return

                        # Check target node UUIDs have not been deleted/recreated
                        for full_n, orig_uuid in target_node_uuids.items():
                            if not cmds.objExists(full_n):
                                err = f"Application aborted: Target node '{full_n}' no longer exists in scene."
                                if on_error: on_error(err)
                                return
                            cur_uuid = cmds.ls(full_n, uuid=True)[0]
                            if cur_uuid != orig_uuid:
                                err = f"Application aborted: Target node '{full_n}' was recreated with new UUID."
                                if on_error: on_error(err)
                                return

                        # Preserve target frame
                        cmds.currentTime(start_frame, update=True)

                    skel_data = completed_data["skeleton"]
                    pose_sample = load_pose_sample(skel_data)
                    skel_def = get_authoritative_mhr_skeleton_def()

                    retarget_result = retarget(pose_sample, skel_def, rig_profile_snap, retarget_profile_snap)
                    plan = prepare_write_plan(retarget_result, namespace=start_ns, auto_key=auto_key)

                    if not plan.can_apply:
                        err = f"Cannot apply pose: {'; '.join(plan.blockers)}"
                        if on_error: on_error(err)
                        return

                    session = PoseSession()
                    target_kf = start_frame if auto_key else None
                    report = session.commit(plan, keyframe=target_kf)

                    if report.status == "success":
                        if on_success: on_success(completed_data)
                    else:
                        if on_error: on_error(f"Pose commit failed: {'; '.join(report.messages)}")

                if mutils:
                    mutils.executeInMainThreadWithResult(_main_thread_apply)
                else:
                    _main_thread_apply()

            except Exception as e:
                err_msg = f"Unexpected client error: {str(e)}"
                if on_error:
                    if mutils: mutils.executeInMainThreadWithResult(on_error, err_msg)
                    else: on_error(err_msg)

        th = threading.Thread(target=_worker, daemon=True)
        th.start()
