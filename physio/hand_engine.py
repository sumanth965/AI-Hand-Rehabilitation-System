"""
Hand Tracking Engine for the Zero-Keyboard AI Physiotherapy System.
Uses MediaPipe for real-time hand tracking with gesture recognition.
"""

import cv2
import mediapipe as mp
import numpy as np
import threading
import time
import math
from collections import deque
from typing import Optional

from physio.constants import GAME_AREA_WIDTH, WINDOW_HEIGHT, SMOOTHING_WINDOW
from physio.utils import weighted_average
from physio.models import HandData
from physio.camera import WebcamStream


class HandEngine:
    """Hand tracking with gesture recognition"""
    
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.6
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        self.webcam = None
        self.hand_data = HandData()
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Calibration defaults
        self.fist_threshold = 0.12
        self.calibration_active = False
        self.calibrated_max_extension = 170.0
        
        # Smoothing buffers (weighted average)
        self.index_x_buffer = deque(maxlen=SMOOTHING_WINDOW)
        self.index_y_buffer = deque(maxlen=SMOOTHING_WINDOW)
        self.palm_x_buffer = deque(maxlen=SMOOTHING_WINDOW)
        self.palm_y_buffer = deque(maxlen=SMOOTHING_WINDOW)
        
        self.mirrored_frame = None
        
    def start(self):
        try:
            self.webcam = WebcamStream(src=0).start()
        except Exception as e:
            print(f"Camera initialization failed: {e}")
            self.webcam = None
            
        self.running = True
        self.thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self.thread.start()
        
    def _tracking_loop(self):
        while self.running:
            grabbed, frame = self.webcam.read()
            if not grabbed or frame is None:
                continue
            
            # Mirror for natural interaction
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_frame)
            
            # Draw landmarks and process data
            annotated = frame.copy()
            new_hand_data = HandData()
            
            if results.multi_hand_landmarks:
                for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    # Get hand label (Left/Right)
                    label = results.multi_handedness[i].classification[0].label
                    
                    # Process primary hand data to get real-time flex/stretch metrics
                    hand_angle = 180.0
                    temp_hand_data = HandData()
                    if i == 0:
                        new_hand_data = self._process_landmarks(hand_landmarks)
                        new_hand_data.hand_label = label
                        temp_hand_data = new_hand_data
                        if temp_hand_data.knuckle_angles and len(temp_hand_data.knuckle_angles) > 0:
                            hand_angle = temp_hand_data.knuckle_angles[0]
                    else:
                        temp_hand_data = self._process_landmarks(hand_landmarks)
                        if temp_hand_data.knuckle_angles and len(temp_hand_data.knuckle_angles) > 0:
                            hand_angle = temp_hand_data.knuckle_angles[0]
                            
                    # Determine dynamic cyber-medical colors based on stretch quality
                    if hand_angle > 155:
                        bone_col = (0, 255, 200) # Glowing neon cyan for full extension/stretch
                        node_col = (255, 255, 255)
                    elif hand_angle < 110:
                        bone_col = (255, 120, 0) # Glowing amber orange for deep flexion/fist
                        node_col = (255, 200, 100)
                    else:
                        bone_col = (0, 180, 255) # Sleek sci-fi blue for transition range
                        node_col = (200, 220, 255)
                        
                    # Draw thicker neon landmarks for easier webcam visibility from a distance
                    self.mp_draw.draw_landmarks(
                        annotated, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                        self.mp_draw.DrawingSpec(color=bone_col, thickness=3, circle_radius=3),
                        self.mp_draw.DrawingSpec(color=node_col, thickness=1)
                    )
            
            with self.lock:
                self.hand_data = new_hand_data
                self.mirrored_frame = annotated
            
            time.sleep(0.001)
    
    def _process_landmarks(self, landmarks) -> HandData:
        """Extract hand data with gesture recognition"""
        # Key landmarks
        wrist = landmarks.landmark[0]
        thumb_tip = landmarks.landmark[4]
        index_tip = landmarks.landmark[8]
        middle_tip = landmarks.landmark[12]
        ring_tip = landmarks.landmark[16]
        pinky_tip = landmarks.landmark[20]
        index_mcp = landmarks.landmark[5]
        middle_mcp = landmarks.landmark[9]
        ring_mcp = landmarks.landmark[13]
        pinky_mcp = landmarks.landmark[17]
        
        # Scale to game area (left 75% of screen)
        raw_index_x = index_tip.x * GAME_AREA_WIDTH
        raw_index_y = index_tip.y * WINDOW_HEIGHT
        
        # Weighted average smoothing
        self.index_x_buffer.append(raw_index_x)
        self.index_y_buffer.append(raw_index_y)
        
        smooth_x = weighted_average(self.index_x_buffer)
        smooth_y = weighted_average(self.index_y_buffer)
        
        # Dynamic Reach Scaling based on Calibration ROM
        if self.calibration_active and self.calibrated_max_extension < 170.0:
            extension_mult = 170.0 / self.calibrated_max_extension
            center_x = GAME_AREA_WIDTH / 2
            center_y = WINDOW_HEIGHT / 2
            
            scaled_offset_x = (smooth_x - center_x) * extension_mult
            scaled_offset_y = (smooth_y - center_y) * extension_mult
            
            smooth_x = np.clip(center_x + scaled_offset_x, 15, GAME_AREA_WIDTH - 15)
            smooth_y = np.clip(center_y + scaled_offset_y, 15, WINDOW_HEIGHT - 15)
            
        index_pos = (int(smooth_x), int(smooth_y))
        thumb_pos = (int(thumb_tip.x * GAME_AREA_WIDTH), int(thumb_tip.y * WINDOW_HEIGHT))
        
        # Palm center
        raw_palm_x = ((wrist.x + middle_mcp.x) / 2) * GAME_AREA_WIDTH
        raw_palm_y = ((wrist.y + middle_mcp.y) / 2) * WINDOW_HEIGHT
        
        self.palm_x_buffer.append(raw_palm_x)
        self.palm_y_buffer.append(raw_palm_y)
        
        palm_center = (int(weighted_average(self.palm_x_buffer)), 
                      int(weighted_average(self.palm_y_buffer)))
        
        wrist_pos = (int(wrist.x * GAME_AREA_WIDTH), int(wrist.y * WINDOW_HEIGHT))
        
        # Pinch detection
        pinch_dist = math.sqrt(
            (thumb_tip.x - index_tip.x)**2 + 
            (thumb_tip.y - index_tip.y)**2
        )
        is_pinching = pinch_dist < 0.07  # Relaxed for easier detection
        
        # Fist detection (all fingertips close to palm)
        avg_finger_y = (index_tip.y + middle_tip.y + ring_tip.y + pinky_tip.y) / 4
        palm_y = (wrist.y + middle_mcp.y) / 2
        is_fist = abs(avg_finger_y - palm_y) < self.fist_threshold
        
        # Finger extension (max reach)
        extension = math.sqrt(
            (index_tip.x - wrist.x)**2 + 
            (index_tip.y - wrist.y)**2
        ) * GAME_AREA_WIDTH
        
        # Calculate knuckle angles
        angles = [
            self._calculate_angle((wrist.x, wrist.y), (index_mcp.x, index_mcp.y), (index_tip.x, index_tip.y)),
            self._calculate_angle((wrist.x, wrist.y), (middle_mcp.x, middle_mcp.y), (middle_tip.x, middle_tip.y)),
            self._calculate_angle((wrist.x, wrist.y), (ring_mcp.x, ring_mcp.y), (ring_tip.x, ring_tip.y)),
            self._calculate_angle((wrist.x, wrist.y), (pinky_mcp.x, pinky_mcp.y), (pinky_tip.x, pinky_tip.y))
        ]
        
        # Wrist Rotation (Pronation/Supination)
        # Angle between Index MCP and Pinky MCP
        dx_rot = pinky_mcp.x - index_mcp.x
        dy_rot = pinky_mcp.y - index_mcp.y
        wrist_rot = math.degrees(math.atan2(dy_rot, dx_rot))

        # Wrist Deviation (Radial/Ulnar)
        # Angle between Wrist and Middle MCP
        dx_dev = middle_mcp.x - wrist.x
        dy_dev = middle_mcp.y - wrist.y
        wrist_dev = math.degrees(math.atan2(dy_dev, dx_dev))
        
        return HandData(
            index_tip=index_pos,
            thumb_tip=thumb_pos,
            palm_center=palm_center,
            wrist=wrist_pos,
            is_pinching=is_pinching,
            is_fist=is_fist,
            finger_extension=extension,
            knuckle_angles=angles,
            wrist_rotation_angle=wrist_rot,
            wrist_deviation_angle=wrist_dev,
            landmarks=[landmarks]
        )
    
    def _calculate_angle(self, p1, p2, p3) -> float:
        # Calculate lengths of sides
        a = math.sqrt((p2[0] - p3[0])**2 + (p2[1] - p3[1])**2)
        c = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
        b = math.sqrt((p1[0] - p3[0])**2 + (p1[1] - p3[1])**2)
        
        # Prevent division by zero
        if a * c == 0:
            return 0.0
            
        # Law of Cosines formula
        cos_angle = (a**2 + c**2 - b**2) / (2 * a * c)
        
        # Clamp value to [-1, 1] to handle float precision errors
        cos_angle = max(-1.0, min(1.0, cos_angle))
        
        # Calculate angle in radians and convert to degrees
        angle_rad = math.acos(cos_angle)
        return math.degrees(angle_rad)
    
    def get_hand_data(self) -> HandData:
        with self.lock:
            return self.hand_data
    
    def get_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            return self.mirrored_frame.copy() if self.mirrored_frame is not None else None
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.webcam:
            self.webcam.stop()
        try:
            self.hands.close()
        except Exception:
            pass
