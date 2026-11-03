"""
services.inference_service
==========================
Thread-safe, queued human 3D pose inference service for Pose2maya.
Resolves:
  - I01: Configurable checkpoint & MHR paths with auto-discovery
  - I03: Separates inference from heavy multi-format exports
  - I04: Mutex-guarded serial inference queue preventing concurrent estimator corruption
  - I05: Explicit device handling
"""

import os
import sys
import json
import time
import uuid
import queue
import threading
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Sequence

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class InferenceJob:
    job_id: str
    image_path: str
    bbox: Optional[List[float]] = None  # [x, y, w, h]
    export_fbx: bool = False
    export_bvh: bool = False
    export_glb: bool = False
    render_multiview: bool = False
    generate_html: bool = False
    status: str = "queued"  # "queued", "running", "succeeded", "failed"
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    started_time: Optional[float] = None
    latency_seconds: Optional[float] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class InferenceService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InferenceService, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        checkpoint_path: Optional[str] = None,
        mhr_path: Optional[str] = None,
        device: str = "cuda",
        fake_mode: bool = False
    ):
        if self._initialized:
            self.fake_mode = fake_mode
            return
        self._initialized = True

        self.device = device
        self.fake_mode = fake_mode
        self.runner = None
        self.runner_lock = threading.Lock()
        self.job_queue: queue.Queue[InferenceJob] = queue.Queue()
        self.jobs: Dict[str, InferenceJob] = {}

        # Resolve paths
        self.checkpoint_path = checkpoint_path or self._find_path(
            os.path.join(REPO_ROOT, "checkpoints", "sam-3d-body-dinov3", "model.ckpt"),
            r"D:\sam-3d-body\checkpoints\sam-3d-body-dinov3\model.ckpt"
        )
        self.mhr_path = mhr_path or self._find_path(
            os.path.join(REPO_ROOT, "checkpoints", "sam-3d-body-dinov3", "assets", "mhr_model.pt"),
            r"D:\sam-3d-body\checkpoints\sam-3d-body-dinov3\assets\mhr_model.pt"
        )

        # Worker thread for serialized queue processing
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def _find_path(self, preferred: str, fallback: str) -> str:
        if os.path.exists(preferred):
            return preferred
        if os.path.exists(fallback):
            return fallback
        return preferred

    def _lazy_init_runner(self):
        """Initializes SAM3D runner lazily upon first job."""
        if self.runner is not None or self.fake_mode:
            return

        with self.runner_lock:
            if self.runner is not None:
                return
            from sam3d_cli import SAM3DStandaloneRunner
            print(f"[InferenceService] Lazy loading model onto {self.device}...")
            self.runner = SAM3DStandaloneRunner(
                checkpoint_path=self.checkpoint_path,
                mhr_path=self.mhr_path,
                device=self.device
            )
            print("[InferenceService] Model loaded successfully.")

    def submit_job(
        self,
        image_path: str,
        bbox: Optional[Sequence[float]] = None,
        export_fbx: bool = False,
        export_bvh: bool = False,
        export_glb: bool = False,
        render_multiview: bool = False,
        generate_html: bool = False
    ) -> InferenceJob:
        job_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
        job = InferenceJob(
            job_id=job_id,
            image_path=image_path,
            bbox=list(bbox) if bbox is not None else None,
            export_fbx=export_fbx,
            export_bvh=export_bvh,
            export_glb=export_glb,
            render_multiview=render_multiview,
            generate_html=generate_html
        )
        self.jobs[job_id] = job
        self.job_queue.put(job)
        return job

    def get_job(self, job_id: str) -> Optional[InferenceJob]:
        return self.jobs.get(job_id)

    def _process_queue(self):
        while True:
            job = self.job_queue.get()
            try:
                job.status = "running"
                job.progress = 0.1
                now_t = time.time()
                job.started_time = now_t
                job.started_at = datetime.now().isoformat()

                if self.fake_mode:
                    # Synthetic test mode
                    time.sleep(0.05)
                    from pose_core.mhr_adapter import get_authoritative_mhr_skeleton_def
                    skel = get_authoritative_mhr_skeleton_def()
                    lat = round(time.time() - job.started_time, 3)
                    job.latency_seconds = lat

                    output_dir = os.path.join(REPO_ROOT, "outputs", "jobs", job.job_id)
                    os.makedirs(output_dir, exist_ok=True)
                    fake_v2_path = os.path.join(output_dir, f"{job.job_id}_pose_v2.json")
                    fake_legacy_path = os.path.join(output_dir, f"{job.job_id}_skeleton.json")
                    from pose_core.schema import PoseSample
                    fake_sample = PoseSample(
                        schema_version="2.0",
                        skeleton_id=skel.skeleton_id,
                        local_rotations=skel.rest_rotations,
                        world_positions=skel.rest_world_positions,
                        root_translation=[0.0, 0.0, 0.0],
                        root_rotation=[0.0, 0.0, 0.0, 1.0]
                    )
                    with open(fake_v2_path, "w", encoding="utf-8") as f:
                        json.dump(fake_sample.to_dict(), f, indent=2)
                    with open(fake_legacy_path, "w", encoding="utf-8") as f:
                        json.dump(fake_sample.to_dict(), f, indent=2)

                    job.result = {
                        "job_id": job.job_id,
                        "num_joints": skel.num_joints,
                        "status": "fake_success",
                        "pose_v2_json": fake_v2_path,
                        "skeleton_json": fake_legacy_path,
                        "latency_seconds": lat
                    }
                    job.status = "succeeded"
                    job.progress = 1.0
                    job.completed_at = datetime.now().isoformat()
                    continue

                self._lazy_init_runner()

                output_dir = os.path.join(REPO_ROOT, "outputs", "jobs", job.job_id)
                os.makedirs(output_dir, exist_ok=True)

                with self.runner_lock:
                    job.progress = 0.4
                    runner_res = self.runner.process_image(
                        image_path=job.image_path,
                        output_dir=output_dir,
                        bbox=job.bbox,
                        export_fbx=job.export_fbx,
                        export_bvh=job.export_bvh,
                        export_glb=job.export_glb,
                        render_multiview=job.render_multiview,
                        generate_html=job.generate_html
                    )

                if runner_res is None:
                    job.status = "failed"
                    job.error = "No human body detected in image."
                else:
                    lat = round(time.time() - job.started_time, 3)
                    job.latency_seconds = lat
                    runner_res["latency_seconds"] = lat
                    job.status = "succeeded"
                    job.progress = 1.0
                    job.result = runner_res
                    job.completed_at = datetime.now().isoformat()

            except Exception as e:
                job.status = "failed"
                job.error = str(e)
            finally:
                self.job_queue.task_done()
