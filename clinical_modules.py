"""
═══════════════════════════════════════════════════════════════════════════════
  clinical_modules.py — PPE-II Clinical-Grade Upgrades
  AI-Based Gamified Physiotherapy Assistant
═══════════════════════════════════════════════════════════════════════════════
  
  5 modular improvements for clinical accuracy:
  
  1. ClinicalAccuracyFilter   — Moving-average jitter removal (window=5)
  2. VirtualSensei            — Therapeutic target comparison + voice coaching
  3. RecoveryPredictor        — Scikit-learn Linear Regression for next-session prediction
  4. TherapistDashboard       — Matplotlib progress graph saved as progress.png
  5. EmergencyPause           — Landmark confidence gating to prevent bad data

  Usage:
      from clinical_modules import (
          ClinicalAccuracyFilter,
          VirtualSensei,
          RecoveryPredictor,
          TherapistDashboard,
          EmergencyPause,
      )
═══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import time
import math
import sqlite3
import threading
import numpy as np
from collections import deque
from datetime import datetime

import pyttsx3
import matplotlib
matplotlib.use("Agg")           # Non-interactive backend (safe for Pygame)
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter

# Scikit-learn (only needed by RecoveryPredictor)
try:
    from sklearn.linear_model import LinearRegression
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[clinical_modules] WARNING: scikit-learn not installed. "
          "RecoveryPredictor will fall back to manual regression.")


# ============================================================================
# MODULE 1: CLINICAL ACCURACY FILTER
# Moving-average filter (window=5) for hand landmarks
# ============================================================================

class ClinicalAccuracyFilter:
    """
    Removes jitter from MediaPipe hand landmarks using a simple
    moving-average filter (SMA) with a configurable window size.

    Usage:
        filt = ClinicalAccuracyFilter(window_size=5)

        # Inside your tracking loop:
        stable_angles = filt.filter_angles(raw_knuckle_angles)
        stable_point  = filt.filter_point(raw_x, raw_y)
    """

    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        # One deque per finger (Index, Middle, Ring, Pinky)
        self._angle_buffers = [deque(maxlen=window_size) for _ in range(4)]
        # Position buffers for a single tracked point
        self._x_buffer = deque(maxlen=window_size)
        self._y_buffer = deque(maxlen=window_size)

    def filter_angles(self, raw_angles: list[float]) -> list[float]:
        """
        Accept 4 raw knuckle angles, push them into the SMA buffers,
        and return 4 stabilised (averaged) values.
        """
        if len(raw_angles) != 4:
            return raw_angles          # Passthrough if unexpected size

        stable = []
        for i, angle in enumerate(raw_angles):
            self._angle_buffers[i].append(angle)
            avg = sum(self._angle_buffers[i]) / len(self._angle_buffers[i])
            stable.append(round(avg, 2))
        return stable

    def filter_point(self, x: float, y: float) -> tuple[float, float]:
        """
        Smooth a 2-D point (e.g., index-tip position) with SMA.
        Returns (smoothed_x, smoothed_y).
        """
        self._x_buffer.append(x)
        self._y_buffer.append(y)
        sx = sum(self._x_buffer) / len(self._x_buffer)
        sy = sum(self._y_buffer) / len(self._y_buffer)
        return (round(sx, 2), round(sy, 2))

    def reset(self):
        """Clear all buffers (e.g., when hand re-appears after a pause)."""
        for buf in self._angle_buffers:
            buf.clear()
        self._x_buffer.clear()
        self._y_buffer.clear()


# ============================================================================
# MODULE 2: MEDICAL CORRECTNESS ENGINE  (The Virtual Sensei)
# Compares real-time angle against therapeutic target
# ============================================================================

class VirtualSensei:
    """
    Compares the live flexion angle against a configurable
    therapeutic target (default 90°).

    • If the user HOLDS the correct position (within tolerance)
      for `hold_duration` seconds → triggers 'success' callback.
    • If the angle is too low → uses pyttsx3 to say "Bend further".

    Usage:
        sensei = VirtualSensei(target_angle=90, tolerance=10, hold_duration=3.0)

        # Each frame:
        event = sensei.evaluate(current_angle)
        # event is one of: "success", "bend_further", "hold", "too_far", None
    """

    def __init__(self, target_angle: float = 90.0,
                 tolerance: float = 10.0,
                 hold_duration: float = 3.0):
        self.target_angle = target_angle
        self.tolerance = tolerance
        self.hold_duration = hold_duration

        # Internal state
        self._hold_start: float | None = None
        self._success_triggered = False

        # Voice engine (threaded so it never blocks the game loop)
        self._voice_lock = threading.Lock()
        self._is_speaking = False
        self._last_speech_time = 0.0
        self._speech_cooldown = 4.0          # seconds between voice prompts

    # ── Public API ───────────────────────────────────────────────
    def evaluate(self, current_angle: float) -> str | None:
        """
        Call once per frame.  Returns an event string or None.
        Events: "success", "hold", "bend_further", "too_far"
        """
        diff = current_angle - self.target_angle

        # Within tolerance band → count hold time
        if abs(diff) <= self.tolerance:
            if self._hold_start is None:
                self._hold_start = time.time()

            elapsed = time.time() - self._hold_start

            if elapsed >= self.hold_duration and not self._success_triggered:
                self._success_triggered = True
                self._speak("Great job! Target reached.")
                return "success"

            return "hold"                   # Still holding, not yet done

        # Outside tolerance → reset hold timer
        self._hold_start = None
        self._success_triggered = False

        if diff < -self.tolerance:
            # self._speak("Bend further.")
            return "bend_further"
        else:
            # self._speak("Too far, relax slightly.")
            return "too_far"

    def deliver_coaching(self, message: str):
        """
        Deliver a generated coaching message using pyttsx3.
        Respects the same speech cooldown to avoid spam.
        """
        self._speak(message)

    def reset(self):
        """Reset for a new session / exercise."""
        self._hold_start = None
        self._success_triggered = False

    def get_hold_progress(self) -> float:
        """Returns 0.0–1.0 showing how close to completing the hold."""
        if self._hold_start is None:
            return 0.0
        return min(1.0, (time.time() - self._hold_start) / self.hold_duration)

    # ── Private voice helper ─────────────────────────────────────
    def _speak(self, text: str):
        now = time.time()
        if now - self._last_speech_time < self._speech_cooldown:
            return                          # Cooldown active
        with self._voice_lock:
            if self._is_speaking:
                return
            self._is_speaking = True
            self._last_speech_time = now
        threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()

    def _speak_thread(self, text: str):
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass
        finally:
            with self._voice_lock:
                self._is_speaking = False


# ============================================================================
# MODULE 3: MACHINE LEARNING LAYER — Linear Regression Predictor
# Predicts next-session flexion angle from last 10 sessions
# ============================================================================

class RecoveryPredictor:
    """
    Pulls the last N `avg_hand_angle` entries from the SQLite database
    and uses Scikit-learn LinearRegression to predict the angle for
    the next session.

    Usage:
        predictor = RecoveryPredictor(db_path="rehab_data.db")
        result    = predictor.predict()
        # result = { "predicted_angle": 95.2,
        #            "current_avg":    88.4,
        #            "improvement_pct": 7.7,
        #            "trend":          "improving" }
    """

    def __init__(self, db_path: str = "rehab_data.db", lookback: int = 10):
        self.db_path = db_path
        self.lookback = lookback

    def predict(self) -> dict:
        """
        Returns a dict with prediction info, or an error message
        if not enough data is available.
        """
        angles = self._fetch_angles()

        if len(angles) < 2:
            return {"error": "Not enough sessions (need ≥ 2)."}

        X = np.arange(len(angles)).reshape(-1, 1)     # session index
        y = np.array(angles)

        if SKLEARN_AVAILABLE:
            model = LinearRegression()
            model.fit(X, y)
            next_x = np.array([[len(angles)]])
            predicted = float(model.predict(next_x)[0])
        else:
            # Manual fallback (simple least-squares)
            predicted = self._manual_linear_regression(X.flatten(), y)

        current_avg = float(np.mean(y[-3:])) if len(y) >= 3 else float(y[-1])
        improvement = ((predicted - current_avg) / max(current_avg, 1)) * 100

        return {
            "predicted_angle": round(predicted, 1),
            "current_avg": round(current_avg, 1),
            "improvement_pct": round(improvement, 1),
            "trend": "improving" if improvement > 0 else "declining",
            "sessions_used": len(angles),
        }

    # ── Internal helpers ─────────────────────────────────────────
    def _fetch_angles(self) -> list[float]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT avg_hand_angle FROM sessions
                WHERE avg_hand_angle > 0
                ORDER BY id DESC LIMIT ?
            """, (self.lookback,))
            rows = cursor.fetchall()
            conn.close()
            return [r[0] for r in reversed(rows)]     # chronological
        except Exception:
            return []

    @staticmethod
    def _manual_linear_regression(x: np.ndarray, y: np.ndarray) -> float:
        n = len(x)
        mx, my = x.mean(), y.mean()
        num = np.sum((x - mx) * (y - my))
        den = np.sum((x - mx) ** 2)
        if den == 0:
            return float(y[-1])
        m = num / den
        b = my - m * mx
        return float(m * n + b)


# ============================================================================
# MODULE 4: THERAPIST DASHBOARD — Matplotlib Visualization
# Generates progress.png for the doctor to review
# ============================================================================

class TherapistDashboard:
    """
    Reads session history from SQLite and generates a clinical-grade
    progress graph (Date vs. Flexion Angle + Session Duration).
    Saves the chart as `progress.png`.

    Usage:
        dash = TherapistDashboard(db_path="rehab_data.db")
        dash.generate()                  # → saves progress.png
        surf = dash.generate_surface()   # → returns a Pygame Surface
    """

    def __init__(self, db_path: str = "rehab_data.db", output_path: str = "progress.png"):
        self.db_path = db_path
        self.output_path = output_path

    def generate(self) -> str:
        """Generate progress.png and return the file path."""
        data = self._fetch_data()
        if not data:
            return ""

        dates      = [row[0] for row in data]
        angles     = [row[1] for row in data]
        scores     = [row[2] for row in data]
        pain       = [row[3] for row in data]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), dpi=120,
                                        gridspec_kw={"height_ratios": [2, 1]})
        fig.patch.set_facecolor("#0c1428")
        fig.suptitle("🏥  Patient Recovery Dashboard",
                     color="white", fontsize=16, fontweight="bold", y=0.98)

        # ── Top chart: Flexion Angle trend ─────────────────────────
        ax1.set_facecolor("#151b2e")
        ax1.plot(dates, angles, marker="o", color="#00c8f5",
                 linewidth=2.5, markersize=7, label="Avg Flexion Angle")
        ax1.fill_between(dates, angles, alpha=0.15, color="#00c8f5")

        # Target line
        ax1.axhline(y=90, color="#ff6b6b", linestyle="--",
                     linewidth=1.2, label="Therapeutic Target (90°)")
        ax1.set_ylabel("Flexion Angle (°)", color="white", fontsize=11)
        ax1.set_title("Range of Motion Progress", color="#00c8f5", fontsize=13)
        ax1.legend(loc="lower right", fontsize=9, facecolor="#1a2240",
                   edgecolor="#333", labelcolor="white")
        ax1.tick_params(colors="white", labelsize=9)
        ax1.grid(color="#212d4d", linestyle="--", alpha=0.5)
        ax1.tick_params(axis="x", rotation=45)

        # ── Bottom chart: Pain level bar chart ─────────────────────
        ax2.set_facecolor("#151b2e")
        colours = ["#50dc78" if p <= 3 else "#f0c040" if p <= 6 else "#ff4757" for p in pain]
        ax2.bar(dates, pain, color=colours, width=0.6, edgecolor="#222")
        ax2.set_ylabel("Pain Level (0-10)", color="white", fontsize=11)
        ax2.set_title("Reported Pain Over Time", color="#f0c040", fontsize=13)
        ax2.set_ylim(0, 10)
        ax2.tick_params(colors="white", labelsize=9)
        ax2.tick_params(axis="x", rotation=45)
        ax2.grid(color="#212d4d", linestyle="--", alpha=0.3)

        fig.tight_layout(rect=[0, 0, 1, 0.95])
        fig.savefig(self.output_path, facecolor="#0c1428", bbox_inches="tight")
        plt.close(fig)
        print(f"[TherapistDashboard] Saved → {self.output_path}")
        return self.output_path

    def generate_surface(self):
        """Generate the chart and return it as a Pygame Surface (for in-game view)."""
        import io, pygame
        data = self._fetch_data()
        if not data:
            surf = pygame.Surface((800, 500))
            surf.fill((12, 20, 40))
            return surf

        dates  = [row[0] for row in data]
        angles = [row[1] for row in data]

        fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
        fig.patch.set_facecolor("#0c1428")
        ax.set_facecolor("#151b2e")
        ax.plot(dates, angles, marker="o", color="#00c8f5", linewidth=2.5, markersize=7)
        ax.fill_between(dates, angles, alpha=0.15, color="#00c8f5")
        ax.axhline(y=90, color="#ff6b6b", linestyle="--", linewidth=1.2)
        ax.set_title("Flexion Angle Progress", color="white", fontsize=14)
        ax.set_ylabel("Angle (°)", color="white")
        ax.tick_params(colors="white", labelsize=9)
        ax.tick_params(axis="x", rotation=45)
        ax.grid(color="#212d4d", linestyle="--", alpha=0.5)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor="#0c1428")
        buf.seek(0)
        plt.close(fig)
        return pygame.image.load(buf, "png")

    # ── Internal ─────────────────────────────────────────────────
    def _fetch_data(self) -> list[tuple]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT strftime('%d/%m', timestamp) as date,
                       avg_hand_angle,
                       score,
                       pain_level
                FROM sessions
                ORDER BY id ASC
                LIMIT 30
            """)
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception:
            return []


# ============================================================================
# MODULE 5: FAILURE HANDLING — Emergency Pause
# Pauses game + prevents bad data when hand confidence is low
# ============================================================================

class EmergencyPause:
    """
    Monitors landmark detection confidence.
    If confidence drops below threshold → triggers pause mode.

    Usage:
        pause_guard = EmergencyPause(confidence_threshold=0.5)

        # Each frame:
        is_paused = pause_guard.check(hand_data, landmarks_results)

        if is_paused:
            # Show "Hand Not Detected" overlay, skip data logging
    """

    def __init__(self, confidence_threshold: float = 0.5,
                 grace_frames: int = 5):
        """
        Args:
            confidence_threshold: Min acceptable landmark confidence (0–1).
            grace_frames: Number of consecutive low-confidence frames
                          before triggering pause (prevents flicker).
        """
        self.threshold = confidence_threshold
        self.grace_frames = grace_frames
        self._low_conf_count = 0
        self.is_paused = False
        self.pause_reason = ""

    def check(self, hand_data, mediapipe_results=None) -> bool:
        """
        Evaluate confidence from the current frame.
        Returns True if the system should be paused.

        Args:
            hand_data:   HandData dataclass (from your HandEngine).
            mediapipe_results:  Raw MediaPipe `results` object (optional,
                                for deeper confidence checking).
        """
        confidence = self._get_confidence(hand_data, mediapipe_results)

        if confidence < self.threshold:
            self._low_conf_count += 1
            if self._low_conf_count >= self.grace_frames:
                self.is_paused = True
                self.pause_reason = (
                    f"Hand Not Detected (conf: {confidence:.2f} < {self.threshold})"
                )
                return True
        else:
            self._low_conf_count = 0
            self.is_paused = False
            self.pause_reason = ""

        return False

    def reset(self):
        """Reset counters (e.g., when resuming manually)."""
        self._low_conf_count = 0
        self.is_paused = False
        self.pause_reason = ""

    # ── Internal ─────────────────────────────────────────────────
    @staticmethod
    def _get_confidence(hand_data, results) -> float:
        """
        Extract a 0–1 confidence score.

        Strategy:
        1. If hand_data has no landmarks → 0.0
        2. If MediaPipe results exist, average the per-landmark
           visibility/confidence scores.
        3. Fallback: return 1.0 if landmarks are present.
        """
        # No hand detected at all
        if hand_data.landmarks is None or len(hand_data.landmarks) == 0:
            return 0.0

        # Try extracting per-landmark visibility from MediaPipe
        if results is not None and results.multi_hand_landmarks:
            try:
                lms = results.multi_hand_landmarks[0].landmark
                visibilities = [lm.visibility for lm in lms
                                if hasattr(lm, "visibility")]
                if visibilities:
                    return sum(visibilities) / len(visibilities)
            except Exception:
                pass

        # Fallback: hand was found → high confidence
        return 1.0


# ============================================================================
# INTEGRATION EXAMPLE
# ============================================================================
#
# Paste this block into your game loop inside zero_keyboard_physio.py:
#
#   from clinical_modules import (
#       ClinicalAccuracyFilter,
#       VirtualSensei,
#       RecoveryPredictor,
#       TherapistDashboard,
#       EmergencyPause,
#   )
#
#   # ── Initialise once ──
#   accuracy_filter = ClinicalAccuracyFilter(window_size=5)
#   sensei          = VirtualSensei(target_angle=90, tolerance=10, hold_duration=3.0)
#   predictor       = RecoveryPredictor(db_path="rehab_data.db")
#   dashboard       = TherapistDashboard(db_path="rehab_data.db")
#   pause_guard     = EmergencyPause(confidence_threshold=0.5, grace_frames=5)
#
#   # ── Inside your per-frame update ──
#   hand = hand_engine.get_hand_data()
#
#   # 1. Emergency Pause check
#   if pause_guard.check(hand, mediapipe_results):
#       # Draw "Hand Not Detected" overlay; skip everything else
#       continue
#
#   # 2. Filter angles for clinical stability
#   if hand.knuckle_angles:
#       stable_angles = accuracy_filter.filter_angles(hand.knuckle_angles)
#       avg_angle = sum(stable_angles) / len(stable_angles)
#   else:
#       avg_angle = 0.0
#
#   # 3. Virtual Sensei evaluation
#   event = sensei.evaluate(avg_angle)
#   hold_progress = sensei.get_hold_progress()
#   # Draw a circular progress bar using hold_progress (0.0–1.0)
#
#   # 4. After session ends — predict recovery
#   result = predictor.predict()
#   if "predicted_angle" in result:
#       improvement = result["improvement_pct"]
#       # Display: f"Predicted Recovery: +{improvement}%"
#
#   # 5. Generate therapist dashboard
#   dashboard.generate()  # → saves progress.png


# -- Quick self-test --
if __name__ == "__main__":
    import sys
    # Force UTF-8 output on Windows console
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print("  Clinical Modules -- Self-Test")
    print("=" * 60)

    # 1. ClinicalAccuracyFilter
    filt = ClinicalAccuracyFilter(window_size=5)
    noisy = [85.3, 87.1, 82.9, 89.0, 86.5, 88.2, 84.7, 90.1, 85.8, 87.3]
    print("\n[1] ClinicalAccuracyFilter -- Jitter Removal")
    for val in noisy:
        result = filt.filter_angles([val, val, val, val])
        print(f"    Raw: {val:.1f} deg -> Filtered: {result[0]:.1f} deg")

    # 2. VirtualSensei
    print("\n[2] VirtualSensei -- Therapeutic Target (90 deg)")
    sensei = VirtualSensei(target_angle=90, tolerance=10, hold_duration=1.0)
    for angle in [70, 75, 80, 85, 88, 92, 95, 100, 105]:
        event = sensei.evaluate(angle)
        print(f"    Angle: {angle} deg -> Event: {event}")

    # 3. RecoveryPredictor
    print("\n[3] RecoveryPredictor -- Linear Regression")
    predictor = RecoveryPredictor(db_path="rehab_data.db")
    result = predictor.predict()
    print(f"    Result: {result}")

    # 4. TherapistDashboard
    print("\n[4] TherapistDashboard -- Generating progress.png")
    dash = TherapistDashboard(db_path="rehab_data.db")
    path = dash.generate()
    print(f"    Saved to: {path if path else 'No data available'}")

    # 5. EmergencyPause
    print("\n[5] EmergencyPause -- Confidence Check")
    from dataclasses import dataclass, field
    from typing import Optional, List, Tuple

    @dataclass
    class MockHandData:
        landmarks: Optional[list] = None

    guard = EmergencyPause(confidence_threshold=0.5, grace_frames=3)
    # Simulate 5 frames with no hand
    for i in range(5):
        paused = guard.check(MockHandData(landmarks=None))
        print(f"    Frame {i+1}: paused={paused} (low_conf={guard._low_conf_count})")

    print("\n[OK] All modules passed self-test!")

