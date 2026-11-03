"""
maya_scripts.pose_session
=========================
Manages transaction lifecycle for Maya character pose application:
  - Preview temporary overlay (idempotent, multiple previews maintain initial baseline)
  - Cancel & restoration to pre-preview scene state
  - Commit with selective keyframing and atomic error rollback
  - Single Maya Undo Chunk: one Ctrl+Z cleanly reverts to pre-preview state
"""

from typing import Dict, Any, Optional, List

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None

from pose_core.schema import WritePlan, ApplyReport


class PoseSession:
    """
    Session transaction manager enforcing safety guarantees (AUD-08):
    1. Repeated previews do not overwrite original scene baseline, and expanding channel sets are backed up (L04).
    2. Commit errors trigger automatic rollback of all modified attributes, removing any added keys at target frame and restoring time (L05).
    3. Committing after a preview leaves a clean undo baseline (Ctrl+Z reverts to original state).
    4. AnimCurve channels evaluate at current time upon cancel rather than restoring stale frame values (L07).
    """

    def __init__(self, cmd_module=None):
        self._cmd = cmd_module if cmd_module is not None else cmds
        self._baseline_backup: Dict[str, Any] = {}
        self._is_previewing: bool = False
        self._autokey_before: Optional[bool] = None

    @property
    def is_previewing(self) -> bool:
        return self._is_previewing

    def _record_baseline(self, attr: str):
        c = self._cmd
        has_curve = False
        if hasattr(c, "keyframe"):
            try:
                has_curve = (c.keyframe(attr, q=True, keyframeCount=True) or 0) > 0
            except Exception:
                has_curve = False
        val = c.getAttr(attr)
        self._baseline_backup[attr] = {
            "val": val,
            "has_curve": has_curve
        }

    def preview(self, plan: WritePlan) -> ApplyReport:
        """Temporarily applies WritePlan so user can inspect viewport."""
        report = ApplyReport()

        if not plan.can_apply:
            report.status = "failed"
            report.messages = list(plan.blockers)
            return report

        c = self._cmd
        if c is None:
            report.status = "preview"
            report.channels_modified = len(plan.channels)
            report.messages.append("Mock preview: cmds not available.")
            return report

        # Disable autokey during preview so preview does not write unwanted keys
        if self._autokey_before is None and hasattr(c, "autoKeyframe"):
            try:
                self._autokey_before = bool(c.autoKeyframe(q=True, state=True))
                c.autoKeyframe(state=False)
            except Exception:
                self._autokey_before = None

        # 1. Back up baseline scene values. Any channel not yet backed up gets recorded (L04 fix)
        for sw in plan.mode_switches:
            attr = sw["attr"]
            if c.objExists(attr) and attr not in self._baseline_backup:
                self._record_baseline(attr)

        for ch in plan.channels:
            full_attr = f"{ch['node']}.{ch['attr']}"
            if c.objExists(full_attr) and full_attr not in self._baseline_backup:
                self._record_baseline(full_attr)

        self._is_previewing = True

        # 2. Apply temporary values
        modified = 0
        for sw in plan.mode_switches:
            if c.objExists(sw["attr"]):
                c.setAttr(sw["attr"], sw["target"])
                modified += 1

        for ch in plan.channels:
            full_attr = f"{ch['node']}.{ch['attr']}"
            if c.objExists(full_attr):
                c.setAttr(full_attr, ch["target"])
                modified += 1

        report.status = "preview"
        report.channels_modified = modified
        report.messages.append(f"Previewing pose on {modified} channels.")
        return report

    def cancel(self) -> ApplyReport:
        """Restores scene attributes to the exact pre-preview baseline (L04, L07)."""
        report = ApplyReport()
        c = self._cmd

        if c is None:
            self._baseline_backup.clear()
            self._is_previewing = False
            report.status = "cancelled"
            report.messages.append("Mock cancel: cleared preview state.")
            return report

        if not self._is_previewing or not self._baseline_backup:
            report.status = "cancelled"
            report.messages.append("No active preview to cancel.")
            self._is_previewing = False
            return report

        restored = 0
        for attr, info in self._baseline_backup.items():
            if c.objExists(attr):
                try:
                    # L07 fix: If animated via animCurve, evaluate curve at current time
                    if isinstance(info, dict) and info.get("has_curve", False) and hasattr(c, "currentTime"):
                        curr_t = c.currentTime(q=True)
                        val_at_t = c.getAttr(attr, time=curr_t)
                        c.setAttr(attr, val_at_t)
                    else:
                        val = info["val"] if isinstance(info, dict) else info
                        c.setAttr(attr, val)
                    restored += 1
                except Exception:
                    pass

        self._baseline_backup.clear()
        self._is_previewing = False

        # Restore autokey state
        if self._autokey_before is not None and hasattr(c, "autoKeyframe"):
            try:
                c.autoKeyframe(state=self._autokey_before)
            except Exception:
                pass
            self._autokey_before = None

        report.status = "cancelled"
        report.channels_modified = restored
        report.messages.append(f"Cancelled preview and restored {restored} channels to initial state.")
        return report

    def commit(self, plan: WritePlan, keyframe: Optional[float] = None) -> ApplyReport:
        """
        Permanently writes pose channels and optionally sets keyframes.
        Enclosed in an atomic Maya undo chunk with exception rollback (L05).
        """
        report = ApplyReport()

        if not plan.can_apply:
            report.status = "failed"
            report.messages = list(plan.blockers)
            return report

        c = self._cmd
        if c is None:
            report.status = "success"
            report.channels_modified = len(plan.channels)
            report.keyframes_set = len(plan.channels) if keyframe is not None else 0
            self._baseline_backup.clear()
            self._is_previewing = False
            report.messages.append("Mock commit: cmds not available.")
            return report

        # Step 1: If previewing, restore baseline scene values BEFORE opening the undo chunk (AUD-08)
        if self._is_previewing and self._baseline_backup:
            for attr, info in self._baseline_backup.items():
                if c.objExists(attr):
                    try:
                        if isinstance(info, dict) and info.get("has_curve", False) and hasattr(c, "currentTime"):
                            curr_t = c.currentTime(q=True)
                            val_at_t = c.getAttr(attr, time=curr_t)
                            c.setAttr(attr, val_at_t)
                        else:
                            val = info["val"] if isinstance(info, dict) else info
                            c.setAttr(attr, val)
                    except Exception:
                        pass
            self._baseline_backup.clear()
            self._is_previewing = False

        if self._autokey_before is not None and hasattr(c, "autoKeyframe"):
            try:
                c.autoKeyframe(state=self._autokey_before)
            except Exception:
                pass
            self._autokey_before = None

        # Step 2: Take pre-commit snapshot for manual rollback on failure (L05)
        frame_before = c.currentTime(q=True) if hasattr(c, "currentTime") else 1.0
        pre_commit_snapshot = {}
        had_key_at_target = {}

        for sw in plan.mode_switches:
            attr = sw["attr"]
            if c.objExists(attr):
                pre_commit_snapshot[attr] = c.getAttr(attr)
                if keyframe is not None and hasattr(c, "keyframe"):
                    try:
                        cnt = c.keyframe(attr, time=(keyframe, keyframe), q=True, keyframeCount=True) or 0
                        had_key_at_target[attr] = cnt > 0
                    except Exception:
                        had_key_at_target[attr] = False

        for ch in plan.channels:
            full_attr = f"{ch['node']}.{ch['attr']}"
            if c.objExists(full_attr):
                pre_commit_snapshot[full_attr] = c.getAttr(full_attr)
                if keyframe is not None and hasattr(c, "keyframe"):
                    try:
                        cnt = c.keyframe(full_attr, time=(keyframe, keyframe), q=True, keyframeCount=True) or 0
                        had_key_at_target[full_attr] = cnt > 0
                    except Exception:
                        had_key_at_target[full_attr] = False

        # Step 3: Open Maya Undo Chunk
        if hasattr(c, "undoInfo"):
            c.undoInfo(openChunk=True, chunkName="Pose2Maya_Commit")

        modified_channels = []
        keys_set = 0
        try:
            if keyframe is not None and hasattr(c, "currentTime"):
                c.currentTime(keyframe, update=True)

            # Apply mode switches
            for sw in plan.mode_switches:
                attr = sw["attr"]
                if c.objExists(attr):
                    c.setAttr(attr, sw["target"])
                    if keyframe is not None and hasattr(c, "setKeyframe"):
                        c.setKeyframe(attr, time=keyframe)

            # Apply target channels
            for ch in plan.channels:
                full_attr = f"{ch['node']}.{ch['attr']}"
                if c.objExists(full_attr):
                    c.setAttr(full_attr, ch["target"])
                    modified_channels.append(ch)

            # Keyframe modified channels
            if keyframe is not None and modified_channels and hasattr(c, "setKeyframe"):
                for ch in modified_channels:
                    c.setKeyframe(ch["node"], attribute=ch["attr"], time=keyframe)
                    keys_set += 1

            report.status = "success"
            report.channels_modified = len(modified_channels)
            report.modified_list = [f"{ch['node']}.{ch['attr']}" for ch in modified_channels]
            report.keyframes_set = keys_set
            report.undo_available = True
            report.messages.append(f"Successfully applied pose to {len(modified_channels)} channels.")

        except Exception as e:
            # Independent error rollback to pre_commit_snapshot (AUD-08 & L05)
            # 1. Cut any newly created keys at target frame
            if keyframe is not None and hasattr(c, "cutKey"):
                for sw in plan.mode_switches:
                    attr = sw["attr"]
                    if not had_key_at_target.get(attr, False):
                        try:
                            c.cutKey(attr, time=(keyframe, keyframe), clear=True)
                        except Exception:
                            pass
                for ch in plan.channels:
                    full_attr = f"{ch['node']}.{ch['attr']}"
                    if not had_key_at_target.get(full_attr, False):
                        try:
                            c.cutKey(full_attr, time=(keyframe, keyframe), clear=True)
                        except Exception:
                            pass

            # 2. Restore pre-commit attribute values and pre-existing keyframe values
            for attr, val in pre_commit_snapshot.items():
                if c.objExists(attr):
                    try:
                        c.setAttr(attr, val)
                        if had_key_at_target.get(attr, False) and keyframe is not None and hasattr(c, "setKeyframe"):
                            c.setKeyframe(attr, time=keyframe, value=val)
                    except Exception:
                        pass

            # 3. Restore frame time
            if hasattr(c, "currentTime"):
                try:
                    c.currentTime(frame_before, update=True)
                except Exception:
                    pass

            report.status = "failed"
            report.messages.append(f"Execution error during commit (all changes rolled back): {str(e)}")

        finally:
            if hasattr(c, "undoInfo"):
                c.undoInfo(closeChunk=True)

        return report


class FakeCmds:
    """
    Lightweight mock of maya.cmds for unit testing transaction lifecycles and undo chunks.
    """
    def __init__(self):
        self.attrs: Dict[str, Any] = {}
        self.undo_chunks: List[Dict[str, Any]] = []
        self._current_chunk: Optional[Dict[str, Any]] = None
        self.keyframes: Dict[str, List[float]] = {}
        self.current_time_val: float = 1.0
        self.autokey_state: bool = False

    def autoKeyframe(self, state=None, q=False):
        if q:
            return self.autokey_state
        if state is not None:
            self.autokey_state = bool(state)
        return self.autokey_state

    def keyframe(self, attr: str, time=None, q=False, keyframeCount=False, timeChange=False):
        keys = self.keyframes.get(attr, [])
        if time is not None:
            t_start, t_end = time
            keys = [t for t in keys if t_start <= t <= t_end]
        if keyframeCount:
            return len(keys)
        if timeChange:
            return keys
        return keys

    def cutKey(self, attr: str, time=None, clear=True):
        if attr in self.keyframes:
            if time is not None:
                t_start, t_end = time
                self.keyframes[attr] = [t for t in self.keyframes[attr] if not (t_start <= t <= t_end)]
            else:
                self.keyframes[attr] = []

    def objExists(self, name: str) -> bool:
        if name in self.attrs:
            return True
        node = name.split(".")[0]
        return any(k.startswith(f"{node}.") or k == node for k in self.attrs)

    def getAttr(self, attr: str, time=None) -> Any:
        return self.attrs.get(attr, 0.0)

    def setAttr(self, attr: str, val: Any) -> None:
        if self._current_chunk is not None and attr not in self._current_chunk:
            self._current_chunk[attr] = self.attrs.get(attr, 0.0)
        self.attrs[attr] = val

    def undoInfo(self, openChunk: bool = False, closeChunk: bool = False, **kwargs) -> None:
        if openChunk:
            self._current_chunk = {}
        elif closeChunk:
            if self._current_chunk is not None:
                self.undo_chunks.append(self._current_chunk)
                self._current_chunk = None

    def undo(self) -> None:
        if self.undo_chunks:
            chunk = self.undo_chunks.pop()
            for attr, val in chunk.items():
                self.attrs[attr] = val

    def setKeyframe(self, node_or_attr: str, attribute: Optional[str] = None, time: Optional[float] = None, **kwargs) -> None:
        attr = f"{node_or_attr}.{attribute}" if attribute else node_or_attr
        t = time if time is not None else self.current_time_val
        if attr not in self.keyframes:
            self.keyframes[attr] = []
        self.keyframes[attr].append(float(t))

    def currentTime(self, time: Optional[float] = None, q: bool = False, update: bool = False) -> float:
        if q:
            return self.current_time_val
        if time is not None:
            self.current_time_val = float(time)
        return self.current_time_val

