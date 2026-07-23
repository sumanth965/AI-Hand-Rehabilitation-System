"""
Clinical Intelligence: Movement Quality Evaluation & Advanced Compensation Detection.
"""

import math
import time
import numpy as np
from collections import deque
from datetime import datetime


class KinematicQualityTracker:
    """Calculates live smoothness, accuracy, ROM score, hold stability, and overall Quality Score."""
    
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.positions = []
        self.velocities = []
        self.jerk_values = []
        self.hold_deviations = []
        self.accuracy_hits = 0
        self.accuracy_attempts = 0
        self.rom_angles = []
        self.hold_window = []
        
    def update(self, hand_data, is_active_session=True, active_hold=False):
        if not is_active_session or not hand_data or hand_data.index_tip is None:
            return
            
        pos = hand_data.index_tip
        self.positions.append(pos)
        
        # Calculate velocity & jerk (for Smoothness)
        if len(self.positions) >= 2:
            p1 = self.positions[-2]
            p2 = self.positions[-1]
            vel = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            self.velocities.append(vel)
            
            if len(self.velocities) >= 2:
                accel = self.velocities[-1] - self.velocities[-2]
                if len(self.jerk_values) > 0:
                    jerk = abs(accel - self.jerk_values[-1])
                    self.jerk_values.append(jerk)
                else:
                    self.jerk_values.append(abs(accel))
                    
        # Hold Stability tracking
        if active_hold:
            self.hold_window.append(pos)
            if len(self.hold_window) >= 15:
                xs = [p[0] for p in self.hold_window]
                ys = [p[1] for p in self.hold_window]
                sd_x = np.std(xs) if len(xs) > 1 else 0.0
                sd_y = np.std(ys) if len(ys) > 1 else 0.0
                dev = math.hypot(sd_x, sd_y)
                self.hold_deviations.append(dev)
                self.hold_window.clear()
        else:
            self.hold_window.clear()
            
        # ROM angles
        if hand_data.knuckle_angles and len(hand_data.knuckle_angles) > 0:
            self.rom_angles.append(hand_data.knuckle_angles[0])
            
    def record_accuracy(self, hits, attempts):
        self.accuracy_hits = hits
        self.accuracy_attempts = attempts
        
    def calculate_metrics(self, calibrated_max_rom=90.0) -> dict:
        # 1. Smoothness Score (0-100)
        if self.jerk_values:
            avg_jerk = sum(self.jerk_values) / len(self.jerk_values)
            smoothness = max(0.0, min(100.0, 100.0 * math.exp(-0.08 * avg_jerk)))
        else:
            smoothness = 80.0
            
        # 2. Movement Accuracy (0-100)
        if self.accuracy_attempts > 0:
            accuracy = (self.accuracy_hits / self.accuracy_attempts) * 100.0
            accuracy = max(0.0, min(100.0, accuracy))
        else:
            accuracy = 85.0
            
        # 3. ROM Score (0-100)
        if self.rom_angles:
            avg_rom = sum(self.rom_angles) / len(self.rom_angles)
            rom_target = max(45.0, calibrated_max_rom)
            rom_score = (avg_rom / rom_target) * 100.0
            rom_score = max(0.0, min(100.0, rom_score))
        else:
            rom_score = 75.0
            
        # 4. Hold Stability Score (0-100)
        if self.hold_deviations:
            avg_dev = sum(self.hold_deviations) / len(self.hold_deviations)
            stability = max(0.0, min(100.0, 100.0 * math.exp(-0.04 * avg_dev)))
        else:
            stability = 90.0
            
        overall_score = (smoothness + accuracy + rom_score + stability) / 4.0
        
        if overall_score >= 90:
            rating = "Excellent"
        elif overall_score >= 75:
            rating = "Good"
        elif overall_score >= 50:
            rating = "Moderate"
        else:
            rating = "Needs Improvement"
            
        return {
            "smoothness": round(smoothness, 1),
            "accuracy": round(accuracy, 1),
            "rom": round(rom_score, 1),
            "stability": round(stability, 1),
            "overall": round(overall_score, 1),
            "rating": rating
        }


class AdvancedCompensationDetector:
    """Analyses hand landmark translations to detect shoulder/arm compensation and logs events."""
    
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.prev_wrist = None
        self.prev_rot = None
        self.wrist_velocities = deque(maxlen=45)
        self.rot_velocities = deque(maxlen=45)
        self.lateral_movements = deque(maxlen=45)
        self.jerk_buffer = deque(maxlen=45)
        self.events = []
        self.last_triggered_time = 0.0
        self.warning_text = ""
        
    def analyze(self, hand_data, current_level=1) -> tuple[bool, str, str, float]:
        if not hand_data or hand_data.wrist is None:
            return False, "", "", 0.0
            
        wrist = hand_data.wrist
        rot = hand_data.wrist_rotation_angle
        now = time.time()
        
        if now - self.last_triggered_time < 3.0:
            return False, "", "", 0.0
            
        detected = False
        comp_type = ""
        desc = ""
        severity = 0.0
        
        if self.prev_wrist is not None:
            disp = math.hypot(wrist[0] - self.prev_wrist[0], wrist[1] - self.prev_wrist[1])
            self.wrist_velocities.append(disp)
            
            # 1. Sudden Landmark Translation
            if disp > 55.0 and len(self.wrist_velocities) > 5:
                detected = True
                comp_type = "Sudden Landmark Translation"
                desc = "Rotate your forearm instead of shifting your entire arm suddenly."
                severity = min(1.0, disp / 120.0)
                
            # 2. Inconsistent Wrist Movement
            if not detected and len(self.wrist_velocities) >= 15:
                vel_std = np.std(list(self.wrist_velocities))
                if vel_std > 18.0:
                    detected = True
                    comp_type = "Inconsistent Wrist Movement"
                    desc = "Maintain a steady, controlled motion. Avoid jerking."
                    severity = min(1.0, vel_std / 35.0)
                    
            # 3. Unstable Trajectory
            if not detected and len(self.wrist_velocities) >= 3:
                jerk = abs(self.wrist_velocities[-1] - self.wrist_velocities[-2])
                self.jerk_buffer.append(jerk)
                if len(self.jerk_buffer) >= 15:
                    avg_jerk = np.mean(list(self.jerk_buffer))
                    if avg_jerk > 12.0:
                        detected = True
                        comp_type = "Unstable Trajectory"
                        desc = "Keep your wrist steady and trace along a smooth path."
                        severity = min(1.0, avg_jerk / 30.0)
                        
            # 5. Excessive Lateral Movement
            if not detected and current_level in [1, 5, 7]:
                lat_disp = abs(wrist[0] - self.prev_wrist[0])
                self.lateral_movements.append(lat_disp)
                if len(self.lateral_movements) >= 20:
                    avg_lat = np.mean(list(self.lateral_movements))
                    if avg_lat > 15.0:
                        detected = True
                        comp_type = "Excessive Lateral Movement"
                        desc = "Rotate your wrist or bend fingers directly. Avoid shifting sideways."
                        severity = min(1.0, avg_lat / 35.0)
                        
        # 4. Abnormal Rotation Speed
        if not detected and self.prev_rot is not None:
            d_rot = abs(rot - self.prev_rot)
            if d_rot > 180:
                d_rot = 360 - d_rot
            self.rot_velocities.append(d_rot)
            
            if d_rot > 35.0 and len(self.rot_velocities) > 5:
                detected = True
                comp_type = "Abnormal Rotation Speed"
                desc = "Control your forearm rotation speed. Move slowly and deliberately."
                severity = min(1.0, d_rot / 70.0)
                
        self.prev_wrist = wrist
        self.prev_rot = rot
        
        if detected:
            self.last_triggered_time = now
            self.events.append({
                "timestamp": datetime.now().isoformat(),
                "type": comp_type,
                "severity": round(severity, 2)
            })
            self.warning_text = f"Compensation Detected: {desc}"
            
        return detected, comp_type, desc, severity
