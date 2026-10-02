"""GameplayMixin implementation for PhysioSystem."""

from .shared import *


class GameplayMixin:
    def _update_menu(self, hand_data: HandData):
        if hasattr(self, 'logout_button') and self.logout_button.update(hand_data.index_tip):
            self.state = GameState.PATIENT_REGISTRATION
            self.patient_name = ""
            self.patient_age = ""
            self.input_active = "name"
            self.pain_checked = False
            self.calibration_active = False
            self.calibrated_fist_val = 0.12
            self.calibrated_max_extension = 170.0
            self.calibrated_min_angle = 15.0
            self.calibrated_max_angle = 90.0
            self.sounds.play('pop')
            return

        if hasattr(self, 'exit_button') and self.exit_button.update(hand_data.index_tip):
            self.running = False
            return
            
        # Calibration button
        if hasattr(self, 'calibrate_button') and self.calibrate_button.update(hand_data.index_tip):
            self.state = GameState.CALIBRATION
            self._init_calibration()
            self.sounds.play('select')
            return

        # History button
        if self.history_button.update(hand_data.index_tip):
            self.state = GameState.HISTORY
            self.dashboard_surf = None
            self.dashboard_loading = True
            self.sounds.play('select')
            
            # Load dashboard chart asynchronously in a background thread to prevent UI freezing
            def load_async():
                try:
                    surf = self.db.render_matplotlib_dashboard(self.patient_name)
                    self.dashboard_surf = surf
                except Exception as e:
                    print(f"Failed loading async chart: {e}")
                finally:
                    self.dashboard_loading = False
            
            threading.Thread(target=load_async, daemon=True).start()
            return
            
        for button in self.level_buttons:
            if button.update(hand_data.index_tip):
                self.current_level = button.level_num
                self.pending_level = button.level_num
                self.sounds.play('select')
                if not getattr(self, 'pain_checked', False):
                    self.pain_level = 0  # reset pain before pain screen
                    self.state = GameState.PAIN_SCALE  # show pain scale first
                else:
                    self._start_level()
                break
    
    def _update_level1(self, hand_data: HandData):
        """
        Level 1: Bubble Pop (Webcam-Based Reaching & Target Acquisition) - Accuracy Type: hit_rate
        Level 1 provides a webcam-based reaching and target-acquisition task, with reach distance
        serving as a software-derived ROM-related proxy. This is NOT equivalent to a clinical
        goniometric ROM measurement.
        """
        # Safety: ensure bubbles exist
        if not self.bubbles:
            self._spawn_bubbles()
            return

        # Move bubbles
        for bubble in self.bubbles:
            if not bubble.popped:
                bubble.x += bubble.vx
                bubble.y += bubble.vy
                if bubble.x < bubble.radius or bubble.x > GAME_AREA_WIDTH - bubble.radius:
                    bubble.vx *= -1
                if bubble.y < bubble.radius or bubble.y > WINDOW_HEIGHT - bubble.radius:
                    bubble.vy *= -1

        if hand_data.index_tip:
            for bubble in self.bubbles:
                if not bubble.popped:
                    dist = distance(hand_data.index_tip, (bubble.x, bubble.y))
                    if dist < bubble.radius:
                        bubble.popped = True
                        self.accuracy_attempts += 1   # count per bubble, not per frame
                        self.accuracy_hits += 1
                        points = int(10 * self.score_multiplier * (3 if bubble.is_golden else 1))
                        self.score += points
                        self.combo += 1
                        self._trigger_feedback()
                        self.sounds.play('pop')
                        color = (255, 215, 0) if bubble.is_golden else COLOR_BUBBLE
                        self.particles.emit(int(bubble.x), int(bubble.y), color, 20 if bubble.is_golden else 15)
                        self.popups.append(ScorePopup(bubble.x, bubble.y - 20, f"+{points}"))
                        if hand_data.wrist:
                            reach = distance(hand_data.wrist, (bubble.x, bubble.y))
                            self.reach_distance = max(self.reach_distance, reach)

        # Check if all bubbles popped or session timed out
        time_expired = (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5)
        all_popped = bool(self.bubbles and all(b.popped for b in self.bubbles))
        if all_popped or time_expired:
            # Research Accuracy: count every presented but unpopped bubble as a missed attempt
            for bubble in self.bubbles:
                if not bubble.popped:
                    self.accuracy_attempts += 1
                    bubble.popped = True  # Prevent duplicate counting
            self._end_level()
    
    def _update_level2(self, hand_data: HandData):
        """Level 2: The Basket (Strength)"""
        # Smooth basket movement
        if hand_data.palm_center:
            self.basket_x = hand_data.palm_center[0]
        
        speed_mult = 0.5 if self.slow_mo else 1.0
        
        # Update falling items
        for item in self.falling_items[:]:
            item.y += item.speed * speed_mult * getattr(self, 'pacing_multiplier', 1.0) * getattr(self, 'adaptive_speed_scale', 1.0)
            
            # Check collision with basket
            if (item.y >= self.basket_y - 20 and 
                item.y <= self.basket_y + 20 and
                abs(item.x - self.basket_x) < 75):
                
                self.falling_items.remove(item)
                
                if item.is_bomb:
                    if self.shield_active:
                        self.shield_active = False
                        self.shield_timer = 0
                        self.sounds.play('pop')
                        self.particles.emit(int(item.x), self.basket_y, (0, 200, 255), 25)
                        self.popups.append(ScorePopup(item.x, self.basket_y - 30, "DEFLECTED!"))
                    else:
                        # Bomb! Lose points and combo
                        self.score = max(0, self.score - 10)
                        self.combo = 0
                        self.sounds.play('pop')  # Different sound
                        self.particles.emit(int(item.x), self.basket_y, (255, 0, 0), 20)
                        self.popups.append(ScorePopup(item.x, self.basket_y - 30, "-10"))
                elif item.is_powerup:
                    # Power-up! 2x multiplier
                    self.score_multiplier = 2.0
                    self.multiplier_timer = 300  # 5 seconds
                    self.sounds.play('level_complete')
                    self.particles.emit(int(item.x), self.basket_y, (255, 215, 0), 25)
                    self.popups.append(ScorePopup(item.x, self.basket_y - 30, "2X!"))
                elif getattr(item, 'is_shield', False):
                    self.shield_active = True
                    self.shield_timer = 600  # 10 seconds
                    self.sounds.play('level_complete')
                    self.particles.emit(int(item.x), self.basket_y, (0, 200, 255), 25)
                    self.popups.append(ScorePopup(item.x, self.basket_y - 30, "SHIELD!"))
                elif getattr(item, 'is_freeze', False):
                    self.slow_mo = True
                    self.slow_mo_timer = 300  # 5 seconds
                    self.sounds.play('level_complete')
                    self.particles.emit(int(item.x), self.basket_y, (100, 255, 255), 25)
                    self.popups.append(ScorePopup(item.x, self.basket_y - 30, "FREEZE!"))
                else:
                    # Normal item caught — count as hit
                    points = int(15 * self.score_multiplier)
                    self.score += points
                    self.accuracy_hits += 1
                    self.accuracy_attempts += 1  # Count attempt only when item resolves
                    self.combo += 1
                    self.consecutive_misses = 0 # reset misses on hit
                    if self.combo > 0 and self.combo % 8 == 0:
                        self._adjust_pacing("fast")
                    self._trigger_feedback()
                    self.sounds.play('catch')
                    self.particles.emit(int(item.x), self.basket_y, COLOR_SUCCESS, 10)
                    self.popups.append(ScorePopup(item.x, self.basket_y - 30, f"+{points}"))
            
            elif item.y > WINDOW_HEIGHT:
                self.falling_items.remove(item)
                if not item.is_bomb and not item.is_powerup and not getattr(item, 'is_shield', False) and not getattr(item, 'is_freeze', False):
                    self.accuracy_attempts += 1  # Missed a catchable item
                    self.combo = 0  # Reset combo on miss (but not for bombs/powerups)
                    self.consecutive_misses += 1
                    if self.consecutive_misses >= 3:
                        self.consecutive_misses = 0
                        self._adjust_pacing("slow")
        
        # Spawn new items
        if len(self.falling_items) < 3 and random.random() < 0.02:
            self._spawn_falling_item()
        
        # End after 30 seconds
        if (time.time() - self.session_start > self.session_time_limit) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            # Research Accuracy Rule: Count active presented catchable items that were not caught as missed attempts
            # Bombs, shields, freezes, and powerups do not distort the denominator.
            for item in self.falling_items:
                if not item.is_bomb and not item.is_powerup and not getattr(item, 'is_shield', False) and not getattr(item, 'is_freeze', False):
                    self.accuracy_attempts += 1
            self.falling_items.clear()
            self._end_level()
    
    def _update_level3(self, hand_data: HandData):
        """
        Level 3: Pinch & Drop (Fine Motor Pinch & Object Transfer) - Accuracy Type: hit_rate
        Note on self-occlusion: When thumb and index finger overlap from the camera viewpoint,
        landmark visibility/confidence may decrease, potentially causing incorrect pinch-state
        transitions or unintended object release.
        """
        # Update seeds
        for seed in self.seeds[:]:
            if not seed.grabbed:
                seed.y += seed.speed * getattr(self, 'pacing_multiplier', 1.0) * getattr(self, 'adaptive_speed_scale', 1.0)
                
                # Check pinch grab
                if hand_data.is_pinching and hand_data.index_tip:
                    dist = distance(hand_data.index_tip, (seed.x, seed.y))
                    if dist < seed.radius + 35:  # Easier grab radius
                        seed.grabbed = True
                        self.accuracy_attempts += 1
            else:
                # Follow cursor
                if hand_data.index_tip:
                    seed.x = hand_data.index_tip[0]
                    seed.y = hand_data.index_tip[1]
                    
                    # Check drop in pot
                    if not hand_data.is_pinching:
                        pot_dist = distance((seed.x, seed.y), (self.pot_x, self.pot_y))
                        if pot_dist < 60:
                            points = int(25 * self.score_multiplier * (3 if seed.is_golden else 1))
                            self.score += points
                            self.accuracy_hits += 1
                            self.combo += 1
                            self.consecutive_misses = 0 # reset misses on pot success
                            if self.combo > 0 and self.combo % 6 == 0:
                                self._adjust_pacing("fast")
                            self._trigger_feedback()
                            self.sounds.play('catch')
                            color = (255, 215, 0) if seed.is_golden else COLOR_SUCCESS
                            self.particles.emit(self.pot_x, self.pot_y, color, 18 if seed.is_golden else 12)
                            self.popups.append(ScorePopup(self.pot_x, self.pot_y - 40, f"+{points}"))
                        else:
                            self.combo = 0  # Reset on miss
                        self.seeds.remove(seed)
            
            # Remove if off screen
            if seed.y > WINDOW_HEIGHT and not seed.grabbed:
                self.seeds.remove(seed)
                self.accuracy_attempts += 1 # Missed an ungrabbed presented seed
                self.combo = 0 # Missed a seed
                self.consecutive_misses += 1
                if self.consecutive_misses >= 3:
                    self.consecutive_misses = 0
                    self._adjust_pacing("slow")
        
        # Spawn new seeds
        if len(self.seeds) < 2 and random.random() < 0.015:
            self._spawn_seed()
        
        # End after 30 seconds
        if (time.time() - self.session_start > self.session_time_limit) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            # Count any remaining ungrabbed seeds as missed attempts
            for seed in self.seeds:
                if not seed.grabbed:
                    self.accuracy_attempts += 1
            self.seeds.clear()
            self._end_level()

    def _update_level4(self, hand_data: HandData):
        """Level 4: Tracing / Coordination (Hand Stability)"""
        # Time-based movement for the target (Figure 8 pattern)
        theme = self._get_theme()
        speed_mult = theme.get("speed_multiplier", 1.0)
        self.trace_t += 0.008 * speed_mult * getattr(self, 'pacing_multiplier', 1.0) * getattr(self, 'adaptive_speed_scale', 1.0)
        
        # Figure 8 (Lissajous curve) parameters
        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        a = 180 # width scale (was 300)
        b = 90 # height scale (was 150)
        
        # Calculate target position
        self.trace_target_x = cx + a * math.sin(self.trace_t)
        self.trace_target_y = cy + b * math.sin(2 * self.trace_t)
        
        # Store path for drawing
        self.trace_path.append((self.trace_target_x, self.trace_target_y))
        if len(self.trace_path) > 100:
            self.trace_path.pop(0)
            
        # Check tracing accuracy
        if hand_data.index_tip:
            dist = distance(hand_data.index_tip, (self.trace_target_x, self.trace_target_y))
            
            # Record every few frames for accuracy
            if int(self.trace_t * 100) % 5 == 0:
                self.accuracy_attempts += 1
                self.recent_tracing_attempts += 1
                if dist < 85 * getattr(self, 'adaptive_target_scale', 1.0): # Good trace radius (was 60)
                    self.accuracy_hits += 1
                    self.recent_tracing_hits += 1
                    self.score += int(5 * self.score_multiplier)
                    
                    if dist < 45 * getattr(self, 'adaptive_target_scale', 1.0): # Perfect trace (was 30)
                        self.combo += 1
                        self.particles.emit(int(self.trace_target_x), int(self.trace_target_y), COLOR_SUCCESS, 2)
                else:
                    self.combo = 0 # Lost combo
                
                # Check dynamic pacing every 15 checks
                if self.recent_tracing_attempts >= 15:
                    ratio = self.recent_tracing_hits / self.recent_tracing_attempts
                    if ratio >= 0.85 and self.pacing_multiplier < 1.3:
                        self._adjust_pacing("fast")
                    elif ratio < 0.50 and self.pacing_multiplier > 0.6:
                        self._adjust_pacing("slow")
                    self.recent_tracing_attempts = 0
                    self.recent_tracing_hits = 0
            
            # Trigger feedback occasionally
            if self.combo > 0 and self.combo % 20 == 0 and int(self.trace_t * 100) % 5 == 0:
                self._trigger_feedback()
                self.sounds.play('catch')
                self.popups.append(ScorePopup(self.trace_target_x, self.trace_target_y - 40, "SMOOTH!"))
                
        # End after 30 seconds or wall-clock safety ceiling
        if (time.time() - self.session_start > self.session_time_limit) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            self._end_level()

    def _update_level5(self, hand_data: HandData):
        """
        Level 5: Grip & Release (Grip-and-Release Rehabilitation Task) - Accuracy Type: completion_rate
        Level 5 provides repetitive grip-and-release movement training based on detected hand closure
        and subsequent finger extension. The system does not directly measure grip force, pinch force,
        muscle tone, or resistance. A patient may complete the detected grip-release movement without
        the system being able to determine the magnitude of muscular force generated.
        """
        # Constantly deflate slowly (deflation rate adapts to pacing)
        if self.balloon_scale > 1.0:
            self.balloon_scale -= 0.005 * getattr(self, 'pacing_multiplier', 1.0)
            
        # If no rep completed for 8 seconds, slow down the deflation rate (make it easier)
        if not hasattr(self, 'last_rep_time'):
            self.last_rep_time = time.time()
            
        if hand_data.is_fist and self.pump_state == 0:
            # Cycle attempt initiated (grip phase)
            self.pump_state = 1
            self.grip_cycle_start = time.time()
            self.balloon_scale = max(0.5, self.balloon_scale - 0.2)
            self.sounds.play('catch')
        elif not hand_data.is_fist and hand_data.finger_extension > 120 and self.pump_state == 1:
            # Successful grip and full release completed
            self.pump_state = 0
            self.grip_cycle_start = None
            self.pump_reps += 1
            self.accuracy_hits += 1
            self.accuracy_attempts += 1
            self.combo += 1
            self.last_rep_time = time.time() # Reset trigger timer on success
            if self.combo > 0 and self.combo % 3 == 0:
                self._adjust_pacing("fast")
            self.balloon_scale = min(2.0, self.balloon_scale + 0.5)
            self.score += int(15 * self.score_multiplier)
            self.sounds.play('pop')
            self.particles.emit(GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2, COLOR_SUCCESS, 15)
            self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2 - 50, "+1 REP!"))
            
            if self.combo % 3 == 0:
                self._trigger_feedback()
        elif self.pump_state == 1 and getattr(self, 'grip_cycle_start', None) and (time.time() - self.grip_cycle_start > 5.0):
            # Attempted grip cycle but failed to achieve full release within 5 seconds window
            self.pump_state = 0
            self.grip_cycle_start = None
            self.accuracy_attempts += 1  # Record failed cycle attempt
            self.combo = 0
                
        if time.time() - self.last_rep_time > 8.0:
            self.last_rep_time = time.time() # Reset trigger timer
            if self.pacing_multiplier > 0.6:
                self._adjust_pacing("slow")
                
        # End after 30 seconds
        if (time.time() - self.session_start > self.session_time_limit) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            if self.pump_state == 1:
                # Incomplete rep in progress at session termination
                self.accuracy_attempts += 1
                self.pump_state = 0
            self._end_level()

    def _update_level6(self, hand_data: HandData):
        """
        Level 6: Memory Sequence (Cognitive-Motor Training Task) - Accuracy Type: hit_rate
        Level 6 combines sequence recall with visual-motor targeting and is therefore treated as
        a cognitive-motor training task rather than a validated cognitive assessment.
        """
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        pads = {
            1: (cx - 150, cy - 80),
            2: (cx + 150, cy - 80),
            3: (cx - 150, cy + 120),
            4: (cx + 150, cy + 120)
        }
        
        if self.simon_state == "START":
            self.simon_sequence = [random.randint(1, 4)]
            self.simon_state = "SHOW"
            self.simon_timer = time.time()
            self.simon_show_idx = 0
            self.simon_active_pad = None
            
        elif self.simon_state == "SHOW":
            t = time.time() - self.simon_timer
            # Every 1 second, show the next pad
            if t > 0.8:
                if self.simon_show_idx < len(self.simon_sequence):
                    self.simon_active_pad = self.simon_sequence[self.simon_show_idx]
                    self.sounds.play('pop')
                    self.simon_show_idx += 1
                    self.simon_timer = time.time()
                elif t > 1.2:
                    self.simon_active_pad = None
                    self.simon_state = "PLAY"
                    self.simon_player_idx = 0
                    self.popups.append(ScorePopup(cx, cy - 200, "YOUR TURN!", (0, 255, 255)))
            elif t > 0.4:
                self.simon_active_pad = None # brief pause between flashes
                
        elif self.simon_state == "PLAY":
            if not hand_data.index_tip: return
            hx, hy = hand_data.index_tip
            
            # Check collisions with pads
            hovered_pad = None
            for p_id, (px, py) in pads.items():
                if distance((hx, hy), (px, py)) < 75:
                    hovered_pad = p_id
                    break
                    
            if hovered_pad:
                if getattr(self, '_last_hover', None) != hovered_pad:
                    self._last_hover = hovered_pad
                    self._hover_start = time.time()
                elif time.time() - self._hover_start > 0.4: # 0.4s hover to select
                    self.simon_active_pad = hovered_pad
                    self.sounds.play('catch')
                    
                    if hovered_pad == self.simon_sequence[self.simon_player_idx]:
                        # Correct!
                        self.simon_player_idx += 1
                        self.accuracy_hits += 1
                        self.accuracy_attempts += 1
                        self.score += int(10 * self.score_multiplier)
                        self.particles.emit(pads[hovered_pad][0], pads[hovered_pad][1], COLOR_SUCCESS, 10)
                        
                        if self.simon_player_idx >= len(self.simon_sequence):
                            # Sequence complete!
                            self.popups.append(ScorePopup(cx, cy, "CORRECT!", COLOR_SUCCESS))
                            self.simon_sequence.append(random.randint(1, 4))
                            self.simon_state = "SHOW"
                            self.simon_timer = time.time() + 1.0 # Pause before showing next
                            self.simon_show_idx = 0
                            self.simon_active_pad = None
                            self.combo += 1
                            if self.combo % 2 == 0:
                                self._trigger_feedback()
                    else:
                        # Wrong!
                        self.accuracy_attempts += 1
                        self.popups.append(ScorePopup(cx, cy, "WRONG!", COLOR_WARNING))
                        self.simon_state = "START"
                        self.combo = 0
                    
                    self._last_hover = None
            else:
                self._last_hover = None
                self.simon_active_pad = None

        if (time.time() - self.session_start > self.session_time_limit) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            self._end_level()


    def _update_level7(self, hand_data: HandData):
        """
        Level 7: Rotation Orbit (Webcam-Derived Forearm Rotation Proxy) - Accuracy Type: hit_rate
        Level 7 provides a webcam-based forearm rotation training task using the relative orientation
        of hand landmarks as a proxy for rotational movement. Subject to 2D projection limitations,
        camera orientation sensitivity, wrist-motion confounding, possible upper-limb compensation,
        and absence of goniometric validation.
        """
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        
        if not getattr(self, 'wrist_mode', None):
            self.wrist_mode = "rotation"
            self.wrist_target_angle = 45.0 # Starting orbital target
            self.wrist_hold_time = 0.0

        if not hand_data.index_tip or not hand_data.wrist: return
        
        if getattr(self, "wrist_rotation_baseline", None) is None:
            self.wrist_rotation_baseline = hand_data.wrist_rotation_angle

        relative_rotation = hand_data.wrist_rotation_angle - self.wrist_rotation_baseline
        # Map patient movement relative to their starting posture. This keeps
        # Level 7 hand-only and avoids camera/hand-label dependent absolute angles.
        current_angle = relative_rotation * 2.0
        self.forearm_angle_history.append(hand_data.wrist_rotation_angle)
        self.forearm_assessment = self.forearm_classifier.classify(
            hand_data.wrist_rotation_angle,
            self.forearm_angle_history,
            getattr(hand_data, 'wrist_deviation_angle', 0.0),
            getattr(self, 'wrist_hold_time', 0.0),
        )
        
        # Normalize angles to 0-360 for comparison
        target_norm = self.wrist_target_angle % 360
        current_norm = current_angle % 360
        
        diff = abs(current_norm - target_norm)
        if diff > 180: diff = 360 - diff
        
        if diff < getattr(self, 'rotation_tolerance', 25.0): # tolerance adapts for "locking on"
            self.wrist_hold_time += 1/30.0
            if self.wrist_hold_time > getattr(self, 'rotation_hold_required', 1.5):
                # Success! Target angle checkpoint reached
                self.score += int(15 * getattr(self, 'score_multiplier', 1.0))
                self.accuracy_hits += 1
                self.accuracy_attempts += 1
                self.particles.emit(cx, cy, (0, 255, 255), 30)
                self.sounds.play('catch')
                
                # Spawn new target far enough away (at least 60 degrees)
                import random
                offset = random.uniform(60, 180)
                if random.choice([True, False]): offset *= -1
                self.wrist_target_angle = (self.wrist_target_angle + offset) % 360
                self.wrist_hold_time = 0.0
        else:
            self.wrist_hold_time = 0.0
            
        import time
        if (time.time() - getattr(self, 'session_start', 0)) > getattr(self, 'session_time_limit', 60):
            # Final in-progress orbital checkpoint timed out before completion
            self.accuracy_attempts += 1
            self._end_level()

        self.satellite_angle = current_angle

    def _update_level8(self, hand_data: HandData):
        """
        Level 8: Smart Object Assembly - Accuracy Type: binary_completion
        Measures task-level binary completion: whole object assembled before timeout = 100%,
        timeout before all parts placed = 0%. Note on self-occlusion: Complex multi-finger manipulation
        is subject to self-occlusion when grasping and rotating parts in 2D perspective.
        """
        if not hand_data.index_tip or not getattr(hand_data, 'is_pinching', False) and not getattr(self, 'was_pinching', False):
            pass
            
        hx, hy = hand_data.index_tip if hand_data.index_tip else (0,0)
        is_pinching = getattr(hand_data, 'is_pinching', False)
        
        if is_pinching and not getattr(self, 'was_pinching', False):
            for part in getattr(self, 'assembly_parts', []):
                if not part.is_locked:
                    dist = ((part.current_pos[0] - hx)**2 + (part.current_pos[1] - hy)**2)**0.5
                    if dist < 80 * getattr(self, 'adaptive_target_scale', 1.0):
                        part.is_grabbed = True
                        self.sounds.play('select')
                        break
        
        if not is_pinching and getattr(self, 'was_pinching', False):
            for part in getattr(self, 'assembly_parts', []):
                if part.is_grabbed:
                    part.is_grabbed = False
                    dist = ((part.current_pos[0] - part.target_pos[0])**2 + (part.current_pos[1] - part.target_pos[1])**2)**0.5
                    ang_diff = abs(part.current_angle - part.target_angle) % 360
                    if ang_diff > 180: ang_diff = 360 - ang_diff
                    
                    if dist < getattr(self, 'assembly_position_tolerance', 50.0) and ang_diff < getattr(self, 'assembly_angle_tolerance', 30.0):
                        part.is_locked = True
                        part.current_pos = list(part.target_pos)
                        part.current_angle = part.target_angle
                        self.sounds.play('catch')
                        self.particles.emit(part.current_pos[0], part.current_pos[1], (0,255,0), 30)
                        self.score += int(50 * getattr(self, 'score_multiplier', 1.0))
                        
                        if all(p.is_locked for p in self.assembly_parts):
                            self.popups.append(ScorePopup(GAME_AREA_WIDTH//2, WINDOW_HEIGHT//2, "ASSEMBLY COMPLETE!", (0,255,0)))
                            self.accuracy_hits += 1
                            self.accuracy_attempts += 1
                            self._end_level()

        for part in getattr(self, 'assembly_parts', []):
            if part.is_grabbed:
                part.current_pos[0] = hx
                part.current_pos[1] = hy
                part.current_angle = getattr(hand_data, 'wrist_rotation_angle', 0.0)
                
        self.was_pinching = is_pinching
        
        import time
        if (time.time() - self.session_start > max(getattr(self, 'session_time_limit', 60), 60)):
            self.accuracy_attempts += 1
            self._end_level()

    def _update_level9(self, hand_data: HandData):
        """Level 9: Precision Path - Connecting Dots - Accuracy Type: hit_rate"""
        if not hasattr(self, 'precision_dots') or not self.precision_dots:
            self._spawn_precision_dots()
            return

        if hand_data.index_tip:
            idx = self.precision_current_dot
            if idx < len(self.precision_dots):
                target_dot = self.precision_dots[idx]
                target_dot.state = "ACTIVE"
                
                dist = distance(hand_data.index_tip, (target_dot.x, target_dot.y))
                
                # Check if dot is touched
                if dist < target_dot.radius:
                    target_dot.state = "COMPLETED"
                    self.precision_path_points.append((target_dot.x, target_dot.y))
                    self.precision_current_dot += 1
                    
                    self.accuracy_attempts += 1
                    self.accuracy_hits += 1
                    self.score += int(10 * getattr(self, 'score_multiplier', 1.0))
                    self.sounds.play('pop')
                    self.particles.emit(int(target_dot.x), int(target_dot.y), (0, 255, 200), 20)
                    self.popups.append(ScorePopup(target_dot.x, target_dot.y - 20, "+10"))
                    
                    if hand_data.wrist:
                        reach = distance(hand_data.wrist, (target_dot.x, target_dot.y))
                        self.reach_distance = max(self.reach_distance, reach)
                else:
                    # Check if they hovered over a WRONG dot
                    for i, dot in enumerate(self.precision_dots):
                        if i != idx and dot.state == "WAITING":
                            wrong_dist = distance(hand_data.index_tip, (dot.x, dot.y))
                            if wrong_dist < dot.radius + 15:
                                # Subtle correction feedback
                                if getattr(self, 'warning_timer', 0) <= 0:
                                    self.correctness_warning = "Follow the numbered path carefully"
                                    self.warning_timer = 90
                                    self.accuracy_attempts += 1 # counts as a mistake

            else:
                # All dots completed
                self._end_level()
        
        import time
        if (time.time() - self.session_start > max(getattr(self, 'session_time_limit', 60), 60)):
            # Research Accuracy: count remaining unreached dots as missed target attempts
            remaining_dots = len(getattr(self, 'precision_dots', [])) - getattr(self, 'precision_current_dot', 0)
            if remaining_dots > 0:
                self.accuracy_attempts += remaining_dots
            self._end_level()

    def _update_level10(self, hand_data: HandData):
        """
        Level 10: Precision Pathway - Accuracy Type: path_accuracy
        Measures proportion of trajectory tracking samples maintained within the acceptable
        pathway corridor width (min_dist <= half_width).
        0% = completely off-path for all samples.
        100% = perfectly within corridor for 100% of trajectory samples.
        """
        if not getattr(self, 'pathway_started', False):
            self._spawn_precision_pathway()
            return
            
        import time
        import numpy as np
        
        if hand_data.index_tip:
            hx, hy = hand_data.index_tip
            points = self.pathway_config.points
            
            current_p = getattr(self, 'pathway_current_proj', points[0])
            
            if not getattr(self, 'pathway_grabbed', False):
                dist_to_start = np.linalg.norm(np.array([hx, hy]) - np.array(current_p))
                if dist_to_start < 40:
                    self.pathway_grabbed = True
                    self.sounds.play('select')
                else:
                    pass # Don't update progression if not grabbed
            
            if getattr(self, 'pathway_grabbed', False):
                self.pathway_samples += 1
                
                # Find closest distance to any segment on the path
                min_dist = float('inf')
                best_proj = current_p
                
                for i in range(len(points)-1):
                    p1 = np.array(points[i])
                    p2 = np.array(points[i+1])
                    p3 = np.array([hx, hy])
                    
                    l2 = np.sum((p1-p2)**2)
                    if l2 == 0:
                        dist = np.linalg.norm(p3 - p1)
                    else:
                        t = max(0, min(1, np.dot(p3 - p1, p2 - p1) / l2))
                        projection = p1 + t * (p2 - p1)
                        dist = np.linalg.norm(p3 - projection)
                    if dist < min_dist:
                        min_dist = dist
                        best_proj = p1 if l2 == 0 else projection
                        
                half_width = self.pathway_config.width / 2
                
                # Track samples maintained within path corridor
                if min_dist <= half_width:
                    self.pathway_on_path_samples = getattr(self, 'pathway_on_path_samples', 0) + 1
                
                # If they stray too far from the path, they drop the marker
                if min_dist > half_width + 40:
                    self.pathway_grabbed = False
                    self.correctness_warning = "LOST MARKER - Return to Start"
                    self.warning_timer = 45
                else:
                    self.pathway_current_proj = best_proj
                    self.pathway_total_deviation += min_dist
                    
                    # Check boundaries
                    if min_dist > half_width:
                        self.pathway_boundary_violations += 1
                        self.correctness_warning = "PATH DEVIATION"
                        self.warning_timer = 30
                    elif min_dist > half_width * 0.7:
                        self.correctness_warning = "WARNING - Approaching Boundary"
                        self.warning_timer = 15
                    
                # End condition
                end_p = np.array(points[-1])
                dist_to_end = np.linalg.norm(np.array(self.pathway_current_proj) - end_p)
                if dist_to_end < 40:
                    samples = getattr(self, 'pathway_samples', 0)
                    on_path = getattr(self, 'pathway_on_path_samples', 0)
                    if samples > 0:
                        self.accuracy_attempts = samples
                        self.accuracy_hits = on_path
                        accuracy = round((on_path / samples) * 100.0, 2)
                    else:
                        self.accuracy_attempts = 0
                        self.accuracy_hits = 0
                        accuracy = 0.0
                    
                    violation_penalty = min(30, self.pathway_boundary_violations * 2)
                    self.score = int(max(0, accuracy - violation_penalty))
                    
                    self.popups.append(ScorePopup(hx, hy - 40, "PATH COMPLETE!", COLOR_SUCCESS))
                    self.sounds.play('level_complete')
                    self._end_level()
                    return
                
        if (time.time() - self.session_start > max(getattr(self, 'session_time_limit', 60), 60)):
            samples = getattr(self, 'pathway_samples', 0)
            on_path = getattr(self, 'pathway_on_path_samples', 0)
            if samples > 0:
                self.accuracy_attempts = samples
                self.accuracy_hits = on_path
                accuracy = round((on_path / samples) * 100.0, 2)
            else:
                self.accuracy_attempts = 0
                self.accuracy_hits = 0
                accuracy = 0.0
            violation_penalty = min(30, getattr(self, 'pathway_boundary_violations', 0) * 2)
            self.score = int(max(0, accuracy - violation_penalty))
            self._end_level()

    def _draw_level1(self):
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme['level1_name']

        # Title (pushed down to clear HUD bar)
        title = self.font_medium.render(f"LEVEL 1: {level_name}", True, primary)
        self.screen.blit(title, (50, 85))

        # Bubble counter
        total_bubbles = len(self.bubbles)
        remaining = sum(1 for b in self.bubbles if not b.popped)
        counter_text = self.font_hint.render(
            f"Bubbles: {remaining} / {total_bubbles}", True, (180, 210, 230))
        self.screen.blit(counter_text, (50, 115))

        # Dot row showing bubble status
        dot_x = 50
        dot_y = 142
        for bubble in self.bubbles:
            dot_color = primary if not bubble.popped else (50, 55, 75)
            pygame.draw.circle(self.screen, dot_color, (dot_x, dot_y), 6)
            pygame.draw.circle(self.screen, (255, 255, 255), (dot_x, dot_y), 6, 1)
            dot_x += 18

        # Bubbles
        for bubble in self.bubbles:
            if not bubble.popped:
                pygame.draw.circle(self.screen, bubble.color, (int(bubble.x), int(bubble.y)), bubble.radius)
                surf = pygame.Surface((bubble.radius*2, bubble.radius*2), pygame.SRCALPHA)
                pygame.draw.ellipse(surf, (255,255,255,90), (bubble.radius*0.4, bubble.radius*0.15, bubble.radius, bubble.radius*0.5))
                self.screen.blit(surf, (int(bubble.x) - bubble.radius, int(bubble.y) - bubble.radius))
                pygame.draw.circle(self.screen, primary, (int(bubble.x), int(bubble.y)), bubble.radius, 2)
    
    def _draw_level2(self):
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme['level2_name']

        # Title pushed lower
        title = self.font_medium.render(f"LEVEL 2: {level_name}", True, primary)
        self.screen.blit(title, (50, 85))

        # Timer bar lower
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 135
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        # Basket (theme-colored)
        basket_rect = pygame.Rect(int(self.basket_x - 75), self.basket_y, 150, 40)
        pygame.draw.rect(self.screen, theme["secondary_color"], basket_rect, border_radius=10)
        pygame.draw.rect(self.screen, primary, basket_rect, 3, border_radius=10)

        # Shield Effect
        if self.shield_active:
            pulse = int(5 * math.sin(time.time() * 10))
            shield_rect = basket_rect.copy()
            shield_rect.inflate_ip(20 + pulse, 20 + pulse)
            pygame.draw.ellipse(self.screen, (0, 200, 255), shield_rect, 3)
            # draw a faint inner fill via an alpha surface
            shield_surf = pygame.Surface((shield_rect.width, shield_rect.height), pygame.SRCALPHA)
            pygame.draw.ellipse(shield_surf, (0, 200, 255, 40), shield_surf.get_rect())
            self.screen.blit(shield_surf, shield_rect.topleft)

        # Freezing background tint
        if self.slow_mo:
            freeze_surf = pygame.Surface((GAME_AREA_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            freeze_surf.fill((100, 255, 255, 15))
            self.screen.blit(freeze_surf, (0, 0))

        # Falling items
        for item in self.falling_items:
            pygame.draw.circle(self.screen, item.color,
                             (int(item.x), int(item.y)), item.radius)
            pygame.draw.circle(self.screen, COLOR_TEXT,
                             (int(item.x), int(item.y)), item.radius, 2)
    
    def _draw_level3(self):
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme['level3_name']

        # Title pushed lower
        title = self.font_medium.render(f"LEVEL 3: {level_name}", True, primary)
        self.screen.blit(title, (50, 85))

        # Timer bar lower
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 135
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        # Pot (theme-colored)
        pygame.draw.circle(self.screen, theme["secondary_color"], (self.pot_x, self.pot_y), 50)
        pygame.draw.circle(self.screen, primary, (self.pot_x, self.pot_y), 50, 3)

        # Seeds
        for seed in self.seeds:
            color = theme["accent_color"] if seed.grabbed else COLOR_SEED
            pygame.draw.circle(self.screen, color,
                             (int(seed.x), int(seed.y)), seed.radius)
            pygame.draw.circle(self.screen, COLOR_TEXT,
                             (int(seed.x), int(seed.y)), seed.radius, 2)
                             
    def _draw_level4(self):
        """Draw Tracing Level"""
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme.get('level4_name', 'Magic Trace')

        title = self.font_medium.render(f"LEVEL 4: {level_name}", True, primary)
        self.screen.blit(title, (50, 85))
        
        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 135
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        
        # Draw the full Figure-8 guide path (static background)
        points = []
        for i in range(101):
            t = i * (math.pi * 2 / 100)
            px = cx + 180 * math.sin(t)
            py = cy + 90 * math.sin(2 * t)
            points.append((px, py))
            
        if len(points) > 1:
            pygame.draw.lines(self.screen, (30, 50, 70), False, points, 5)
            
        # Draw the recent path trail (active)
        if len(self.trace_path) > 1:
            pygame.draw.lines(self.screen, theme["secondary_color"], False, self.trace_path, 3)
            
        # Draw target
        pygame.draw.circle(self.screen, theme["accent_color"], (int(self.trace_target_x), int(self.trace_target_y)), 25)
        pygame.draw.circle(self.screen, (255, 255, 255), (int(self.trace_target_x), int(self.trace_target_y)), 10)
        
        inst = self.font_small.render("Keep your finger exactly on the moving target!", True, COLOR_TEXT)
        self.screen.blit(inst, inst.get_rect(center=(cx, cy + 200)))
        
    def _draw_level5(self):
        """Draw Grip & Release Level"""
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme.get('level5_name', 'Balloon Pump')

        title = self.font_medium.render(f"LEVEL 5: {level_name}", True, primary)
        self.screen.blit(title, (50, 85))
        
        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 135
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2 + 30
        
        # Draw balloon/core
        base_r = 80
        current_r = int(base_r * self.balloon_scale)
        
        color = theme["accent_color"] if self.pump_state == 0 else theme["secondary_color"]
        pygame.draw.circle(self.screen, color, (cx, cy), current_r)
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), current_r, max(1, current_r // 15))
        
        # Reps text
        reps_text = self.font_large.render(str(self.pump_reps), True, (255, 255, 255))
        self.screen.blit(reps_text, reps_text.get_rect(center=(cx, cy)))
        
        inst_txt = "Make a FIST, then OPEN your hand fully!" if self.pump_state == 0 else "OPEN your hand wide!"
        inst = self.font_small.render(inst_txt, True, COLOR_TEXT)
        self.screen.blit(inst, inst.get_rect(center=(cx, cy + current_r + 40)))
        
    def _draw_level6(self):
        """Draw Memory Sequence Level"""
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme.get('level6_name', 'Memory Sequence')

        title = self.font_medium.render(f"LEVEL 6: {level_name}", True, primary)
        self.screen.blit(title, (50, 85))
        
        # Timer
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 135
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        pads = {
            1: (cx - 150, cy - 80),
            2: (cx + 150, cy - 80),
            3: (cx - 150, cy + 120),
            4: (cx + 150, cy + 120)
        }
        pad_colors = {
            1: (255, 100, 100), # Red
            2: (100, 255, 100), # Green
            3: (100, 100, 255), # Blue
            4: (255, 255, 100)  # Yellow
        }
        
        for p_id, (px, py) in pads.items():
            col = pad_colors[p_id]
            is_active = (getattr(self, 'simon_active_pad', None) == p_id)
            is_hovering = (self.simon_state == "PLAY" and getattr(self, '_last_hover', None) == p_id)
            
            draw_col = col if is_active else tuple(int(c * 0.4) for c in col)
            r_size = 75 if is_active else 65
            if is_hovering and not is_active:
                draw_col = tuple(int(c * 0.7) for c in col)
                r_size = 70
                # Draw hover progress
                if hasattr(self, '_hover_start'):
                    prog = min(1.0, (time.time() - self._hover_start) / 0.4)
                    pygame.draw.arc(self.screen, (255,255,255), (px-80, py-80, 160, 160), math.pi/2, math.pi/2 + 2*math.pi*prog, 4)
            
            pygame.draw.circle(self.screen, draw_col, (px, py), r_size)
            pygame.draw.circle(self.screen, (255, 255, 255), (px, py), r_size, 3)
            
        status = "WATCH CAREFULLY!" if self.simon_state == "SHOW" else "REPEAT SEQUENCE"
        if self.simon_state == "START": status = "GET READY"
        inst = self.font_medium.render(status, True, COLOR_TEXT)
        self.screen.blit(inst, inst.get_rect(center=(cx, cy + 240)))
        
        seq_len = max(0, len(self.simon_sequence) - 1) if self.simon_state == "START" else len(self.simon_sequence)
        score_t = self.font_small.render(f"Sequence Length: {seq_len}", True, (0, 255, 200))
        self.screen.blit(score_t, score_t.get_rect(center=(cx, cy - 200)))
    
    def _draw_cursor(self, hand_data: HandData):  # noqa
        if not hand_data.index_tip:
            return

        cx, cy = hand_data.index_tip
        t = time.time()

        # --- State-based colors ---
        if hand_data.is_fist:
            core_color   = (255, 140, 0)   # Orange = fist/pause
            ring_color   = (255, 180, 60)
            glow_color   = (255, 120, 0)
        elif hand_data.is_pinching:
            core_color   = (50, 255, 150)  # Green = pinching
            ring_color   = (100, 255, 180)
            glow_color   = (0, 200, 100)
        else:
            core_color   = (0, 200, 255)   # Cyan = normal point
            ring_color   = (80, 220, 255)
            glow_color   = (0, 150, 220)

        # --- Motion trail ---
        self._cursor_trail.append((cx, cy))
        if len(self._cursor_trail) > 12:
            self._cursor_trail.pop(0)

        for i, (tx, ty) in enumerate(self._cursor_trail[:-1]):
            alpha_factor = (i + 1) / len(self._cursor_trail)
            r = int(glow_color[0] * alpha_factor)
            g = int(glow_color[1] * alpha_factor)
            b = int(glow_color[2] * alpha_factor)
            trail_r = max(2, int(8 * alpha_factor))
            pygame.draw.circle(self.screen, (r, g, b), (tx, ty), trail_r)

        # --- Outer pulsing glow ring ---
        pulse = int(5 + 4 * math.sin(t * 5))
        pygame.draw.circle(self.screen, glow_color, (cx, cy), 22 + pulse, 2)

        # --- Mid ring ---
        pygame.draw.circle(self.screen, ring_color, (cx, cy), 18, 3)

        # --- Filled inner circle ---
        pygame.draw.circle(self.screen, core_color, (cx, cy), 12)

        # --- Bright white center dot ---
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 4)

        # --- Crosshair lines for precision ---
        line_len = 8
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx - line_len - 14, cy), (cx - 14, cy), 2)
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx + 14, cy), (cx + line_len + 14, cy), 2)
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx, cy - line_len - 14), (cx, cy - 14), 2)
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx, cy + 14), (cx, cy + line_len + 14), 2)

        # --- Pinch line between thumb and index ---
        if hand_data.is_pinching and hand_data.thumb_tip:
            pygame.draw.line(self.screen, (50, 255, 150),
                             hand_data.index_tip, hand_data.thumb_tip, 3)
            # Small circle at thumb tip too
            pygame.draw.circle(self.screen, (50, 255, 150),
                               hand_data.thumb_tip, 8)
            pygame.draw.circle(self.screen, (255, 255, 255),
                               hand_data.thumb_tip, 3)
    
    def _spawn_bubbles(self):
        self.bubbles.clear()
        theme = self._get_theme()
        spd = theme["speed_multiplier"] * getattr(self, 'adaptive_speed_scale', 1.0)
        sz = int(60 * theme["size_multiplier"] * getattr(self, 'adaptive_target_scale', 1.0))
        bubble_color = theme["primary_color"]

        positions = [
            (200, 200), (GAME_AREA_WIDTH - 200, 200),
            (200, WINDOW_HEIGHT - 150), (GAME_AREA_WIDTH - 200, WINDOW_HEIGHT - 150),
            (GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2)
        ]
        for x, y in positions:
            is_golden = random.random() < 0.2  # 20% golden
            color = (255, 215, 0) if is_golden else bubble_color
            vx = random.uniform(-2, 2) * spd
            vy = random.uniform(-2, 2) * spd
            bubble = Bubble(x, y, sz, color)
            bubble.vx = vx
            bubble.vy = vy
            bubble.is_golden = is_golden
            self.bubbles.append(bubble)
        if getattr(self, 'active_prescription', None) and getattr(self, 'active_prescription').difficulty_tier == 'EASY':
            self.bubbles[0].is_golden = True
        elif random.random() < 0.2:
            self.bubbles[0].is_golden = True

    def _spawn_precision_dots(self):
        from physio.models import PrecisionDot
        import random
        
        num_dots = 8
        target_size = 35
        
        # Use Adaptive Engine settings if available
        if getattr(self, 'active_prescription', None):
            tier = getattr(self, 'active_prescription').difficulty_tier
            if tier == 'EASY':
                num_dots = 5
                target_size = 50
            elif tier == 'HARD':
                num_dots = 12
                target_size = 25
        
        self.precision_dots = []
        self.precision_path_points = []
        self.precision_current_dot = 0
        
        margin = 100
        for i in range(num_dots):
            x = random.randint(margin, GAME_AREA_WIDTH - margin)
            y = random.randint(margin + 50, WINDOW_HEIGHT - margin)
            
            # Ensure dots don't overlap too much
            attempts = 0
            while attempts < 50 and any(distance((x, y), (d.x, d.y)) < target_size * 3 for d in self.precision_dots):
                x = random.randint(margin, GAME_AREA_WIDTH - margin)
                y = random.randint(margin + 50, WINDOW_HEIGHT - margin)
                attempts += 1
                
            self.precision_dots.append(PrecisionDot(x, y, target_size, i + 1))
            
        # Ensure first dot is marked active
        if self.precision_dots:
            self.precision_dots[0].state = "ACTIVE"

    def _spawn_precision_pathway(self):
        from physio.models import PathwayConfig
        import math
        
        width = 80
        if getattr(self, 'active_prescription', None):
            tier = getattr(self, 'active_prescription').difficulty_tier
            if tier == 'EASY':
                width = 120
            elif tier == 'HARD':
                width = 50
                
        points = []
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        
        import random
        path_types = ["Straight", "S-Curve", "Zig-Zag"]
        path_type = random.choice(path_types)
        
        if path_type == "Straight":
            points = [(150, cy), (GAME_AREA_WIDTH - 150, cy)]
        elif path_type == "S-Curve":
            for i in range(101):
                t = i / 100.0
                x = 150 + t * (GAME_AREA_WIDTH - 300)
                y = cy + math.sin(t * math.pi * 2) * 150
                points.append((x, y))
        elif path_type == "Zig-Zag":
            points = [
                (150, cy),
                (300, cy - 150),
                (500, cy + 150),
                (700, cy - 150),
                (GAME_AREA_WIDTH - 150, cy)
            ]
            
        self.pathway_config = PathwayConfig(
            path_type=path_type,
            points=points,
            width=width,
            recommended_direction="Right"
        )
        self.pathway_started = True
        self.pathway_boundary_violations = 0
        self.pathway_total_deviation = 0.0
        self.pathway_samples = 0
        self.pathway_current_proj = points[0]
        self.pathway_grabbed = False

    def _spawn_falling_item(self):
        theme = self._get_theme()
        spd = theme["speed_multiplier"] * getattr(self, 'adaptive_speed_scale', 1.0)
        sz = int(25 * theme["size_multiplier"] * getattr(self, 'adaptive_target_scale', 1.0))

        x = random.randint(100, GAME_AREA_WIDTH - 100)
        y = -30

        rand = random.random()
        if rand < 0.15:  # 15% bombs
            item = FallingItem(x, y, sz, 3 * spd, (255, 50, 50))
            item.is_bomb = True
        elif rand < 0.20:  # 5% 2x power-ups
            item = FallingItem(x, y, int(sz * 0.8), 2.5 * spd, (255, 215, 0))
            item.is_powerup = True
        elif rand < 0.25:  # 5% shields
            item = FallingItem(x, y, int(sz * 0.8), 2.5 * spd, (0, 200, 255))
            item.is_shield = True
        elif rand < 0.30:  # 5% freeze
            item = FallingItem(x, y, int(sz * 0.8), 2.5 * spd, (100, 255, 255))
            item.is_freeze = True
        else:  # 70% normal
            item = FallingItem(x, y, sz, 3 * spd, theme["secondary_color"])

        self.falling_items.append(item)

    def _spawn_seed(self):
        theme = self._get_theme()
        spd = theme["speed_multiplier"] * getattr(self, 'adaptive_speed_scale', 1.0)
        sz = int(18 * theme["size_multiplier"] * getattr(self, 'adaptive_target_scale', 1.0))

        x = random.randint(100, GAME_AREA_WIDTH - 100)
        y = -30
        is_golden = random.random() < 0.25  # 25% golden
        seed = Seed(x, y, sz, 2.5 * spd, False)
        seed.is_golden = is_golden
        self.seeds.append(seed)
    

    def _draw_level7(self):
        """Draw Level 7: Rotation Orbit"""
        import math
        import pygame
        theme = self._get_theme()
        primary = theme['primary_color']
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        orbit_radius = 200
        
        level_name = theme.get('level7_name', 'Rotation Orbit')
        title = getattr(self, 'font_medium').render(f"LEVEL 7: {level_name}", True, primary)
        self.screen.blit(title, (50, 85))
        
        # 1. Draw Planet (Center)
        pygame.draw.circle(self.screen, (20, 50, 100), (cx, cy), 60) # Core
        pygame.draw.circle(self.screen, primary, (cx, cy), 60, 3) # Atmosphere
        
        # 2. Draw Orbital Ring
        pygame.draw.circle(self.screen, (50, 50, 50), (cx, cy), orbit_radius, 2)
        
        # 3. Draw Target Zone (Asteroid/Space Station)
        target_rad = math.radians(self.wrist_target_angle)
        tx = cx + int(math.cos(target_rad) * orbit_radius)
        ty = cy + int(math.sin(target_rad) * orbit_radius)
        
        # Draw target zone glow based on hold time
        hold_pct = min(self.wrist_hold_time / 1.5, 1.0)
        target_color = (int(255 * hold_pct), 255, int(255 * (1-hold_pct)))
        pygame.draw.circle(self.screen, target_color, (tx, ty), 35, 4)
        pygame.draw.circle(self.screen, target_color, (tx, ty), int(35 * hold_pct)) # Fill up
        
        # 4. Draw Satellite (Patient's Forearm Rotation)
        # Using a dummy object hand_data, but we need to access it via self or pass it. 
        # _draw_level7 doesn't take hand_data, so we read it from self if available or we store current_angle in _update_level7.
        # Let's fix that by storing satellite_angle in self during _update_level7.
        # Fallback to 0 if not set.
        sat_angle = getattr(self, 'satellite_angle', 0.0)
        sat_rad = math.radians(sat_angle)
        sx = cx + int(math.cos(sat_rad) * orbit_radius)
        sy = cy + int(math.sin(sat_rad) * orbit_radius)
        
        pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), 15)
        pygame.draw.circle(self.screen, primary, (sx, sy), 20, 2)
        
        # Draw tether from planet to satellite
        pygame.draw.line(self.screen, (100, 100, 100), (cx, cy), (sx, sy), 1)

    def _draw_level8(self):
        """Draw Level 8: Smart Assembly"""
        theme = self._get_theme()
        primary = theme['primary_color']
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        
        level_name = theme.get('level8_name', 'Toy Builder')
        title = getattr(self, 'font_medium').render(f"LEVEL 8: {level_name}", True, primary)
        self.screen.blit(title, (50, 85))
        
        import math
        import pygame
        
        def rotate_polygon(points, angle_deg, offset_x, offset_y):
            rad = math.radians(angle_deg)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            rotated = []
            for px, py in points:
                rx = px * cos_a - py * sin_a
                ry = px * sin_a + py * cos_a
                rotated.append((rx + offset_x, ry + offset_y))
            return rotated

        for part in getattr(self, 'assembly_parts', []):
            blueprint_poly = rotate_polygon(part.shape, part.target_angle, part.target_pos[0], part.target_pos[1])
            pygame.draw.polygon(self.screen, (50, 50, 50), blueprint_poly, 2)
            
        for part in getattr(self, 'assembly_parts', []):
            if not part.is_locked:
                poly = rotate_polygon(part.shape, part.current_angle, part.current_pos[0], part.current_pos[1])
                color = (255,255,255) if part.is_grabbed else part.color
                pygame.draw.polygon(self.screen, color, poly)
                pygame.draw.polygon(self.screen, (200,200,200), poly, 2)
            else:
                poly = rotate_polygon(part.shape, part.target_angle, part.target_pos[0], part.target_pos[1])
                pygame.draw.polygon(self.screen, part.color, poly)
                pygame.draw.polygon(self.screen, (0, 255, 0), poly, 3)

        inst = getattr(self, 'font_small').render("PINCH to grab, ARM to move, WRIST to rotate", True, (200, 200, 200))
        self.screen.blit(inst, inst.get_rect(center=(cx, WINDOW_HEIGHT - 40)))

    def _draw_level9(self):
        theme = self._get_theme()
        primary = theme["primary_color"]
        
        title = self.font_medium.render("LEVEL 9: Precision Path", True, primary)
        self.screen.blit(title, (GAME_AREA_WIDTH // 2 - title.get_width() // 2, 60))
        
        # Draw path lines
        if len(self.precision_path_points) >= 2:
            pygame.draw.lines(self.screen, (0, 255, 200), False, self.precision_path_points, 3)
            
        # If there's a current dot, draw a line from last point to current index tip
        if self.precision_path_points and self.precision_current_dot < len(self.precision_dots):
            hand_data = self.hand_engine.get_hand_data()
            if hand_data and hand_data.index_tip:
                pygame.draw.line(self.screen, (0, 255, 200, 100), self.precision_path_points[-1], hand_data.index_tip, 2)

        # Draw dots
        import time
        import math
        for dot in getattr(self, 'precision_dots', []):
            color = (100, 100, 100) # WAITING
            if dot.state == "ACTIVE":
                color = (0, 255, 200)
                # Pulsing effect
                pulse = int(math.sin(time.time() * 5) * 5)
                pygame.draw.circle(self.screen, color, (int(dot.x), int(dot.y)), dot.radius + pulse, 2)
            elif dot.state == "COMPLETED":
                color = (0, 150, 100)
            
            pygame.draw.circle(self.screen, color, (int(dot.x), int(dot.y)), dot.radius)
            pygame.draw.circle(self.screen, (255, 255, 255), (int(dot.x), int(dot.y)), dot.radius, 2)
            
            # Number
            num_surf = self.font_small.render(str(dot.order), True, (0, 0, 0) if dot.state == "COMPLETED" else (255, 255, 255))
            self.screen.blit(num_surf, (dot.x - num_surf.get_width()//2, dot.y - num_surf.get_height()//2))

    def _draw_level10(self):
        theme = self._get_theme()
        primary = theme["primary_color"]
        
        title = self.font_medium.render("LEVEL 10: Precision Pathway", True, primary)
        self.screen.blit(title, (GAME_AREA_WIDTH // 2 - title.get_width() // 2, 85))
        
        if not getattr(self, 'pathway_config', None):
            return
            
        points = self.pathway_config.points
        width = self.pathway_config.width
        
        if len(points) >= 2:
            # Draw boundary (thicker line behind)
            pygame.draw.lines(self.screen, (40, 40, 60), False, points, int(width))
            # Draw centerline
            pygame.draw.lines(self.screen, primary, False, points, 2)
            
            # Start and End markers
            start_p = getattr(self, 'pathway_current_proj', points[0])
            end_p = points[-1]
            pygame.draw.circle(self.screen, (100, 255, 100), (int(start_p[0]), int(start_p[1])), 15)
            self.screen.blit(self.font_tiny.render("START", True, (255,255,255)), (start_p[0]-20, start_p[1]-30))
            
            pygame.draw.circle(self.screen, (255, 100, 100), (int(end_p[0]), int(end_p[1])), 15)
            self.screen.blit(self.font_tiny.render("END", True, (255,255,255)), (end_p[0]-15, end_p[1]-30))

    def _spawn_coin_vault(self):
        """Initialize Level 11 coins, vaults, and state machine."""
        tier = int(getattr(self, 'difficulty_tier', 3))
        target_scale = float(getattr(self, 'adaptive_target_scale', 1.0))
        
        # Dimensions and positioning with wide safety margins to guarantee zero panel overlap
        vw = int(135 * target_scale)
        vh = int(72 * target_scale)
        margin_x = 24
        margin_y_top = 90
        margin_y_bottom = 24
        
        self.vaults = [
            Vault("GOLD", "1", (255, 215, 0), margin_x, margin_y_top, vw, vh),
            Vault("BLUE", "2", (0, 180, 255), GAME_AREA_WIDTH - vw - margin_x, margin_y_top, vw, vh),
            Vault("GREEN", "3", (50, 230, 140), margin_x, WINDOW_HEIGHT - vh - margin_y_bottom, vw, vh),
            Vault("RED", "4", (240, 70, 90), GAME_AREA_WIDTH - vw - margin_x, WINDOW_HEIGHT - vh - margin_y_bottom, vw, vh)
        ]
        
        coin_counts = {1: 3, 2: 3, 3: 4, 4: 4, 5: 5}
        total_coins = coin_counts.get(tier, 4)
        
        vault_types = [
            ("GOLD", "1", (255, 215, 0)),
            ("BLUE", "2", (0, 180, 255)),
            ("GREEN", "3", (50, 230, 140)),
            ("RED", "4", (240, 70, 90))
        ]
        
        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2 + 10
        coin_radius = int(24 * target_scale)
        
        self.coins = []
        for i in range(total_coins):
            vtype, sym, col = vault_types[i % len(vault_types)]
            self.coins.append(
                Coin(
                    coin_id=i + 1,
                    color_type=vtype,
                    symbol=sym,
                    color=col,
                    x=float(cx),
                    y=float(cy),
                    radius=float(coin_radius),
                    target_vault=vtype,
                    state="PRESENTED",
                    spawn_timestamp=time.time()
                )
            )
        
        self.current_coin_idx = 0
        self.active_coin = self.coins[0] if self.coins else None
        self.manipulation_state = "COIN_PRESENTED"
        self.in_hand_shift_start = 0.0
        self.shift_progress = 0.0
        self.coin_grabbed_in_placement = True
        self.manipulation_times = []
        self.placement_times = []
        self.successful_pickups = 0
        self.pickup_attempts = 0
        self.successful_translations = 0
        self.translation_attempts = 0
        self.successful_placements = 0
        self.placement_attempts = 0
        self.unintended_drops = 0
        self.correction_count = 0
        self.occlusion_grace_frames = 0
        self.manipulation_time_avg = 0.0
        self.placement_time_avg = 0.0

    def _update_level11(self, hand_data: HandData):
        """
        Level 11: Coin Vault - In-Hand Manipulation
        Accuracy Type: manipulation_success_rate
        Measures virtual in-hand manipulation performance (finger-to-palm translation,
        in-hand shift holding, palm-to-finger repositioning, and vault placement).
        Does NOT physically measure objects occluded inside the palm; implements an inferred
        webcam-derived virtual manipulation proxy with anti-cheat state validation.
        """
        if not self.active_coin or self.current_coin_idx >= len(self.coins):
            self._end_level()
            return
            
        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2 + 10
        now = time.time()
        target_scale = float(getattr(self, 'adaptive_target_scale', 1.0))
        
        # Self-occlusion grace buffer (cushions momentary loss during complex hand flexion)
        if hand_data.index_tip is None or hand_data.thumb_tip is None:
            self.occlusion_grace_frames = getattr(self, 'occlusion_grace_frames', 0) + 1
            if self.occlusion_grace_frames > 25:
                # Prolonged loss handled by global system freeze
                pass
            return
        
        self.occlusion_grace_frames = 0
        pinch_pos = (
            (hand_data.index_tip[0] + hand_data.thumb_tip[0]) // 2,
            (hand_data.index_tip[1] + hand_data.thumb_tip[1]) // 2
        )
        idx_pos = hand_data.index_tip
        palm_pos = hand_data.palm_center or hand_data.wrist or pinch_pos
        
        # Hand-relative normalized distance metrics
        palm_span = distance(hand_data.wrist, palm_pos) if hand_data.wrist else 100.0
        dist_pinch_to_palm = distance(pinch_pos, palm_pos)
        rel_palm_dist = dist_pinch_to_palm / max(35.0, palm_span)
        avg_knuckle = sum(hand_data.knuckle_angles) / len(hand_data.knuckle_angles) if hand_data.knuckle_angles else 90.0

        # --- STATE MACHINE ---
        if self.manipulation_state in ("READY", "COIN_PRESENTED"):
            self.active_coin.x = float(cx)
            self.active_coin.y = float(cy)
            
            # Check for pickup: pinch within coin proximity (check both pinch point and visible index tip)
            dist_pinch = distance(pinch_pos, (self.active_coin.x, self.active_coin.y))
            dist_idx = distance(idx_pos, (self.active_coin.x, self.active_coin.y))
            dist_to_coin = min(dist_pinch, dist_idx)
            pickup_radius = self.active_coin.radius + (45.0 * target_scale)
            
            if hand_data.is_pinching and dist_to_coin < pickup_radius:
                self.successful_pickups += 1
                self.pickup_attempts += 1
                self.accuracy_attempts += 1
                self.active_coin.pickup_timestamp = now
                self.active_coin.state = "PICKED_UP"
                self.manipulation_state = "IN_HAND_TRANSLATION"
                self.manipulation_phase_start = now
                self.sounds.play('catch')
                self.particles.emit(int(self.active_coin.x), int(self.active_coin.y), self.active_coin.color, 16)
                self.popups.append(ScorePopup(self.active_coin.x, self.active_coin.y - 30, "PICKED UP! FOLD INTO PALM"))
                
        elif self.manipulation_state == "IN_HAND_TRANSLATION":
            # Coin follows pinch point while translating
            self.active_coin.x = float(pinch_pos[0])
            self.active_coin.y = float(pinch_pos[1])
            
            # Unintended drop if released when far from palm
            if not hand_data.is_pinching and rel_palm_dist > 0.65:
                self.unintended_drops += 1
                self.active_coin.state = "PRESENTED"
                self.manipulation_state = "COIN_PRESENTED"
                self.sounds.play('pop')
                self.popups.append(ScorePopup(pinch_pos[0], pinch_pos[1] - 30, "DROPPED! RETRY PICKUP"))
                return
                
            # Finger-to-palm transition detected: pinch approaches palm center or hand flexes
            if rel_palm_dist < 0.45 or avg_knuckle < 58.0 or getattr(hand_data, 'is_fist', False):
                self.active_coin.state = "PALM_HOLD"
                self.manipulation_state = "IN_HAND_SHIFT"
                self.in_hand_shift_start = now
                self.active_coin.manipulation_start_timestamp = now
                self.sounds.play('select')
                self.particles.emit(int(palm_pos[0]), int(palm_pos[1]), (0, 220, 255), 18)
                self.popups.append(ScorePopup(palm_pos[0], palm_pos[1] - 30, "PALM HOLD: REPOSITION COIN"))
                
        elif self.manipulation_state == "IN_HAND_SHIFT":
            # Coin rests in palm pocket
            self.active_coin.x = float(palm_pos[0])
            self.active_coin.y = float(palm_pos[1])
            
            # Anti-cheat hold duration requirement
            req_hold = max(0.8, float(getattr(self, 'rotation_hold_required', 1.5)))
            elapsed = now - self.in_hand_shift_start
            self.shift_progress = min(1.0, elapsed / req_hold)
            
            # Unintended drop if hand flings wide open prematurely
            if rel_palm_dist > 0.75 and elapsed < 0.35 and not getattr(hand_data, 'is_fist', False) and avg_knuckle > 80.0:
                self.unintended_drops += 1
                self.active_coin.state = "PRESENTED"
                self.manipulation_state = "COIN_PRESENTED"
                self.sounds.play('pop')
                self.popups.append(ScorePopup(palm_pos[0], palm_pos[1] - 30, "LOST CONTROL IN PALM!"))
                return
                
            if self.shift_progress >= 1.0:
                self.successful_translations += 1
                self.translation_attempts += 1
                self.active_coin.manipulation_end_timestamp = now
                manip_duration = self.active_coin.manipulation_end_timestamp - self.active_coin.manipulation_start_timestamp
                self.manipulation_times.append(manip_duration)
                self.active_coin.state = "PALM_TO_FINGERTIP"
                self.manipulation_state = "PALM_TO_FINGERTIP"
                self.sounds.play('select')
                self.particles.emit(int(palm_pos[0]), int(palm_pos[1]), (50, 255, 150), 20)
                self.popups.append(ScorePopup(palm_pos[0], palm_pos[1] - 35, "BRING TO FINGERTIPS!"))
                
        elif self.manipulation_state == "PALM_TO_FINGERTIP":
            # Patient extends fingers outward to present coin at fingertips
            self.active_coin.x = float(lerp(self.active_coin.x, pinch_pos[0], 0.25))
            self.active_coin.y = float(lerp(self.active_coin.y, pinch_pos[1], 0.25))
            
            is_extended = (rel_palm_dist > 0.55 or getattr(hand_data, 'finger_extension', 0.0) > 0.35 or avg_knuckle > 60.0 or not getattr(hand_data, 'is_fist', False))
            if is_extended:
                self.active_coin.state = "READY_FOR_PLACEMENT"
                self.manipulation_state = "TARGET_PLACEMENT"
                self.placement_phase_start = now
                self.coin_grabbed_in_placement = True
                self.sounds.play('pop')
                self.popups.append(ScorePopup(pinch_pos[0], pinch_pos[1] - 30, f"PLACE IN {self.active_coin.target_vault} VAULT!"))
                
        elif self.manipulation_state == "TARGET_PLACEMENT":
            tol = float(getattr(self, 'assembly_position_tolerance', 50.0))
            is_grabbed = getattr(self, 'coin_grabbed_in_placement', True)
            
            # Re-grab check: if the coin was released and sits at center, permit picking it up again
            if not is_grabbed:
                dist_pinch = distance(pinch_pos, (self.active_coin.x, self.active_coin.y))
                dist_idx = distance(idx_pos, (self.active_coin.x, self.active_coin.y))
                grab_rad = self.active_coin.radius + (45.0 * target_scale)
                if hand_data.is_pinching and min(dist_pinch, dist_idx) < grab_rad:
                    self.coin_grabbed_in_placement = True
                    is_grabbed = True
                    self.sounds.play('select')
                    self.popups.append(ScorePopup(self.active_coin.x, self.active_coin.y - 25, "GRABBED!"))
            
            if is_grabbed:
                # Coin follows pinch point for precision placement
                self.active_coin.x = float(pinch_pos[0])
                self.active_coin.y = float(pinch_pos[1])
                
                # Check placement in vaults upon pinch release
                if not hand_data.is_pinching:
                    placed_in_vault = None
                    for v in self.vaults:
                        if (v.x - tol <= self.active_coin.x <= v.x + v.w + tol and
                            v.y - tol <= self.active_coin.y <= v.y + v.h + tol):
                            placed_in_vault = v
                            break
                            
                    if placed_in_vault is not None:
                        self.placement_attempts += 1
                        if placed_in_vault.vault_id == self.active_coin.target_vault:
                            # SUCCESS: Correct vault!
                            self.successful_placements += 1
                            self.accuracy_hits += 1
                            self.active_coin.placement_timestamp = now
                            place_duration = self.active_coin.placement_timestamp - self.placement_phase_start
                            self.placement_times.append(place_duration)
                            placed_in_vault.coins_collected += 1
                            self.active_coin.state = "PLACED"
                            self.coin_grabbed_in_placement = False
                            
                            pts = int(40 * self.score_multiplier)
                            self.score += pts
                            self.combo += 1
                            self.consecutive_misses = 0
                            self.sounds.play('level_complete')
                            self.particles.emit(int(self.active_coin.x), int(self.active_coin.y), self.active_coin.color, 30)
                            self.popups.append(ScorePopup(self.active_coin.x, self.active_coin.y - 30, f"+{pts} VAULT SECURED!"))
                            
                            # Advance to next coin
                            self.current_coin_idx += 1
                            if self.current_coin_idx < len(self.coins):
                                self.active_coin = self.coins[self.current_coin_idx]
                                self.active_coin.spawn_timestamp = now
                                self.manipulation_state = "COIN_PRESENTED"
                            else:
                                self.manipulation_time_avg = round(sum(self.manipulation_times) / len(self.manipulation_times), 3) if self.manipulation_times else 0.0
                                self.placement_time_avg = round(sum(self.placement_times) / len(self.placement_times), 3) if self.placement_times else 0.0
                                self._end_level()
                            return
                        else:
                            # Mismatched vault
                            self.correction_count += 1
                            self.combo = 0
                            self.coin_grabbed_in_placement = False
                            self.sounds.play('pop')
                            self.popups.append(ScorePopup(self.active_coin.x, self.active_coin.y - 30, f"WRONG VAULT! NEED {self.active_coin.target_vault}"))
                            self.active_coin.x = float(cx)
                            self.active_coin.y = float(cy)
                            self.active_coin.state = "READY_FOR_PLACEMENT"
                            return
                    else:
                        # Released outside any vault
                        self.unintended_drops += 1
                        self.coin_grabbed_in_placement = False
                        self.sounds.play('pop')
                        self.popups.append(ScorePopup(self.active_coin.x, self.active_coin.y - 30, "DROPPED! RETRY PLACEMENT"))
                        self.active_coin.x = float(cx)
                        self.active_coin.y = float(cy)
                        self.active_coin.state = "READY_FOR_PLACEMENT"
                        return

        # Check time limit
        time_expired = (time.time() - self.session_start > self.session_time_limit) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5)
        if time_expired:
            self.manipulation_time_avg = round(sum(self.manipulation_times) / len(self.manipulation_times), 3) if self.manipulation_times else 0.0
            self.placement_time_avg = round(sum(self.placement_times) / len(self.placement_times), 3) if self.placement_times else 0.0
            self._end_level()

    def _draw_level11(self):
        theme = self._get_theme()
        primary = theme.get("primary_color", (0, 200, 255))
        level_name = theme.get("level11_name", "Coin Vault")
        
        # Cached font resolution (safely falls back if running in test harnesses)
        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 22, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 13)
        font_vault = getattr(self, 'font_vault', None) or pygame.font.SysFont("segoeui", 12, bold=True)
        font_phase = getattr(self, 'font_phase', None) or pygame.font.SysFont("segoeui", 10, bold=True)
        font_coin = getattr(self, 'font_coin', None) or pygame.font.SysFont("segoeui", 18, bold=True)
        font_tiny = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 11)
        
        # Header title (centered neatly between top vaults, cleared below HUD)
        title_surf = font_head.render(f"LEVEL 11: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, title_surf.get_rect(center=(GAME_AREA_WIDTH // 2, 92)))
        
        sub_surf = font_hint.render("In-Hand Dexterity & Vault Sorting", True, (160, 195, 225))
        self.screen.blit(sub_surf, sub_surf.get_rect(center=(GAME_AREA_WIDTH // 2, 116)))
        
        # Draw 4 Cyber-Clinical Vault Receptacles in the 4 corners
        for v in getattr(self, 'vaults', []):
            v_rect = pygame.Rect(v.x, v.y, v.w, v.h)
            is_target = bool(self.active_coin and self.active_coin.target_vault == v.vault_id)
            
            # Subtle background glassmorphism panel
            bg_surf = pygame.Surface((v.w, v.h), pygame.SRCALPHA)
            bg_alpha = 75 if is_target else 28
            bg_surf.fill((*v.color, bg_alpha))
            self.screen.blit(bg_surf, (v.x, v.y))
            
            # Vault Border with neon pulse if active target
            if is_target:
                pulse = int(3 * math.sin(time.time() * 6))
                glow_rect = v_rect.inflate(4 + pulse * 2, 4 + pulse * 2)
                pygame.draw.rect(self.screen, v.color, glow_rect, 1, border_radius=12)
                pygame.draw.rect(self.screen, v.color, v_rect, 3, border_radius=10)
            else:
                pygame.draw.rect(self.screen, (55, 70, 95), v_rect, 1, border_radius=10)
            
            # Number badge and Vault Label
            badge_r = 9
            bx = v.x + 18
            by = v.y + 18
            pygame.draw.circle(self.screen, v.color, (bx, by), badge_r)
            badge_txt = font_phase.render(v.symbol, True, (15, 20, 30))
            self.screen.blit(badge_txt, badge_txt.get_rect(center=(bx, by)))
            
            v_title = font_vault.render(f"{v.vault_id} VAULT", True, v.color if is_target else (210, 225, 240))
            self.screen.blit(v_title, (bx + badge_r + 6, v.y + 11))
            
            # Vault Coin Drop Slot graphic
            slot_rect = pygame.Rect(v.x + 12, v.y + 34, v.w - 24, 6)
            pygame.draw.rect(self.screen, (10, 15, 25), slot_rect, border_radius=3)
            pygame.draw.rect(self.screen, v.color if is_target else (55, 70, 95), slot_rect, 1, border_radius=3)
            
            # Stored coins count and dots
            cnt_text = f"Stored: {v.coins_collected}"
            cnt_surf = font_tiny.render(cnt_text, True, (215, 225, 235))
            self.screen.blit(cnt_surf, (v.x + 12, v.y + v.h - 18))
            
            # Draw mini stored token dots
            for c_i in range(min(4, v.coins_collected)):
                dot_x = v.x + v.w - 14 - (c_i * 9)
                dot_y = v.y + v.h - 12
                pygame.draw.circle(self.screen, v.color, (dot_x, dot_y), 3)
                pygame.draw.circle(self.screen, (255, 255, 255), (dot_x, dot_y), 3, 1)

        # Draw In-Hand Process Flow Steps (Pill Ribbon centered, 100+ px clearance from vaults)
        phases = [
            ("1. PICKUP", self.manipulation_state in ("READY", "COIN_PRESENTED")),
            ("2. TO PALM", self.manipulation_state in ("IN_HAND_TRANSLATION", "IN_HAND_SHIFT")),
            ("3. TO FINGERS", self.manipulation_state == "PALM_TO_FINGERTIP"),
            ("4. DOCK VAULT", self.manipulation_state == "TARGET_PLACEMENT")
        ]
        pill_w = 88
        gap = 6
        total_bar_w = (pill_w * 4) + (gap * 3)  # 370px
        start_bx = (GAME_AREA_WIDTH - total_bar_w) // 2  # 295px
        bar_y = 138
        
        for idx, (pname, is_active) in enumerate(phases):
            px = start_bx + idx * (pill_w + gap)
            p_rect = pygame.Rect(px, bar_y, pill_w, 22)
            
            p_surf = pygame.Surface((pill_w, 22), pygame.SRCALPHA)
            p_surf.fill((0, 200, 255, 80) if is_active else (20, 26, 40, 180))
            self.screen.blit(p_surf, (px, bar_y))
            pygame.draw.rect(self.screen, (0, 220, 255) if is_active else (50, 65, 85), p_rect, 2 if is_active else 1, border_radius=6)
            
            txt_surf = font_phase.render(pname, True, (255, 255, 255) if is_active else (140, 160, 180))
            self.screen.blit(txt_surf, txt_surf.get_rect(center=p_rect.center))

        # Draw Central Prompt & Active Coin
        if self.active_coin and self.active_coin.state != "PLACED":
            ac = self.active_coin
            cx, cy = int(ac.x), int(ac.y)
            rad = int(ac.radius)
            
            # Floating Guidance Prompt Badge (elevated cleanly above coin with dark backing bubble)
            prompt_str = None
            prompt_col = (240, 248, 255)
            
            if self.manipulation_state in ("READY", "COIN_PRESENTED"):
                pulse_r = int(rad + 12 + 3 * math.sin(time.time() * 5))
                pygame.draw.circle(self.screen, (*ac.color, 90), (cx, cy), pulse_r, 2)
                prompt_str = "PINCH TO PICK UP"
                prompt_col = (240, 248, 255)
                
            elif self.manipulation_state == "IN_HAND_TRANSLATION":
                prompt_str = "FOLD FINGERS INTO PALM"
                prompt_col = (0, 220, 255)
                
            elif self.manipulation_state == "PALM_TO_FINGERTIP":
                prompt_str = "BRING TO FINGERTIPS"
                prompt_col = (50, 255, 150)
                
            elif self.manipulation_state == "TARGET_PLACEMENT":
                target_v = next((v for v in getattr(self, 'vaults', []) if v.vault_id == ac.target_vault), None)
                if target_v:
                    tx = target_v.x + target_v.w // 2
                    ty = target_v.y + target_v.h // 2
                    pygame.draw.line(self.screen, (*ac.color, 70), (cx, cy), (tx, ty), 2)
                
                is_held = getattr(self, 'coin_grabbed_in_placement', True)
                prompt_str = f"PLACE IN {ac.target_vault} VAULT" if is_held else "PINCH TO PICK UP AGAIN"
                prompt_col = ac.color if is_held else (255, 180, 50)
            
            if prompt_str:
                p_surf = font_hint.render(prompt_str, True, prompt_col)
                p_rect = p_surf.get_rect(center=(cx, cy - rad - 28))
                bg_bubble = p_rect.inflate(18, 8)
                bg_bubble_surf = pygame.Surface((bg_bubble.width, bg_bubble.height), pygame.SRCALPHA)
                bg_bubble_surf.fill((16, 22, 36, 215))
                self.screen.blit(bg_bubble_surf, bg_bubble.topleft)
                pygame.draw.rect(self.screen, (0, 180, 220), bg_bubble, 1, border_radius=6)
                self.screen.blit(p_surf, p_rect)

            # Drop shadow under coin
            shadow_surf = pygame.Surface((rad * 2 + 16, rad + 10), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_surf, (0, 0, 0, 95), shadow_surf.get_rect())
            self.screen.blit(shadow_surf, (cx - rad - 8, cy + rad - 4))
            
            # Subtle glow around coin during palm hold
            if self.manipulation_state == "IN_HAND_SHIFT":
                glow_surf = pygame.Surface((rad * 4, rad * 4), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, (*ac.color, 60), (rad * 2, rad * 2), rad + 14)
                self.screen.blit(glow_surf, (cx - rad * 2, cy - rad * 2))
                
            # Coin Outer Rim (Metallic Bevel)
            pygame.draw.circle(self.screen, (245, 245, 250), (cx, cy), rad + 2)
            # Coin Face
            pygame.draw.circle(self.screen, ac.color, (cx, cy), rad)
            # Coin Inner Rim
            pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), max(2, rad - 4), 1)
            
            # Specular shine glint
            glint_x = int(cx - rad * 0.35)
            glint_y = int(cy - rad * 0.35)
            pygame.draw.circle(self.screen, (255, 255, 255), (glint_x, glint_y), max(2, rad // 6))
            
            # Symbol text inside coin with drop shadow
            sym_shadow = font_coin.render(ac.symbol, True, (0, 0, 0))
            self.screen.blit(sym_shadow, sym_shadow.get_rect(center=(cx + 1, cy + 1)))
            sym_surf = font_coin.render(ac.symbol, True, (20, 22, 35))
            self.screen.blit(sym_surf, sym_surf.get_rect(center=(cx, cy)))

        # Palm Shift Hold Progress Ring & Guidance
        if self.manipulation_state == "IN_HAND_SHIFT":
            prog = getattr(self, 'shift_progress', 0.0)
            prog_w = 260
            prog_h = 16
            prog_x = (GAME_AREA_WIDTH - prog_w) // 2
            prog_y = WINDOW_HEIGHT // 2 + 75
            
            # Progress bar track
            pygame.draw.rect(self.screen, (22, 28, 44), (prog_x, prog_y, prog_w, prog_h), border_radius=8)
            fill_w = int(prog_w * prog)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (0, 230, 140), (prog_x, prog_y, fill_w, prog_h), border_radius=8)
            pygame.draw.rect(self.screen, (0, 180, 220), (prog_x, prog_y, prog_w, prog_h), 2, border_radius=8)
            
            hold_lbl = font_hint.render(f"Manipulating In Palm: {int(prog * 100)}%", True, (255, 255, 255))
            self.screen.blit(hold_lbl, hold_lbl.get_rect(center=(GAME_AREA_WIDTH // 2, prog_y - 14)))

        # Bottom Interaction Stats HUD (cleanly centered, 100+ px clearance from bottom vaults)
        stats_w = 420
        stats_h = 32
        stats_x = (GAME_AREA_WIDTH - stats_w) // 2
        stats_y = WINDOW_HEIGHT - 52
        s_surf = pygame.Surface((stats_w, stats_h), pygame.SRCALPHA)
        s_surf.fill((16, 22, 36, 215))
        self.screen.blit(s_surf, (stats_x, stats_y))
        pygame.draw.rect(self.screen, (0, 180, 220), (stats_x, stats_y, stats_w, stats_h), 1, border_radius=8)
        
        target_name = self.active_coin.target_vault if self.active_coin else "DONE"
        hud_str = f"TARGET: {target_name}  |  Pickups: {self.successful_pickups}  |  Shifts: {self.successful_translations}  |  Secured: {self.successful_placements}  |  Drops: {self.unintended_drops}"
        hud_txt = font_tiny.render(hud_str, True, (210, 230, 250))
        self.screen.blit(hud_txt, hud_txt.get_rect(center=(stats_x + stats_w // 2, stats_y + stats_h // 2)))

    def _get_level_goals(self) -> str:
        if self.state == GameState.MAIN_MENU:
            return "Select a level to begin rehabilitation"
        elif self.state == GameState.LEVEL1_FLEXIBILITY:
            return "Reach and touch bubbles across the screen for reaching range and target acquisition"
        elif self.state == GameState.LEVEL2_STRENGTH:
            return "Move palm to catch falling items to train horizontal agility and coordination"
        elif self.state == GameState.LEVEL3_FINEMOTOR:
            return "Pinch seeds and drop them in the pot for fine-motor pinch practice"
        elif self.state == GameState.LEVEL4_COORDINATION:
            return "Follow the moving target smoothly to test hand stability and path coordination"
        elif self.state == GameState.LEVEL5_GRIP_RELEASE:
            return "Make a FIST, then OPEN fully to practice repetitive grip and release cycles!"
        elif self.state == GameState.LEVEL6_FINGER_TAPS:
            return "Memorize the pattern and repeat it for cognitive-motor sequence training!"
        elif self.state == GameState.LEVEL9_PRECISION_PATH:
            return "Connect the numbered dots in sequence using your index fingertip."
        elif self.state == GameState.LEVEL10_PRECISION_PATHWAY:
            return "Guide your index finger from START to END along the pathway."
        elif self.state == GameState.LEVEL11_COIN_VAULT:
            return "Pinch coin -> Translate into palm -> Reposition within hand -> Place in matching vault!"
        return ""

    def _get_current_exercise_name(self) -> str:
        if self.state == GameState.MAIN_MENU:
            return "Therapy Selection"
        if self.state == GameState.CALIBRATION:
            return "ROM Diagnostics"
        return LEVEL_DISPLAY_NAMES.get(getattr(self, "current_level", 0), "Therapeutic Training")

    def _get_exercise_count(self) -> int:
        if getattr(self, "current_level", 0) == 5:
            return int(getattr(self, "pump_reps", 0))
        return int(getattr(self, "accuracy_hits", 0))

    def _get_session_elapsed(self) -> float:
        if self.session_start:
            return max(0.0, time.time() - self.session_start)
        return 0.0

    def _get_correctness_label(self, hand_data: HandData) -> str:
        warning = getattr(self, "correctness_warning", "")
        if warning:
            if "Bend" in warning:
                return "Incorrect - adjust movement"
            return "Correct - good control"
        if hand_data.index_tip is None:
            return "Incorrect - hand missing"
        return "Ready - tracking hand"

    def _get_recovery_prediction(self) -> Optional[float]:
        now = time.time()
        cache_time = getattr(self, "_recovery_prediction_time", 0.0)
        if now - cache_time > 5.0:
            try:
                self._recovery_prediction_cache = self.db.predict_recovery_progress(self.patient_name)
            except Exception:
                self._recovery_prediction_cache = -1.0
            self._recovery_prediction_time = now
        return getattr(self, "_recovery_prediction_cache", -1.0)
    
    def _reset_game(self):
        self.bubbles.clear()
        self.falling_items.clear()
        self.seeds.clear()
        self.score = 0
        self.max_extension = 0
        self.reach_distance = 0
        self.accuracy_hits = 0
        self.accuracy_attempts = 0
        self.angle_history.clear()
        self.combo = 0
        self.feedback_text = None
        self.feedback_timer = 0
        if hasattr(self, 'quality_tracker'):
            self.quality_tracker.reset()
        if hasattr(self, 'compensation_detector'):
            self.compensation_detector.reset()
    
    def _trigger_feedback(self):
        """Trigger visual feedback based on combo"""
        if self.combo >= 15 and "combo15" not in self.achievements_unlocked:
            self.achievements_unlocked.add("combo15")
            self.popups.append(ScorePopup(GAME_AREA_WIDTH//2, 120, "ACHIEVEMENT: 15 COMBO!"))
            self.sounds.play('level_complete')
            
        if self.combo >= 10:
            if "combo10" not in self.achievements_unlocked:
                self.achievements_unlocked.add("combo10")
                self.popups.append(ScorePopup(GAME_AREA_WIDTH//2, 120, "ACHIEVEMENT: 10 COMBO!"))
                self.sounds.play('level_complete')
            self.feedback_text = "AMAZING!"
            self.feedback_timer = 60
        elif self.combo >= 7:
            self.feedback_text = "EXCELLENT!"
            self.feedback_timer = 50
        elif self.combo >= 4:
            self.feedback_text = "GREAT!"
            self.feedback_timer = 40
            self.sounds.play('combo')
        elif self.combo >= 2:
            self.feedback_text = "GOOD!"
            self.feedback_timer = 30
            
    def _adjust_pacing(self, change_type: str):
        """Dynamic pacing adjustment with sound cues and visual popup HUD alerts."""
        now = time.time()
        should_speak = (now - getattr(self, 'last_pacing_voice_time', 0.0)) > 10.0

        if change_type == "slow":
            self.pacing_multiplier = max(0.5, self.pacing_multiplier - 0.15)
            self.sounds.play('select')
            self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2 - 80, WINDOW_HEIGHT // 2, "PACING: SLOWER", (255, 128, 0)))
            if should_speak:
                VOICE.speak("Pacing adjusted. Let's take it slow and steady.")
                self.last_pacing_voice_time = now
        elif change_type == "fast":
            self.pacing_multiplier = min(1.4, self.pacing_multiplier + 0.1)
            self.sounds.play('level_complete')
            self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2 - 80, WINDOW_HEIGHT // 2, "PACING: FASTER!", COLOR_SUCCESS))
            if should_speak:
                VOICE.speak("Excellent coordination! Pacing up slightly.")
                self.last_pacing_voice_time = now
    
    def _update_results(self, hand_data: HandData):
        """Update results screen"""
        # Debounce safeguard for hand lost tracking in results screen
        if hand_data.index_tip is None:
            if not hasattr(self, '_results_lost_t') or self._results_lost_t is None:
                self._results_lost_t = time.time()
            if time.time() - self._results_lost_t > 0.8:
                self.results_mirror_active = True
        else:
            self._results_lost_t = None
            self.results_mirror_active = False

        if self.close_button.update(hand_data.index_tip):
            self.running = False
        
        # PLAY AGAIN
        if self.menu_button.update(hand_data.index_tip):
            # Replay current level
            self.pending_level = self.current_level
            self._reset_game()
            self._start_level()
            self.sounds.play('select')
        
        # MAIN MENU (Via Cloud Sync)
        if self.home_button.update(hand_data.index_tip):
            self.state = GameState.CLOUD_SYNC
            self.sync_start = time.time()
            self.sounds.play('select')
            self.home_button.hover_start = None
            self.menu_button.hover_start = None
            self.close_button.hover_start = None
            if hasattr(self, 'next_button'):
                self.next_button.hover_start = None
                
        # NEXT GAME
        if hasattr(self, 'next_button') and getattr(self, 'current_level', 1) < 8 and self.next_button.update(hand_data.index_tip):
            self.pending_level = min(8, self.current_level + 1)
            self.sounds.play('select')
            self.menu_button.hover_start = None
            self.close_button.hover_start = None
            self.next_button.hover_start = None
            self.home_button.hover_start = None
            if not getattr(self, 'pain_checked', False):
                self.pain_level = 0
                self.state = GameState.PAIN_SCALE
            else:
                self._start_level()

    # ── Pain scale helpers ──────────────────────────────────────────────
    def _start_level(self):
        """Actually start the pending level after pain score captured"""
        self.game_has_started = False
        lv = self.pending_level or 1
        self.current_level = lv
        self.session_start = time.time()
        self.level_wall_start = time.time()
        self.score = 0
        self.max_extension = 0
        self.reach_distance = 0
        self.accuracy_hits = 0
        self.accuracy_attempts = 0
        self.tracking_frames_valid = 0
        self.tracking_frames_total = 0
        self.tracking_valid_duration = 0.0
        self.active_engagement_duration = 0.0
        self.session_aborted = 0
        
        level_accuracy_types = {
            1: "hit_rate",
            2: "hit_rate",
            3: "hit_rate",
            4: "proximity_rate",
            5: "completion_rate",
            6: "hit_rate",
            7: "hit_rate",
            8: "binary_completion",
            9: "hit_rate",
            10: "path_accuracy",
            11: "manipulation_success_rate"
        }
        self.accuracy_type = level_accuracy_types.get(lv, "hit_rate")
        
        self.pacing_multiplier = 1.0
        self.consecutive_misses = 0
        self.last_pacing_voice_time = 0.0
        self.recent_tracing_attempts = 0
        self.recent_tracing_hits = 0
        self._apply_adaptive_prescription(lv)
        if lv == 1:
            self.state = GameState.LEVEL1_FLEXIBILITY
            self._spawn_bubbles()
            VOICE.speak("Level 1: Bubble Pop. Extend your index finger and touch the moving bubbles to pop them and improve flexibility.")
        elif lv == 2:
            self.state = GameState.LEVEL2_STRENGTH
            VOICE.speak("Level 2: Fruit Catch. Move your hand left and right to catch the falling apples in the basket.")
        elif lv == 3:
            self.state = GameState.LEVEL3_FINEMOTOR
            VOICE.speak("Level 3: Fine Motor. Close your index and thumb to pinch and pick up seeds, then drop them in the pot.")
        elif lv == 4:
            self.state = GameState.LEVEL4_COORDINATION
            self.trace_t = 0.0
            self.trace_path = []
            VOICE.speak("Level 4: Trace the Path. Move your index finger along the dotted line to trace the medical pattern.")
        elif lv == 5:
            self.state = GameState.LEVEL5_GRIP_RELEASE
            self.pump_state = 0
            self.pump_reps = 0
            self.balloon_scale = 1.0
            self.grip_cycle_start = None
            self.last_rep_time = time.time()
            VOICE.speak("Level 5: Balloon Pump. Close your hand into a fist, then open it fully to pump up the balloon.")
        elif lv == 6:
            self.state = GameState.LEVEL6_FINGER_TAPS
            self.simon_sequence = []
            self.simon_state = "START"
            VOICE.speak("Level 6: Pattern Tap. Memorize the blinking pattern, then hover over the colored pads in correct order.")
        elif lv == 7:
            self.state = GameState.LEVEL7_WRIST_MECHANICS
            self.wrist_target_angle = 45.0
            self.wrist_hold_time = 0.0
            self.wrist_mode = "rotation"
            self.wrist_rotation_baseline = None
            VOICE.speak("Level 7: Rotation Orbit. Rotate your forearm to align the satellite with the orbital target.")
        elif lv == 8:
            self.state = GameState.LEVEL8_SMART_ASSEMBLY
            cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
            
            base_shape = [(-50, -50), (50, -50), (50, 50), (-50, 50)]
            roof_shape = [(-60, 40), (60, 40), (0, -40)]
            
            import random
            self.assembly_parts = [
                AssemblyPart("Base", (cx, cy+50), 0.0, [150.0, 200.0], random.uniform(-45, 45), (100, 150, 200), base_shape),
                AssemblyPart("Roof", (cx, cy-40), 0.0, [GAME_AREA_WIDTH-150.0, 200.0], random.uniform(-45, 45), (200, 100, 100), roof_shape)
            ]
            VOICE.speak("Level 8: Smart Assembly. Pinch a piece to grab it, drag it to the blueprint, and rotate your wrist to fit it.")
        elif lv == 9:
            self.state = GameState.LEVEL9_PRECISION_PATH
            self._spawn_precision_dots()
            VOICE.speak("Level 9: Precision Path. Connect the numbered dots in sequence using your index fingertip.")
        elif lv == 10:
            self.state = GameState.LEVEL10_PRECISION_PATHWAY
            self.pathway_started = False
            self.pathway_samples = 0
            self.pathway_on_path_samples = 0
            self.pathway_boundary_violations = 0
            self.pathway_total_deviation = 0.0
            VOICE.speak("Level 10: Precision Pathway. Carefully guide your index finger along the path from start to finish.")
        elif lv == 11:
            self.state = GameState.LEVEL11_COIN_VAULT
            self._spawn_coin_vault()
            VOICE.speak("Level 11: Coin Vault. Pinch the coin, translate it into your palm, reposition it within your hand, and place it in the matching vault.")
        self.sounds.play('select')
        self.popups.append(ScorePopup(GAME_AREA_WIDTH//2, WINDOW_HEIGHT//2 - 60, "POSTURE FIX: Sit up & keep shoulders relaxed!"))

    def _apply_adaptive_prescription(self, level: int):
        """Load the latest AI prescription and map it onto game parameters."""
        try:
            prescription = self.adaptive_engine.latest_prescription(self.patient_name or "Unknown", level)
        except Exception as exc:
            print(f"Adaptive prescription unavailable: {exc}")
            prescription = None

        self.active_prescription = prescription
        self.adaptive_target_scale = getattr(prescription, "target_scale", 1.0)
        self.adaptive_speed_scale = getattr(prescription, "speed_scale", 1.0)
        self.session_time_limit = getattr(prescription, "time_limit", self.session_time_limit)
        self.adaptive_guidance_level = getattr(prescription, "guidance_level", "standard")
        self.rotation_tolerance = getattr(prescription, "rotation_tolerance", 25.0)
        self.rotation_hold_required = getattr(prescription, "hold_seconds", 1.5)
        self.assembly_position_tolerance = getattr(prescription, "assembly_position_tolerance", 50.0)
        self.assembly_angle_tolerance = getattr(prescription, "assembly_angle_tolerance", 30.0)
        self.forearm_angle_history.clear()
        self.forearm_assessment = None

        if prescription:
            print(
                "[ADAPTIVE] "
                f"L{level} tier {prescription.difficulty_tier}: "
                f"{prescription.progression} | {prescription.rationale}"
            )
            if prescription.guidance_level == "high":
                VOICE.speak("Adaptive support is active. Targets are easier and pacing is slower for safer control.")
            elif prescription.progression == "advance":
                VOICE.speak("Adaptive challenge is active. The next task will be slightly harder.")


