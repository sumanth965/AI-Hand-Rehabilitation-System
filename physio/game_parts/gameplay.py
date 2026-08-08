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
        """Level 1: Pop the Bubbles (Flexibility)"""
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

        # Check if all bubbles popped (only when list is non-empty)
        if (self.bubbles and all(b.popped for b in self.bubbles)) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
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
            self._end_level()
    
    def _update_level3(self, hand_data: HandData):
        """Level 3: Pinch & Drop (Fine Motor)"""
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
        """Level 5: Grip & Release (Spasticity Pump)"""
        # Constantly deflate slowly (deflation rate adapts to pacing)
        if self.balloon_scale > 1.0:
            self.balloon_scale -= 0.005 * getattr(self, 'pacing_multiplier', 1.0)
            
        # If no rep completed for 8 seconds, slow down the deflation rate (make it easier)
        if not hasattr(self, 'last_rep_time'):
            self.last_rep_time = time.time()
            
        if hand_data.is_fist and self.pump_state == 0:
            self.pump_state = 1
            self.balloon_scale = max(0.5, self.balloon_scale - 0.2)
            self.sounds.play('catch')
        elif not hand_data.is_fist and hand_data.finger_extension > 120 and self.pump_state == 1:
            self.pump_state = 0
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
                
        if time.time() - self.last_rep_time > 8.0:
            self.last_rep_time = time.time() # Reset trigger timer
            if self.pacing_multiplier > 0.6:
                self._adjust_pacing("slow")
                
        # End after 30 seconds
        if (time.time() - self.session_start > self.session_time_limit) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            self.accuracy_attempts = max(self.accuracy_attempts, 5) # Provide base attempts
            self._end_level()

    def _update_level6(self, hand_data: HandData):
        """Level 6: Memory Sequence (Cognitive Motor)"""
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
            self.accuracy_attempts = max(self.accuracy_attempts, 5)
            self._end_level()


    def _update_level7(self, hand_data: HandData):
        """Level 7: Rotation Orbit (Forearm Pronation/Supination)"""
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
                # Success!
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
            self.accuracy_attempts += 1
            self._end_level()

        self.satellite_angle = current_angle
    def _update_level8(self, hand_data: HandData):
        """Level 8: Smart Object Assembly"""
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
        """Level 9: Precision Path - Connecting Dots"""
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
            self._end_level()

    def _update_level10(self, hand_data: HandData):
        """Level 10: Precision Pathway - Fine Motor & Wrist Control"""
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
                    avg_deviation = self.pathway_total_deviation / max(1, self.pathway_samples)
                    accuracy = max(0.0, min(100.0, 100.0 * (1.0 - (avg_deviation / half_width))))
                    self.accuracy_attempts = 100
                    self.accuracy_hits = int(accuracy)
                    
                    violation_penalty = min(30, self.pathway_boundary_violations * 2)
                    self.score = int(max(0, accuracy - violation_penalty))
                    
                    self.popups.append(ScorePopup(hx, hy - 40, "PATH COMPLETE!", COLOR_SUCCESS))
                    self.sounds.play('level_complete')
                    self._end_level()
                    return
                
        if (time.time() - self.session_start > max(getattr(self, 'session_time_limit', 60), 60)):
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

    def _get_level_goals(self) -> str:
        if self.state == GameState.MAIN_MENU:
            return "Select a level to begin rehabilitation"
        elif self.state == GameState.LEVEL1_FLEXIBILITY:
            return "Pop all bubbles in corners to test flexibility and reach"
        elif self.state == GameState.LEVEL2_STRENGTH:
            return "Move palm to catch falling items. Build strength!"
        elif self.state == GameState.LEVEL3_FINEMOTOR:
            return "Pinch seeds and drop them in the pot. Fine motor control!"
        elif self.state == GameState.LEVEL4_COORDINATION:
            return "Follow the moving target smoothly to test hand stability!"
        elif self.state == GameState.LEVEL5_GRIP_RELEASE:
            return "Make a FIST, then OPEN fully to pump the object!"
        elif self.state == GameState.LEVEL6_FINGER_TAPS:
            return "Memorize the pattern and repeat it!"
        elif self.state == GameState.LEVEL9_PRECISION_PATH:
            return "Connect the numbered dots in sequence using your index fingertip."
        elif self.state == GameState.LEVEL10_PRECISION_PATHWAY:
            return "Guide your index finger from START to END along the pathway."
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
            VOICE.speak("Level 10: Precision Pathway. Carefully guide your index finger along the path from start to finish.")
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


