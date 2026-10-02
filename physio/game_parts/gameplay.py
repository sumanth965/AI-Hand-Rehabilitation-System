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
        """Level 2: The Basket (Strength) - Accuracy Type: hit_rate"""
        # Smooth basket movement clamped safely inside game area
        if hand_data.palm_center:
            self.basket_x = max(80, min(GAME_AREA_WIDTH - 80, hand_data.palm_center[0]))
        elif hand_data.index_tip:
            self.basket_x = max(80, min(GAME_AREA_WIDTH - 80, hand_data.index_tip[0]))

        # Update clinical reach and extension tracking
        if hand_data.wrist and hand_data.index_tip:
            reach = distance(hand_data.index_tip, hand_data.wrist)
            self.reach_distance = max(self.reach_distance, reach)
        self.max_extension = max(self.max_extension, getattr(hand_data, 'finger_extension', 0.0))
        
        speed_mult = 0.5 if self.slow_mo else 1.0
        
        # Update falling items (speed multiplier applied once)
        for item in self.falling_items[:]:
            item.y += item.speed * speed_mult * getattr(self, 'pacing_multiplier', 1.0)
            
            # Check collision with basket
            basket_half_w = int(75 * getattr(self, 'adaptive_target_scale', 1.0))
            if (item.y >= self.basket_y - 25 and 
                item.y <= self.basket_y + 25 and
                abs(item.x - self.basket_x) < basket_half_w):
                
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
        Clinical focus: Fine motor pinch coordination, thumb-index opposition, and deliberate release.
        Includes debounce grace to cushion against MediaPipe self-occlusion flickers outside the pot.
        """
        self._last_hand_data = hand_data

        # Update clinical reach and extension tracking
        if hand_data.wrist and hand_data.index_tip:
            reach = distance(hand_data.index_tip, hand_data.wrist)
            self.reach_distance = max(self.reach_distance, reach)
        self.max_extension = max(self.max_extension, getattr(hand_data, 'finger_extension', 0.0))

        # Check if patient is already grasping a seed (enforce single-object fine motor therapy)
        already_holding = any(s.grabbed for s in self.seeds)

        # Pot radius & forgiving drop threshold based on adaptive target scale
        adaptive_target_scale = float(getattr(self, 'adaptive_target_scale', 1.0))
        pot_radius = int(50 * adaptive_target_scale)
        pot_threshold = pot_radius + 15

        # Update seeds
        for seed in self.seeds[:]:
            if not seed.grabbed:
                # Physics movement: speed multiplier applied once
                seed.y += seed.speed * getattr(self, 'pacing_multiplier', 1.0)
                
                # Check pinch grab
                if not already_holding and hand_data.is_pinching and (hand_data.index_tip or hand_data.thumb_tip):
                    pinch_pos = (
                        ((hand_data.index_tip[0] + hand_data.thumb_tip[0]) // 2,
                         (hand_data.index_tip[1] + hand_data.thumb_tip[1]) // 2)
                        if (hand_data.index_tip and hand_data.thumb_tip)
                        else (hand_data.index_tip or hand_data.thumb_tip)
                    )
                    dist_pinch = distance(pinch_pos, (seed.x, seed.y))
                    dist_idx = distance(hand_data.index_tip, (seed.x, seed.y)) if hand_data.index_tip else 999.0
                    grab_margin = int(35 * adaptive_target_scale)
                    
                    if min(dist_pinch, dist_idx) < (seed.radius + grab_margin):
                        seed.grabbed = True
                        seed.unpinch_frames = 0
                        already_holding = True
                        self.accuracy_attempts += 1
                        self.sounds.play('pop')
                        self.particles.emit(int(seed.x), int(seed.y), (255, 235, 120) if seed.is_golden else (255, 255, 255), 6)
            else:
                # Seed is grabbed: smoothly track pinch cursor
                pinch_pos = None
                if hand_data.index_tip and hand_data.thumb_tip:
                    pinch_pos = (
                        (hand_data.index_tip[0] + hand_data.thumb_tip[0]) // 2,
                        (hand_data.index_tip[1] + hand_data.thumb_tip[1]) // 2
                    )
                elif hand_data.index_tip:
                    pinch_pos = hand_data.index_tip
                elif hand_data.thumb_tip:
                    pinch_pos = hand_data.thumb_tip

                if pinch_pos:
                    # Keep seed securely centered within pinch grasp and clamped within playable game area
                    seed.x = max(24, min(GAME_AREA_WIDTH - 24, pinch_pos[0]))
                    seed.y = max(24, min(WINDOW_HEIGHT - 24, pinch_pos[1]))
                    
                    pot_dist = distance((seed.x, seed.y), (self.pot_x, self.pot_y))

                    if not hand_data.is_pinching:
                        if pot_dist < pot_threshold:
                            # Immediate successful release into planter pot!
                            points = int(25 * self.score_multiplier * (3 if seed.is_golden else 1))
                            self.score += points
                            self.accuracy_hits += 1
                            self.combo += 1
                            self.consecutive_misses = 0  # reset misses on pot success
                            if self.combo > 0 and self.combo % 6 == 0:
                                self._adjust_pacing("fast")
                            self._trigger_feedback()
                            self.sounds.play('catch')
                            color = (255, 215, 0) if seed.is_golden else COLOR_SUCCESS
                            self.particles.emit(self.pot_x, self.pot_y, color, 20 if seed.is_golden else 14)
                            popup_text = f"+{points} GOLDEN BLOOM!" if seed.is_golden else f"+{points}"
                            self.popups.append(ScorePopup(self.pot_x, self.pot_y - 45, popup_text, color=color))
                            self.seeds.remove(seed)
                        else:
                            # Outside pot: debounce unpinch by requiring 3 consecutive open frames
                            # Cushions against single-frame camera occlusions or tremor flickers
                            seed.unpinch_frames = getattr(seed, 'unpinch_frames', 0) + 1
                            if seed.unpinch_frames >= 3:
                                # Confirmed intentional drop outside pot
                                self.combo = 0  # Reset on miss
                                self.consecutive_misses += 1
                                if self.consecutive_misses >= 3:
                                    self.consecutive_misses = 0
                                    self._adjust_pacing("slow")
                                self.sounds.play('pop')
                                self.particles.emit(int(seed.x), int(seed.y), COLOR_DANGER, 10)
                                self.popups.append(ScorePopup(int(seed.x), int(seed.y) - 25, "MISSED POT", color=COLOR_DANGER))
                                self.seeds.remove(seed)
                    else:
                        # Fingers actively pinching: reset unpinch debounce buffer
                        seed.unpinch_frames = 0
                else:
                    # Severe tracking loss while holding seed
                    seed.unpinch_frames = getattr(seed, 'unpinch_frames', 0) + 1
                    if seed.unpinch_frames > 45:  # ~0.75s of prolonged tracking disappearance
                        self.combo = 0
                        self.consecutive_misses += 1
                        self.seeds.remove(seed)
            
            # Remove if off screen without being grabbed
            if seed.y > WINDOW_HEIGHT and not seed.grabbed:
                self.seeds.remove(seed)
                self.accuracy_attempts += 1  # Missed an ungrabbed presented seed
                self.combo = 0  # Missed a seed
                self.consecutive_misses += 1
                if self.consecutive_misses >= 3:
                    self.consecutive_misses = 0
                    self._adjust_pacing("slow")
        
        # Spawn new seeds: maintain continuous flow (immediate spawn if 0 seeds)
        if len(self.seeds) == 0:
            self._spawn_seed()
        elif len(self.seeds) < 2 and random.random() < 0.02:
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
        primary = theme.get("primary_color", (0, 200, 255))
        level_name = theme.get('level1_name', 'Bubble Pop')

        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_tiny = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 12)

        # Header Title
        title_surf = font_head.render(f"LEVEL 1: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, (50, 80))

        # Clinical Guidance Subtitle
        sub_surf = font_hint.render("Extend index finger to reach and touch floating bubbles", True, COLOR_MED_MUTED)
        self.screen.blit(sub_surf, (50, 112))

        # Quick Stats Pill (Top Right, safely below home icon)
        total_bubbles = len(self.bubbles)
        remaining = sum(1 for b in self.bubbles if not b.popped)
        pill_x = GAME_AREA_WIDTH - 250
        pill_y = 80
        pill_w = 200
        pill_h = 36
        pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
        pill_bg = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill_bg.fill((20, 28, 45, 210))
        self.screen.blit(pill_bg, (pill_x, pill_y))
        pygame.draw.rect(self.screen, (0, 180, 220), pill_rect, 1, border_radius=10)
        
        stat_text = font_tiny.render(f"Remaining: {remaining} / {total_bubbles}", True, COLOR_MED_TEXT)
        self.screen.blit(stat_text, stat_text.get_rect(center=pill_rect.center))

        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining_ratio = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 138
            pygame.draw.rect(self.screen, (30, 36, 50), (bar_x, bar_y, bar_w, 10), border_radius=5)
            r = int(255 * (1 - remaining_ratio))
            g = int(210 * remaining_ratio)
            bar_color = (r, g, int(180 * remaining_ratio))
            filled_w = int(bar_w * remaining_ratio)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 10), border_radius=5)
            time_text = font_hint.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_MED_MUTED)
            self.screen.blit(time_text, (bar_x + bar_w + 12, bar_y - 4))

        # Bubbles with rich iridescence and golden effects
        for bubble in self.bubbles:
            if not bubble.popped:
                bx, by, br = int(bubble.x), int(bubble.y), bubble.radius
                if bubble.is_golden:
                    # Glowing golden orb
                    pygame.draw.circle(self.screen, (255, 190, 20), (bx, by), br + 3, 2)
                    pygame.draw.circle(self.screen, (255, 215, 0), (bx, by), br)
                    # Specular highlight
                    pygame.draw.circle(self.screen, (255, 255, 220), (bx - br // 3, by - br // 3), max(3, br // 3))
                    # Sparkle cross
                    pygame.draw.line(self.screen, (255, 255, 255), (bx - br//2, by), (bx + br//2, by), 2)
                    pygame.draw.line(self.screen, (255, 255, 255), (bx, by - br//2), (bx, by + br//2), 2)
                    badge = font_tiny.render("3X", True, (255, 240, 120))
                    self.screen.blit(badge, (bx - badge.get_width()//2, by - br - 14))
                else:
                    # Iridescent bio-bubble
                    pygame.draw.circle(self.screen, bubble.color, (bx, by), br)
                    # Glass reflection crescent
                    surf = pygame.Surface((br * 2, br * 2), pygame.SRCALPHA)
                    pygame.draw.ellipse(surf, (255, 255, 255, 95), (int(br * 0.35), int(br * 0.15), br, int(br * 0.55)))
                    self.screen.blit(surf, (bx - br, by - br))
                    pygame.draw.circle(self.screen, primary, (bx, by), br, 2)
    
    def _draw_level2(self):
        theme = self._get_theme()
        primary = theme.get("primary_color", (0, 200, 255))
        level_name = theme.get('level2_name', 'Fruit Catch')

        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_tiny = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 12)

        # Header Title
        title_surf = font_head.render(f"LEVEL 2: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, (50, 80))

        # Clinical Guidance Subtitle
        sub_surf = font_hint.render("Shift palm horizontally to catch falling fruit in the basket", True, COLOR_MED_MUTED)
        self.screen.blit(sub_surf, (50, 112))

        # Quick Stats Pill (Top Right, safely below home icon)
        pill_x = GAME_AREA_WIDTH - 250
        pill_y = 80
        pill_w = 200
        pill_h = 36
        pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
        pill_bg = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill_bg.fill((20, 28, 45, 210))
        self.screen.blit(pill_bg, (pill_x, pill_y))
        pygame.draw.rect(self.screen, (0, 180, 220), pill_rect, 1, border_radius=10)
        
        stat_text = font_tiny.render(f"Caught: {self.accuracy_hits}  |  Combo: {self.combo}x", True, COLOR_MED_TEXT)
        self.screen.blit(stat_text, stat_text.get_rect(center=pill_rect.center))

        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 138
            pygame.draw.rect(self.screen, (30, 36, 50), (bar_x, bar_y, bar_w, 10), border_radius=5)
            r = int(255 * (1 - remaining))
            g = int(210 * remaining)
            bar_color = (r, g, int(180 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 10), border_radius=5)
            time_text = font_hint.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_MED_MUTED)
            self.screen.blit(time_text, (bar_x + bar_w + 12, bar_y - 4))

        # Woven / High-Tech Basket Receptacle
        basket_half_w = int(75 * getattr(self, 'adaptive_target_scale', 1.0))
        bw = basket_half_w * 2
        bh = 42
        bx = int(self.basket_x - basket_half_w)
        by = self.basket_y
        basket_rect = pygame.Rect(bx, by, bw, bh)

        # Basket body with woven shadow
        pygame.draw.rect(self.screen, (160, 95, 45), basket_rect, border_radius=12)
        # Inner rim highlight
        pygame.draw.rect(self.screen, (195, 130, 75), pygame.Rect(bx + 4, by + 4, bw - 8, 10), border_radius=6)
        # Outer neon border
        pygame.draw.rect(self.screen, primary, basket_rect, 2, border_radius=12)

        # Shield Effect
        if self.shield_active:
            pulse = int(5 * math.sin(time.time() * 10))
            shield_rect = basket_rect.inflate(24 + pulse, 24 + pulse)
            pygame.draw.ellipse(self.screen, (0, 200, 255), shield_rect, 2)
            shield_surf = pygame.Surface((shield_rect.width, shield_rect.height), pygame.SRCALPHA)
            pygame.draw.ellipse(shield_surf, (0, 200, 255, 35), shield_surf.get_rect())
            self.screen.blit(shield_surf, shield_rect.topleft)

        # Freezing background tint
        if self.slow_mo:
            freeze_surf = pygame.Surface((GAME_AREA_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            freeze_surf.fill((100, 255, 255, 18))
            self.screen.blit(freeze_surf, (0, 0))

        # Falling items with rich visual differentiation
        for item in self.falling_items:
            ix, iy, ir = int(item.x), int(item.y), item.radius
            if getattr(item, 'is_bomb', False):
                # Spiked Bomb
                pygame.draw.circle(self.screen, (35, 35, 45), (ix, iy), ir)
                pygame.draw.circle(self.screen, (220, 40, 40), (ix, iy), ir, 2)
                # Fuse & Spark
                pygame.draw.line(self.screen, (180, 140, 80), (ix, iy - ir), (ix + 6, iy - ir - 8), 2)
                spark_col = (255, 220, 50) if int(time.time() * 20) % 2 == 0 else (255, 80, 30)
                pygame.draw.circle(self.screen, spark_col, (ix + 6, iy - ir - 8), 3)
            elif getattr(item, 'is_powerup', False):
                # 2X Golden Power-Up
                pygame.draw.circle(self.screen, (255, 215, 0), (ix, iy), ir)
                pygame.draw.circle(self.screen, (255, 255, 255), (ix, iy), ir, 2)
                p_text = font_tiny.render("2X", True, (60, 40, 0))
                self.screen.blit(p_text, p_text.get_rect(center=(ix, iy)))
            elif getattr(item, 'is_shield', False):
                # Cyan Shield Orb
                pygame.draw.circle(self.screen, (0, 200, 255), (ix, iy), ir)
                pygame.draw.circle(self.screen, (255, 255, 255), (ix, iy), ir, 2)
                s_text = font_tiny.render("SHLD", True, (10, 25, 50))
                self.screen.blit(s_text, s_text.get_rect(center=(ix, iy)))
            elif getattr(item, 'is_freeze', False):
                # Ice Crystal Orb
                pygame.draw.circle(self.screen, (130, 240, 255), (ix, iy), ir)
                pygame.draw.circle(self.screen, (255, 255, 255), (ix, iy), ir, 2)
                f_text = font_tiny.render("ICE", True, (10, 35, 60))
                self.screen.blit(f_text, f_text.get_rect(center=(ix, iy)))
            else:
                # Fresh Apple / Fruit
                pygame.draw.circle(self.screen, (225, 45, 55), (ix, iy), ir)
                pygame.draw.circle(self.screen, (255, 130, 130), (ix - ir // 3, iy - ir // 3), max(2, ir // 3))
                # Stem & leaf
                pygame.draw.line(self.screen, (90, 50, 25), (ix, iy - ir), (ix + 3, iy - ir - 6), 2)
                pygame.draw.ellipse(self.screen, (60, 190, 75), pygame.Rect(ix + 3, iy - ir - 6, 6, 4))
                pygame.draw.circle(self.screen, (160, 25, 35), (ix, iy), ir, 1)
    
    def _draw_level3(self):
        theme = self._get_theme()
        primary = theme.get("primary_color", (0, 200, 255))
        accent = theme.get("accent_color", (255, 200, 100))
        level_name = theme.get('level3_name', 'Fine Motor Pinch')

        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_badge = getattr(self, 'font_badge', None) or pygame.font.SysFont("segoeui", 18, bold=True)
        font_tiny = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 12)
        font_small = getattr(self, 'font_small', None) or pygame.font.SysFont("segoeui", 20)

        # Header Title
        title_surf = font_head.render(f"LEVEL 3: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, (50, 80))

        # Clinical Guidance Subtitle
        sub_surf = font_hint.render("Pinch index & thumb to grasp seed  •  Transfer and release into planter pot", True, COLOR_MED_MUTED)
        self.screen.blit(sub_surf, (50, 112))

        # Quick Stats Pill (Top Right, safely below home icon, width 210, x = GAME_AREA_WIDTH - 250)
        pill_x = GAME_AREA_WIDTH - 250
        pill_y = 80
        pill_w = 200
        pill_h = 36
        pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
        pill_bg = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill_bg.fill((20, 28, 45, 210))
        self.screen.blit(pill_bg, (pill_x, pill_y))
        pygame.draw.rect(self.screen, (0, 180, 220), pill_rect, 1, border_radius=10)
        
        stat_text = font_tiny.render(f"Planted: {self.accuracy_hits}  |  Combo: {self.combo}x", True, COLOR_MED_TEXT)
        self.screen.blit(stat_text, stat_text.get_rect(center=pill_rect.center))

        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 138
            pygame.draw.rect(self.screen, (30, 36, 50), (bar_x, bar_y, bar_w, 10), border_radius=5)
            r = int(255 * (1 - remaining))
            g = int(210 * remaining)
            bar_color = (r, g, int(180 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 10), border_radius=5)
            time_text = font_hint.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_MED_MUTED)
            self.screen.blit(time_text, (bar_x + bar_w + 12, bar_y - 4))

        # Pot Dimensions & Properties
        target_scale = float(getattr(self, 'adaptive_target_scale', 1.0))
        pot_r = int(50 * target_scale)
        pot_cx = self.pot_x
        pot_cy = self.pot_y

        is_holding_seed = any(s.grabbed for s in self.seeds)
        held_seed = next((s for s in self.seeds if s.grabbed), None)

        # Drop Beacon / Target Visual Guidance
        if is_holding_seed and held_seed:
            dist_to_pot = distance((held_seed.x, held_seed.y), (pot_cx, pot_cy))
            over_pot = dist_to_pot < (pot_r + 15)
            
            # Pulsing guidance ring around the pot
            pulse = (math.sin(time.time() * 8) + 1.0) * 0.5
            ring_r = pot_r + int(8 + pulse * 14)
            ring_color = (50, 240, 140) if over_pot else primary
            pygame.draw.circle(self.screen, ring_color, (pot_cx, pot_cy), ring_r, 2)
            
            # Interactive Cue Badge above the pot
            cue_text_str = "RELEASE PINCH NOW!" if over_pot else "DROP SEED HERE v"
            cue_color = (50, 255, 140) if over_pot else (0, 220, 255)
            cue_surf = font_badge.render(cue_text_str, True, cue_color)
            cue_rect = cue_surf.get_rect(center=(pot_cx, pot_cy - pot_r - 28))
            
            # Cue background bubble
            bg_pad = 8
            bg_rect = cue_rect.inflate(bg_pad * 2, 4)
            cue_bg = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            cue_bg.fill((15, 22, 35, 230))
            self.screen.blit(cue_bg, bg_rect.topleft)
            pygame.draw.rect(self.screen, cue_color, bg_rect, 1, border_radius=8)
            self.screen.blit(cue_surf, cue_rect)

        # Planter Pot Body (Stylized Tapered Ceramic Planter)
        pot_top_w = pot_r * 2
        pot_bot_w = int(pot_r * 1.4)
        pot_h = int(pot_r * 1.1)
        pot_top_y = pot_cy - int(pot_r * 0.35)
        pot_bot_y = pot_top_y + pot_h

        # Planter Polygon
        pot_poly = [
            (pot_cx - pot_top_w // 2, pot_top_y),
            (pot_cx + pot_top_w // 2, pot_top_y),
            (pot_cx + pot_bot_w // 2, pot_bot_y),
            (pot_cx - pot_bot_w // 2, pot_bot_y)
        ]
        pygame.draw.polygon(self.screen, (175, 75, 45), pot_poly)
        
        # Subtle shaded side highlight for 3D depth
        pot_shade_left = [
            (pot_cx - pot_top_w // 2, pot_top_y),
            (pot_cx - pot_top_w // 4, pot_top_y),
            (pot_cx - pot_bot_w // 4, pot_bot_y),
            (pot_cx - pot_bot_w // 2, pot_bot_y)
        ]
        shade_surf = pygame.Surface((GAME_AREA_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        pygame.draw.polygon(shade_surf, (255, 255, 255, 25), pot_shade_left)
        self.screen.blit(shade_surf, (0, 0))
        
        # Planter pot rim / collar
        collar_rect = pygame.Rect(pot_cx - pot_top_w // 2 - 4, pot_top_y - 6, pot_top_w + 8, 12)
        pygame.draw.rect(self.screen, (195, 90, 55), collar_rect, border_radius=4)
        pygame.draw.rect(self.screen, (130, 50, 30), collar_rect, 1, border_radius=4)
        
        # Outer border
        pygame.draw.polygon(self.screen, (130, 50, 30), pot_poly, 2)

        # Potting Soil Oval at the mouth of the pot
        soil_rect = pygame.Rect(pot_cx - pot_r, pot_top_y - 12, pot_r * 2, 22)
        pygame.draw.ellipse(self.screen, (40, 26, 18), soil_rect)
        pygame.draw.ellipse(self.screen, (75, 50, 35), soil_rect, 1)

        # Dynamic Biofeedback: Plant Growth Progression
        if self.accuracy_hits >= 1:
            # Stem height grows with planted seeds
            stem_h = min(46, 14 + self.accuracy_hits * 3)
            stem_top_y = pot_top_y - stem_h
            
            # Tender green stem
            pygame.draw.line(self.screen, (60, 200, 85), (pot_cx, pot_top_y), (pot_cx, stem_top_y), 4)
            
            # Left & right leaves
            leaf_w = min(16, 8 + self.accuracy_hits)
            leaf_h = min(10, 5 + self.accuracy_hits // 2)
            left_leaf_rect = pygame.Rect(pot_cx - leaf_w - 4, stem_top_y + stem_h // 3, leaf_w, leaf_h)
            right_leaf_rect = pygame.Rect(pot_cx + 4, stem_top_y + stem_h // 3 - 3, leaf_w, leaf_h)
            pygame.draw.ellipse(self.screen, (75, 225, 105), left_leaf_rect)
            pygame.draw.ellipse(self.screen, (50, 175, 75), left_leaf_rect, 1)
            pygame.draw.ellipse(self.screen, (75, 225, 105), right_leaf_rect)
            pygame.draw.ellipse(self.screen, (50, 175, 75), right_leaf_rect, 1)

            # Blooming flower for high achievers (>= 5 hits)
            if self.accuracy_hits >= 5:
                flower_r = min(9, 5 + (self.accuracy_hits - 5))
                # Petals
                for angle_deg in (0, 72, 144, 216, 288):
                    rad = math.radians(angle_deg)
                    petal_x = int(pot_cx + math.cos(rad) * (flower_r + 2))
                    petal_y = int(stem_top_y + math.sin(rad) * (flower_r + 2))
                    pygame.draw.circle(self.screen, (255, 140, 190), (petal_x, petal_y), max(3, flower_r - 2))
                # Flower center
                pygame.draw.circle(self.screen, (255, 220, 50), (pot_cx, stem_top_y), flower_r - 1)

        # Planter Pot Label
        pot_lbl = font_tiny.render(f"PLANTER ({self.accuracy_hits})", True, (255, 240, 230))
        self.screen.blit(pot_lbl, pot_lbl.get_rect(center=(pot_cx, pot_bot_y - 12)))

        # Hand pinch tether line (if seed is grabbed and both fingertips available)
        last_hand = getattr(self, '_last_hand_data', None)
        if held_seed and last_hand and last_hand.index_tip and last_hand.thumb_tip:
            idx_pt = last_hand.index_tip
            th_pt = last_hand.thumb_tip
            tether_col = (255, 220, 80) if held_seed.is_golden else (0, 240, 255)
            pygame.draw.line(self.screen, tether_col, idx_pt, th_pt, 2)
            pygame.draw.circle(self.screen, tether_col, idx_pt, 4)
            pygame.draw.circle(self.screen, tether_col, th_pt, 4)

        # Render Seeds
        for seed in self.seeds:
            sx, sy, sr = int(seed.x), int(seed.y), seed.radius
            
            # Grabbed halo
            if seed.grabbed:
                pulse_r = sr + 5 + int(2 * math.sin(time.time() * 10))
                halo_col = (255, 215, 0) if seed.is_golden else (0, 220, 255)
                pygame.draw.circle(self.screen, halo_col, (sx, sy), pulse_r, 2)

            if seed.is_golden:
                # Golden Seed Design (3x Points)
                # Outer glow
                pygame.draw.circle(self.screen, (255, 190, 20), (sx, sy), sr + 2)
                # Gold body
                pygame.draw.circle(self.screen, (255, 215, 0), (sx, sy), sr)
                # Inner specular highlight
                pygame.draw.circle(self.screen, (255, 250, 190), (sx - sr // 3, sy - sr // 3), max(2, sr // 3))
                # Sparkle cross
                pygame.draw.line(self.screen, (255, 255, 255), (sx - sr // 2, sy), (sx + sr // 2, sy), 2)
                pygame.draw.line(self.screen, (255, 255, 255), (sx, sy - sr // 2), (sx, sy + sr // 2), 2)
                # Gold outline
                pygame.draw.circle(self.screen, (200, 140, 0), (sx, sy), sr, 2)
                # 3X badge above seed
                badge_surf = font_tiny.render("3X", True, (255, 230, 100))
                self.screen.blit(badge_surf, (sx - badge_surf.get_width() // 2, sy - sr - 15))
            else:
                # Organic Standard Seed Design
                # Seed body (rich amber acorn tone)
                pygame.draw.circle(self.screen, (165, 95, 45), (sx, sy), sr)
                # Subtle acorn cap / dark upper arc
                cap_rect = pygame.Rect(sx - sr, sy - sr, sr * 2, sr)
                pygame.draw.arc(self.screen, (100, 55, 25), cap_rect, 0, math.pi, 3)
                # Specular sheen
                pygame.draw.circle(self.screen, (215, 150, 85), (sx - sr // 3, sy - sr // 3), max(2, sr // 3))
                # Outline
                outline_color = (0, 230, 255) if seed.grabbed else (90, 50, 25)
                pygame.draw.circle(self.screen, outline_color, (sx, sy), sr, 2)
                             
    def _draw_level4(self):
        """Draw Tracing Level"""
        theme = self._get_theme()
        primary = theme.get("primary_color", (0, 200, 255))
        level_name = theme.get('level4_name', 'Magic Trace')

        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_tiny = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 12)

        # Header Title
        title_surf = font_head.render(f"LEVEL 4: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, (50, 80))

        # Clinical Guidance Subtitle
        sub_surf = font_hint.render("Trace along the figure-8 track keeping fingertip centered in the target", True, COLOR_MED_MUTED)
        self.screen.blit(sub_surf, (50, 112))

        # Quick Stats Pill (Top Right, safely below home icon)
        pill_x = GAME_AREA_WIDTH - 250
        pill_y = 80
        pill_w = 200
        pill_h = 36
        pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
        pill_bg = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill_bg.fill((20, 28, 45, 210))
        self.screen.blit(pill_bg, (pill_x, pill_y))
        pygame.draw.rect(self.screen, (0, 180, 220), pill_rect, 1, border_radius=10)
        
        stat_text = font_tiny.render(f"Hits: {self.accuracy_hits}  |  Combo: {self.combo}x", True, COLOR_MED_TEXT)
        self.screen.blit(stat_text, stat_text.get_rect(center=pill_rect.center))

        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 138
            pygame.draw.rect(self.screen, (30, 36, 50), (bar_x, bar_y, bar_w, 10), border_radius=5)
            r = int(255 * (1 - remaining))
            g = int(210 * remaining)
            bar_color = (r, g, int(180 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 10), border_radius=5)
            time_text = font_hint.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_MED_MUTED)
            self.screen.blit(time_text, (bar_x + bar_w + 12, bar_y - 4))

        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2 + 10
        
        # Draw Figure-8 background guide path
        points = []
        for i in range(101):
            t = i * (math.pi * 2 / 100)
            px = cx + 180 * math.sin(t)
            py = cy + 90 * math.sin(2 * t)
            points.append((px, py))
            
        if len(points) > 1:
            pygame.draw.lines(self.screen, (35, 50, 70), False, points, 6)
            pygame.draw.lines(self.screen, (60, 95, 130), False, points, 2)
            
        # Draw recent tracking trail
        if len(self.trace_path) > 1:
            pygame.draw.lines(self.screen, theme.get("secondary_color", (50, 230, 140)), False, self.trace_path, 3)
            
        # Draw target bullseye and tolerance ring
        tx, ty = int(self.trace_target_x), int(self.trace_target_y)
        target_scale = float(getattr(self, 'adaptive_target_scale', 1.0))
        tol_r = int(85 * target_scale)
        perf_r = int(45 * target_scale)
        
        # Outer tolerance aura
        pygame.draw.circle(self.screen, (0, 180, 220, 60), (tx, ty), tol_r, 1)
        pygame.draw.circle(self.screen, (50, 230, 140, 80), (tx, ty), perf_r, 1)

        # Core target
        pulse = int(3 * math.sin(time.time() * 8))
        pygame.draw.circle(self.screen, theme.get("accent_color", (255, 200, 100)), (tx, ty), 22 + pulse)
        pygame.draw.circle(self.screen, (255, 255, 255), (tx, ty), 12)
        pygame.draw.circle(self.screen, primary, (tx, ty), 5)
        
        # Bottom guidance prompt
        inst = font_hint.render("Keep your index fingertip centered inside the moving target", True, COLOR_MED_TEXT)
        self.screen.blit(inst, inst.get_rect(center=(cx, WINDOW_HEIGHT - 45)))

        
    def _draw_level5(self):
        """Draw Grip & Release Level"""
        theme = self._get_theme()
        primary = theme.get("primary_color", (0, 200, 255))
        level_name = theme.get('level5_name', 'Balloon Pump')

        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_tiny = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 12)
        font_large = getattr(self, 'font_large', None) or pygame.font.SysFont("segoeui", 48, bold=True)

        # Header Title
        title_surf = font_head.render(f"LEVEL 5: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, (50, 80))

        # Clinical Guidance Subtitle
        sub_surf = font_hint.render("Close hand into a fist to compress, then open wide (>120 deg) to expand", True, COLOR_MED_MUTED)
        self.screen.blit(sub_surf, (50, 112))

        # Quick Stats Pill (Top Right, safely below home icon)
        pill_x = GAME_AREA_WIDTH - 250
        pill_y = 80
        pill_w = 200
        pill_h = 36
        pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
        pill_bg = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill_bg.fill((20, 28, 45, 210))
        self.screen.blit(pill_bg, (pill_x, pill_y))
        pygame.draw.rect(self.screen, (0, 180, 220), pill_rect, 1, border_radius=10)
        
        stat_text = font_tiny.render(f"Reps: {self.pump_reps}  |  Pacing: {self.pacing_multiplier:.1f}x", True, COLOR_MED_TEXT)
        self.screen.blit(stat_text, stat_text.get_rect(center=pill_rect.center))

        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 138
            pygame.draw.rect(self.screen, (30, 36, 50), (bar_x, bar_y, bar_w, 10), border_radius=5)
            r = int(255 * (1 - remaining))
            g = int(210 * remaining)
            bar_color = (r, g, int(180 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 10), border_radius=5)
            time_text = font_hint.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_MED_MUTED)
            self.screen.blit(time_text, (bar_x + bar_w + 12, bar_y - 4))

        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2 + 15
        
        # Draw pneumatic sphere / balloon
        base_r = 75
        current_r = int(base_r * self.balloon_scale)
        
        # Max expansion guide ring
        pygame.draw.circle(self.screen, (40, 55, 75), (cx, cy), int(base_r * 2.0), 1)

        # Balloon body
        color = (255, 140, 40) if self.pump_state == 0 else (50, 220, 130)
        pygame.draw.circle(self.screen, color, (cx, cy), current_r)
        
        # Inner depth glow
        depth_surf = pygame.Surface((current_r * 2, current_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(depth_surf, (255, 255, 255, 45), (current_r - current_r // 3, current_r - current_r // 3), max(4, current_r // 3))
        self.screen.blit(depth_surf, (cx - current_r, cy - current_r))
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), current_r, 3)
        
        # Large Reps number inside core
        reps_text = font_large.render(str(self.pump_reps), True, (255, 255, 255))
        self.screen.blit(reps_text, reps_text.get_rect(center=(cx, cy)))
        
        # State prompt badge
        inst_txt = "MAKE A TIGHT FIST" if self.pump_state == 0 else "OPEN HAND WIDE (>120 DEG)"
        inst_col = (255, 180, 50) if self.pump_state == 0 else (50, 240, 140)
        inst_surf = font_hint.render(inst_txt, True, inst_col)
        inst_rect = inst_surf.get_rect(center=(cx, WINDOW_HEIGHT - 45))
        
        # Bubble backing for text
        b_rect = inst_rect.inflate(20, 8)
        b_surf = pygame.Surface((b_rect.width, b_rect.height), pygame.SRCALPHA)
        b_surf.fill((15, 22, 35, 210))
        self.screen.blit(b_surf, b_rect.topleft)
        pygame.draw.rect(self.screen, inst_col, b_rect, 1, border_radius=8)
        self.screen.blit(inst_surf, inst_rect)
        
    def _draw_level6(self):
        """Draw Memory Sequence Level"""
        theme = self._get_theme()
        primary = theme.get("primary_color", (0, 200, 255))
        level_name = theme.get('level6_name', 'Memory Sequence')

        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_tiny = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 12)
        font_badge = getattr(self, 'font_badge', None) or pygame.font.SysFont("segoeui", 18, bold=True)

        # Header Title
        title_surf = font_head.render(f"LEVEL 6: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, (50, 80))

        # Clinical Guidance Subtitle
        sub_surf = font_hint.render("Memorize the sequence illumination • Replicate the order by touching pads", True, COLOR_MED_MUTED)
        self.screen.blit(sub_surf, (50, 112))

        # Quick Stats Pill (Top Right, safely below home icon)
        seq_len = max(0, len(self.simon_sequence) - 1) if self.simon_state == "START" else len(self.simon_sequence)
        pill_x = GAME_AREA_WIDTH - 250
        pill_y = 80
        pill_w = 200
        pill_h = 36
        pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
        pill_bg = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill_bg.fill((20, 28, 45, 210))
        self.screen.blit(pill_bg, (pill_x, pill_y))
        pygame.draw.rect(self.screen, (0, 180, 220), pill_rect, 1, border_radius=10)
        
        stat_text = font_tiny.render(f"Sequence: {seq_len}  |  Score: {self.score}", True, COLOR_MED_TEXT)
        self.screen.blit(stat_text, stat_text.get_rect(center=pill_rect.center))

        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 138
            pygame.draw.rect(self.screen, (30, 36, 50), (bar_x, bar_y, bar_w, 10), border_radius=5)
            r = int(255 * (1 - remaining))
            g = int(210 * remaining)
            bar_color = (r, g, int(180 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 10), border_radius=5)
            time_text = font_hint.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_MED_MUTED)
            self.screen.blit(time_text, (bar_x + bar_w + 12, bar_y - 4))

        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2 + 30
        
        # Status Prompt Badge (placed at y = 168, cleanly between timer bar and pads)
        status = "WATCH CAREFULLY!" if self.simon_state == "SHOW" else "REPEAT SEQUENCE"
        if self.simon_state == "START": status = "GET READY"
        status_col = (0, 220, 255) if self.simon_state == "PLAY" else (255, 200, 50)
        st_surf = font_badge.render(status, True, status_col)
        st_rect = st_surf.get_rect(center=(cx, 168))
        
        st_bg_rect = st_rect.inflate(20, 6)
        st_bg = pygame.Surface((st_bg_rect.width, st_bg_rect.height), pygame.SRCALPHA)
        st_bg.fill((15, 22, 35, 220))
        self.screen.blit(st_bg, st_bg_rect.topleft)
        pygame.draw.rect(self.screen, status_col, st_bg_rect, 1, border_radius=8)
        self.screen.blit(st_surf, st_rect)

        # 4 Memory Pads with tactile bevels
        pads = {
            1: (cx - 140, cy - 70),
            2: (cx + 140, cy - 70),
            3: (cx - 140, cy + 90),
            4: (cx + 140, cy + 90)
        }
        pad_colors = {
            1: (255, 75, 75),   # Red
            2: (60, 230, 90),   # Green
            3: (50, 160, 255),  # Blue
            4: (255, 215, 40)   # Yellow
        }
        
        for p_id, (px, py) in pads.items():
            col = pad_colors[p_id]
            is_active = (getattr(self, 'simon_active_pad', None) == p_id)
            is_hovering = (self.simon_state == "PLAY" and getattr(self, '_last_hover', None) == p_id)
            
            draw_col = col if is_active else tuple(int(c * 0.35) for c in col)
            r_size = 65 if is_active else 56
            if is_hovering and not is_active:
                draw_col = tuple(int(c * 0.75) for c in col)
                r_size = 60
                # Hover radial ring
                if hasattr(self, '_hover_start'):
                    prog = min(1.0, (time.time() - self._hover_start) / 0.4)
                    arc_rect = pygame.Rect(px - 72, py - 72, 144, 144)
                    pygame.draw.arc(self.screen, (255, 255, 255), arc_rect, math.pi / 2, math.pi / 2 + 2 * math.pi * prog, 4)
            
            # Active glow
            if is_active:
                pygame.draw.circle(self.screen, col, (px, py), r_size + 8, 2)
            
            pygame.draw.circle(self.screen, draw_col, (px, py), r_size)
            pygame.draw.circle(self.screen, (255, 255, 255), (px, py), r_size, 2)
            
            # Pad Number
            num_surf = font_badge.render(str(p_id), True, (255, 255, 255) if is_active else (180, 180, 180))
            self.screen.blit(num_surf, num_surf.get_rect(center=(px, py)))
    
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
        theme = self._get_theme()
        primary = theme.get('primary_color', (0, 200, 255))
        level_name = theme.get('level7_name', 'Rotation Orbit')
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2 + 25
        orbit_radius = 185

        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_tiny = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 12)

        # Header Title
        title_surf = font_head.render(f"LEVEL 7: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, (50, 80))

        # Clinical Guidance Subtitle
        sub_surf = font_hint.render("Rotate forearm pronation & supination to steer probe to orbital checkpoint", True, COLOR_MED_MUTED)
        self.screen.blit(sub_surf, (50, 112))

        # Quick Stats Pill (Top Right, safely below home icon)
        pill_x = GAME_AREA_WIDTH - 250
        pill_y = 80
        pill_w = 200
        pill_h = 36
        pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
        pill_bg = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill_bg.fill((20, 28, 45, 210))
        self.screen.blit(pill_bg, (pill_x, pill_y))
        pygame.draw.rect(self.screen, (0, 180, 220), pill_rect, 1, border_radius=10)
        
        stat_text = font_tiny.render(f"Orbits: {self.accuracy_hits}  |  Hold: {self.wrist_hold_time:.1f}s", True, COLOR_MED_TEXT)
        self.screen.blit(stat_text, stat_text.get_rect(center=pill_rect.center))

        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 138
            pygame.draw.rect(self.screen, (30, 36, 50), (bar_x, bar_y, bar_w, 10), border_radius=5)
            r = int(255 * (1 - remaining))
            g = int(210 * remaining)
            bar_color = (r, g, int(180 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 10), border_radius=5)
            time_text = font_hint.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_MED_MUTED)
            self.screen.blit(time_text, (bar_x + bar_w + 12, bar_y - 4))
        
        # 1. Central Planet
        pygame.draw.circle(self.screen, (15, 35, 65), (cx, cy), 55)
        # Continental / atmospheric swirl
        pygame.draw.circle(self.screen, (25, 60, 110), (cx - 10, cy - 10), 38)
        pygame.draw.circle(self.screen, primary, (cx, cy), 55, 2)
        
        # 2. Orbital Ring
        pygame.draw.circle(self.screen, (40, 55, 80), (cx, cy), orbit_radius, 2)
        
        # 3. Checkpoint Target Zone (Hold to lock on)
        target_rad = math.radians(self.wrist_target_angle)
        tx = cx + int(math.cos(target_rad) * orbit_radius)
        ty = cy + int(math.sin(target_rad) * orbit_radius)
        
        hold_pct = min(self.wrist_hold_time / 1.5, 1.0)
        target_color = (int(50 + 205 * hold_pct), int(255 * (1.0 - hold_pct * 0.3)), int(220 * (1 - hold_pct)))
        pygame.draw.circle(self.screen, target_color, (tx, ty), 32, 2)
        if hold_pct > 0:
            pygame.draw.circle(self.screen, (50, 240, 140, 120), (tx, ty), int(30 * hold_pct))
        
        cp_lbl = font_tiny.render("TARGET", True, target_color)
        self.screen.blit(cp_lbl, cp_lbl.get_rect(center=(tx, ty - 40)))
        
        # 4. Satellite Probe (Active Patient Forearm Rotation)
        sat_angle = getattr(self, 'satellite_angle', 0.0)
        sat_rad = math.radians(sat_angle)
        sx = cx + int(math.cos(sat_rad) * orbit_radius)
        sy = cy + int(math.sin(sat_rad) * orbit_radius)
        
        # Probe tether beam
        pygame.draw.line(self.screen, (60, 90, 130), (cx, cy), (sx, sy), 1)
        # Spacecraft probe
        pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), 12)
        pygame.draw.circle(self.screen, primary, (sx, sy), 18, 2)

    def _draw_level8(self):
        """Draw Level 8: Smart Assembly"""
        theme = self._get_theme()
        primary = theme.get('primary_color', (0, 200, 255))
        level_name = theme.get('level8_name', 'Smart Assembly')
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2 + 10

        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_tiny = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 12)

        # Header Title
        title_surf = font_head.render(f"LEVEL 8: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, (50, 80))

        # Clinical Guidance Subtitle
        sub_surf = font_hint.render("Pinch & drag components into blueprint • Rotate wrist to align angles", True, COLOR_MED_MUTED)
        self.screen.blit(sub_surf, (50, 112))

        # Quick Stats Pill (Top Right, safely below home icon)
        parts = getattr(self, 'assembly_parts', [])
        locked_count = sum(1 for p in parts if p.is_locked)
        total_parts = len(parts)
        pill_x = GAME_AREA_WIDTH - 250
        pill_y = 80
        pill_w = 200
        pill_h = 36
        pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
        pill_bg = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill_bg.fill((20, 28, 45, 210))
        self.screen.blit(pill_bg, (pill_x, pill_y))
        pygame.draw.rect(self.screen, (0, 180, 220), pill_rect, 1, border_radius=10)
        
        stat_text = font_tiny.render(f"Locked: {locked_count} / {total_parts}", True, COLOR_MED_TEXT)
        self.screen.blit(stat_text, stat_text.get_rect(center=pill_rect.center))

        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 138
            pygame.draw.rect(self.screen, (30, 36, 50), (bar_x, bar_y, bar_w, 10), border_radius=5)
            r = int(255 * (1 - remaining))
            g = int(210 * remaining)
            bar_color = (r, g, int(180 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 10), border_radius=5)
            time_text = font_hint.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_MED_MUTED)
            self.screen.blit(time_text, (bar_x + bar_w + 12, bar_y - 4))
        
        def rotate_polygon(pts, angle_deg, offset_x, offset_y):
            rad = math.radians(angle_deg)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            rotated = []
            for px, py in pts:
                rx = px * cos_a - py * sin_a
                ry = px * sin_a + py * cos_a
                rotated.append((rx + offset_x, ry + offset_y))
            return rotated

        # Draw blueprint docking targets
        for part in parts:
            blueprint_poly = rotate_polygon(part.shape, part.target_angle, part.target_pos[0], part.target_pos[1])
            pygame.draw.polygon(self.screen, (40, 55, 80), blueprint_poly, 2)
            
        # Draw draggable components
        for part in parts:
            if not part.is_locked:
                poly = rotate_polygon(part.shape, part.current_angle, part.current_pos[0], part.current_pos[1])
                color = (255, 255, 255) if part.is_grabbed else part.color
                pygame.draw.polygon(self.screen, color, poly)
                pygame.draw.polygon(self.screen, (220, 220, 220), poly, 2)
            else:
                poly = rotate_polygon(part.shape, part.target_angle, part.target_pos[0], part.target_pos[1])
                pygame.draw.polygon(self.screen, part.color, poly)
                pygame.draw.polygon(self.screen, (50, 255, 120), poly, 3)

        inst = font_hint.render("PINCH to grab, MOVE to blueprint, WRIST to rotate", True, COLOR_MED_TEXT)
        self.screen.blit(inst, inst.get_rect(center=(cx, WINDOW_HEIGHT - 45)))

    def _draw_level9(self):
        """Draw Level 9: Precision Path (Connecting Dots)"""
        theme = self._get_theme()
        primary = theme.get("primary_color", (0, 200, 255))
        level_name = theme.get('level9_name', 'Precision Path')

        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_tiny = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 12)
        font_badge = getattr(self, 'font_badge', None) or pygame.font.SysFont("segoeui", 16, bold=True)

        # Header Title
        title_surf = font_head.render(f"LEVEL 9: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, (50, 80))

        # Clinical Guidance Subtitle
        sub_surf = font_hint.render("Guide index fingertip sequentially to connect numbered dots in order", True, COLOR_MED_MUTED)
        self.screen.blit(sub_surf, (50, 112))

        # Quick Stats Pill (Top Right, safely below home icon)
        dots = getattr(self, 'precision_dots', [])
        total_dots = len(dots)
        cur_dot = getattr(self, 'precision_current_dot', 0)
        pill_x = GAME_AREA_WIDTH - 250
        pill_y = 80
        pill_w = 200
        pill_h = 36
        pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
        pill_bg = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill_bg.fill((20, 28, 45, 210))
        self.screen.blit(pill_bg, (pill_x, pill_y))
        pygame.draw.rect(self.screen, (0, 180, 220), pill_rect, 1, border_radius=10)
        
        stat_text = font_tiny.render(f"Target Dot: {cur_dot + 1} / {total_dots}", True, COLOR_MED_TEXT)
        self.screen.blit(stat_text, stat_text.get_rect(center=pill_rect.center))

        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 138
            pygame.draw.rect(self.screen, (30, 36, 50), (bar_x, bar_y, bar_w, 10), border_radius=5)
            r = int(255 * (1 - remaining))
            g = int(210 * remaining)
            bar_color = (r, g, int(180 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 10), border_radius=5)
            time_text = font_hint.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_MED_MUTED)
            self.screen.blit(time_text, (bar_x + bar_w + 12, bar_y - 4))
        
        # Draw path lines between completed dots
        if len(self.precision_path_points) >= 2:
            pygame.draw.lines(self.screen, (0, 230, 180), False, self.precision_path_points, 3)
            
        # Draw rubber-band guide line from last completed dot to current fingertip
        if self.precision_path_points and self.precision_current_dot < len(self.precision_dots):
            last_hand = getattr(self, '_last_hand_data', None)
            if last_hand and last_hand.index_tip:
                pygame.draw.line(self.screen, (0, 200, 255, 90), self.precision_path_points[-1], last_hand.index_tip, 2)

        # Draw medical precision dots
        for dot in dots:
            dx, dy, dr = int(dot.x), int(dot.y), dot.radius
            color = (60, 75, 95)  # WAITING
            if dot.state == "ACTIVE":
                color = (0, 220, 255)
                pulse = int(math.sin(time.time() * 6) * 5)
                pygame.draw.circle(self.screen, (0, 255, 200), (dx, dy), dr + 6 + pulse, 2)
            elif dot.state == "COMPLETED":
                color = (40, 180, 120)
            
            pygame.draw.circle(self.screen, color, (dx, dy), dr)
            pygame.draw.circle(self.screen, (255, 255, 255), (dx, dy), dr, 2)
            
            # Dot Order Number
            num_surf = font_badge.render(str(dot.order), True, (255, 255, 255))
            self.screen.blit(num_surf, num_surf.get_rect(center=(dx, dy)))

    def _draw_level10(self):
        """Draw Level 10: Precision Pathway"""
        theme = self._get_theme()
        primary = theme.get("primary_color", (0, 200, 255))
        level_name = theme.get('level10_name', 'Precision Pathway')

        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_tiny = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 12)
        font_badge = getattr(self, 'font_badge', None) or pygame.font.SysFont("segoeui", 16, bold=True)

        # Header Title
        title_surf = font_head.render(f"LEVEL 10: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, (50, 80))

        # Clinical Guidance Subtitle
        sub_surf = font_hint.render("Navigate fingertip through corridor from START to END without boundary breaches", True, COLOR_MED_MUTED)
        self.screen.blit(sub_surf, (50, 112))

        # Quick Stats Pill (Top Right, safely below home icon)
        pill_x = GAME_AREA_WIDTH - 250
        pill_y = 80
        pill_w = 200
        pill_h = 36
        pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
        pill_bg = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pill_bg.fill((20, 28, 45, 210))
        self.screen.blit(pill_bg, (pill_x, pill_y))
        pygame.draw.rect(self.screen, (0, 180, 220), pill_rect, 1, border_radius=10)
        
        stat_text = font_tiny.render(f"Violations: {self.pathway_boundary_violations}", True, COLOR_MED_TEXT)
        self.screen.blit(stat_text, stat_text.get_rect(center=pill_rect.center))

        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / self.session_time_limit)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 138
            pygame.draw.rect(self.screen, (30, 36, 50), (bar_x, bar_y, bar_w, 10), border_radius=5)
            r = int(255 * (1 - remaining))
            g = int(210 * remaining)
            bar_color = (r, g, int(180 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 10), border_radius=5)
            time_text = font_hint.render(f"{max(0, self.session_time_limit - int(elapsed))}s", True, COLOR_MED_MUTED)
            self.screen.blit(time_text, (bar_x + bar_w + 12, bar_y - 4))
        
        if not getattr(self, 'pathway_config', None):
            return
            
        points = self.pathway_config.points
        width = self.pathway_config.width
        
        if len(points) >= 2:
            # Draw boundary corridor
            pygame.draw.lines(self.screen, (30, 45, 65), False, points, int(width))
            # Draw corridor edge limits
            pygame.draw.lines(self.screen, (50, 75, 110), False, points, int(width) - 4)
            # Centerline path
            pygame.draw.lines(self.screen, primary, False, points, 2)
            
            # Start and End markers
            start_p = getattr(self, 'pathway_current_proj', points[0])
            end_p = points[-1]
            pygame.draw.circle(self.screen, (50, 240, 120), (int(start_p[0]), int(start_p[1])), 16)
            pygame.draw.circle(self.screen, (255, 255, 255), (int(start_p[0]), int(start_p[1])), 16, 2)
            start_lbl = font_badge.render("START", True, (50, 240, 120))
            self.screen.blit(start_lbl, (int(start_p[0]) - start_lbl.get_width() // 2, int(start_p[1]) - 32))
            
            pygame.draw.circle(self.screen, (240, 60, 80), (int(end_p[0]), int(end_p[1])), 16)
            pygame.draw.circle(self.screen, (255, 255, 255), (int(end_p[0]), int(end_p[1])), 16, 2)
            end_lbl = font_badge.render("END", True, (240, 60, 80))
            self.screen.blit(end_lbl, (int(end_p[0]) - end_lbl.get_width() // 2, int(end_p[1]) - 32))

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

    def _init_level12(self):
        """
        Initialize Level 12: Card Shift Challenge (Thumb-to-Finger Target Touch).
        Clinical Category: In-Hand Manipulation / Finger Coordination.
        Presents one highlighted target finger at a time for intuitive, patient-friendly thumb touching.
        """
        tier = int(getattr(self, 'difficulty_tier', 3))
        target_scale = float(getattr(self, 'adaptive_target_scale', 1.0))
        
        self.accuracy_type = "completion_rate"
        self.successful_hits = 0
        self.total_attempts = 0
        self.accuracy_hits = 0
        self.accuracy_attempts = 0
        
        # Biomechanical contact tolerance (px) scaled to difficulty and target scale
        base_tol = {1: 55.0, 2: 50.0, 3: 45.0, 4: 40.0, 5: 35.0}
        self.card_shift_tolerance = base_tol.get(tier, 45.0) * target_scale
        
        # Dwell contact duration required for intentional touch confirmation
        dwell_map = {1: 0.15, 2: 0.18, 3: 0.20, 4: 0.23, 5: 0.25}
        self.card_dwell_required = dwell_map.get(tier, 0.20)
        self.card_dwell_start = None
        self.card_contact_progress = 0.0
        
        # Response window per prompt (seconds)
        base_timeouts = {1: 6.0, 2: 5.0, 3: 4.0, 4: 3.2, 5: 2.5}
        self.prompt_timeout = base_timeouts.get(tier, 4.0)
        
        # Anatomical position definitions (0=Palm, 2=Index, 3=Middle, 4=Ring, 5=Pinky)
        self.card_position_meta = {
            0: {"name": "PALM", "icon": "✋", "color": (80, 210, 255), "l_idx": 0},
            2: {"name": "INDEX", "icon": "☝️", "color": (0, 240, 255), "l_idx": 8},
            3: {"name": "MIDDLE", "icon": "🖕", "color": (50, 255, 140), "l_idx": 12},
            4: {"name": "RING", "icon": "💍", "color": (255, 215, 60), "l_idx": 16},
            5: {"name": "PINKY", "icon": "🤙", "color": (210, 110, 255), "l_idx": 20},
        }
        
        # Sequential patient-friendly target progressions by tier
        if tier == 1:
            # Palm -> Index -> Palm -> Middle -> Palm (5 simple targets)
            seq_targets = [0, 2, 0, 3, 0]
        elif tier == 2:
            # Palm -> Index -> Middle -> Palm -> Ring -> Palm (6 targets)
            seq_targets = [0, 2, 3, 0, 4, 0]
        elif tier == 3:
            # Index -> Middle -> Ring -> Pinky -> Middle -> Index (6 targets)
            seq_targets = [2, 3, 4, 5, 3, 2]
        elif tier == 4:
            # Mixed finger sequence with limited repetition (8 targets)
            seq_targets = [0, 4, 2, 5, 3, 0, 2, 3]
        else: # Tier 5
            # Dynamic non-consecutive sequence (10 targets)
            seq_targets = [0, 2, 5, 3, 0, 4, 2, 5, 0, 3]
            
        now = time.time()
        self.prompts = []
        prev_name = "THUMB"
        for idx, to_id in enumerate(seq_targets):
            meta = self.card_position_meta[to_id]
            self.prompts.append(
                CardShiftPrompt(
                    from_position=prev_name,
                    to_position=meta["name"],
                    target_digit_id=to_id,
                    target_digit_name=meta["name"],
                    landmark_idx=meta["l_idx"],
                    color=meta["color"],
                    presented_time=now if idx == 0 else 0.0,
                    timeout_duration=self.prompt_timeout,
                    state="WAITING",
                    dwell_time_required=self.card_dwell_required
                )
            )
            prev_name = meta["name"]
            
        self.current_prompt_idx = 0
        self.active_prompt = self.prompts[0] if self.prompts else None
        self.current_prompt = self.active_prompt
        self.active_prompt_start = now
        self.current_target_distance = 999.0
        self.last_contact_digit = None
        self.card_last_success_time = 0.0
        
        # Telemetry counters for clinical and research export
        self.card_shift_successes = 0
        self.card_shift_attempts = 0
        self.shift_latencies = []
        self.average_shift_latency = 0.0
        self.median_shift_latency = 0.0
        self.maximum_shift_latency = 0.0
        self.incorrect_finger_events = 0
        self.target_timeouts = 0
        self.sequence_completion_rate = 0.0
        
        # Live visual guidance coordinates
        self.live_card_positions = {}
        self.live_cursor_pos = None

    def _update_level12(self, hand_data: HandData):
        """
        Level 12: Card Shift Challenge (Thumb-to-Finger Target Touch).
        Accuracy Type: completion_rate
        Validates intentional thumb touches against the single highlighted fingertip target.
        """
        if not self.active_prompt or self.current_prompt_idx >= len(self.prompts):
            self.card_shift_attempts = self.total_attempts
            self.card_shift_successes = self.successful_hits
            self.sequence_completion_rate = round((self.card_shift_successes / max(1, len(self.prompts))) * 100.0, 2)
            self._end_level()
            return
            
        now = time.time()
        
        # Landmark / hand presence check
        if not hand_data or hand_data.index_tip is None:
            return
            
        # Extract anatomical hand landmarks
        if getattr(hand_data, 'landmarks', None) and len(hand_data.landmarks) > 0 and hasattr(hand_data.landmarks[0], 'landmark'):
            lm = hand_data.landmarks[0].landmark
            palm_x = int(((lm[0].x + lm[9].x) / 2.0) * GAME_AREA_WIDTH)
            palm_y = int(((lm[0].y + lm[9].y) / 2.0) * WINDOW_HEIGHT)
            thumb_pos = (int(lm[4].x * GAME_AREA_WIDTH), int(lm[4].y * WINDOW_HEIGHT)) # Active thumb
            positions = {
                0: (palm_x, palm_y),
                2: (int(lm[8].x * GAME_AREA_WIDTH), int(lm[8].y * WINDOW_HEIGHT)),   # Index
                3: (int(lm[12].x * GAME_AREA_WIDTH), int(lm[12].y * WINDOW_HEIGHT)), # Middle
                4: (int(lm[16].x * GAME_AREA_WIDTH), int(lm[16].y * WINDOW_HEIGHT)), # Ring
                5: (int(lm[20].x * GAME_AREA_WIDTH), int(lm[20].y * WINDOW_HEIGHT)), # Pinky
            }
        else:
            thumb_pos = getattr(hand_data, 'thumb_tip', (0, 0)) or (0, 0)
            idx_pos = getattr(hand_data, 'index_tip', (0, 0))
            palm_pos = (thumb_pos[0], thumb_pos[1] + 60)
            positions = {
                0: palm_pos,
                2: idx_pos,
                3: getattr(hand_data, 'middle_tip', (idx_pos[0] + 30, idx_pos[1] - 10)),
                4: getattr(hand_data, 'ring_tip', (idx_pos[0] + 60, idx_pos[1])),
                5: getattr(hand_data, 'pinky_tip', (idx_pos[0] + 90, idx_pos[1] + 15)),
            }
            
        self.live_card_positions = positions
        self.live_cursor_pos = thumb_pos
        
        target_id = self.active_prompt.target_digit_id
        target_coord = positions.get(target_id, (0, 0))
        dist_to_target = distance(thumb_pos, target_coord)
        self.current_target_distance = dist_to_target
        
        # Check for TARGET CONTACT with required dwell hold
        if dist_to_target <= self.card_shift_tolerance:
            if self.card_dwell_start is None:
                self.card_dwell_start = now
                self.card_contact_progress = 0.05
            else:
                self.card_contact_progress = min(1.0, (now - self.card_dwell_start) / self.card_dwell_required)
                
            if now - self.card_dwell_start >= self.card_dwell_required:
                # SUCCESS: Intentional target contact achieved and held!
                latency = max(0.1, now - self.active_prompt_start)
                self.shift_latencies.append(latency)
                self.average_shift_latency = sum(self.shift_latencies) / len(self.shift_latencies)
                import statistics
                self.median_shift_latency = float(statistics.median(self.shift_latencies))
                self.maximum_shift_latency = float(max(self.shift_latencies))
                
                self.card_shift_successes += 1
                self.successful_hits = getattr(self, 'successful_hits', 0) + 1
                self.accuracy_hits = getattr(self, 'accuracy_hits', 0) + 1
                self.total_attempts = getattr(self, 'total_attempts', 0) + 1
                self.accuracy_attempts = getattr(self, 'accuracy_attempts', 0) + 1
                self.card_shift_attempts = self.total_attempts
                
                points = int(20 * getattr(self, 'score_multiplier', 1.0))
                self.score += points
                self.combo += 1
                self.card_last_success_time = now
                
                self.active_prompt.state = "SUCCESS"
                self.active_prompt.shift_latency = latency
                self.sounds.play('catch')
                self.particles.emit(target_coord[0], target_coord[1], self.active_prompt.color, 30)
                self.popups.append(ScorePopup(target_coord[0], target_coord[1] - 30, "🎉 GREAT!", (50, 255, 160)))
                if hasattr(self, '_trigger_feedback'):
                    self._trigger_feedback()
                    
                self._advance_level12_prompt()
                return
        else:
            self.card_dwell_start = None
            self.card_contact_progress = 0.0
            
            # Check for INCORRECT FINGER CONTACT (user touched wrong finger)
            for d_id, d_coord in positions.items():
                if d_id != target_id and distance(thumb_pos, d_coord) <= (self.card_shift_tolerance * 0.75):
                    if self.last_contact_digit != d_id:
                        self.last_contact_digit = d_id
                        self.incorrect_finger_events += 1
                        self.total_attempts = getattr(self, 'total_attempts', 0) + 1
                        self.accuracy_attempts = getattr(self, 'accuracy_attempts', 0) + 1
                        self.card_shift_attempts = self.total_attempts
                        self.combo = 0
                        self.sounds.play('select')
                        self.particles.emit(d_coord[0], d_coord[1], (255, 120, 60), 12)
                        target_name = self.active_prompt.target_digit_name
                        self.popups.append(ScorePopup(d_coord[0], d_coord[1] - 25, f"Touch {target_name}!", (255, 140, 50)))
                        self.correctness_warning = f"Touch {target_name}"
                        self.warning_timer = 45
                    return
            else:
                self.last_contact_digit = None
                
        # Check for PROMPT TIMEOUT
        elapsed_prompt = now - self.active_prompt_start
        if elapsed_prompt > self.prompt_timeout:
            self.target_timeouts += 1
            self.total_attempts = getattr(self, 'total_attempts', 0) + 1
            self.accuracy_attempts = getattr(self, 'accuracy_attempts', 0) + 1
            self.card_shift_attempts = self.total_attempts
            self.combo = 0
            self.active_prompt.state = "MISSED"
            self.sounds.play('pop')
            self.popups.append(ScorePopup(target_coord[0], target_coord[1] - 25, "TIME'S UP", (200, 200, 210)))
            self._advance_level12_prompt()
            return
            
        # Session overall timeout
        if (now - self.session_start > self.session_time_limit) or (now - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            remaining = len(self.prompts) - self.current_prompt_idx
            for _ in range(remaining):
                self.total_attempts = getattr(self, 'total_attempts', 0) + 1
                self.accuracy_attempts = getattr(self, 'accuracy_attempts', 0) + 1
                self.target_timeouts += 1
            self.card_shift_attempts = self.total_attempts
            self.card_shift_successes = self.successful_hits
            self.sequence_completion_rate = round((self.card_shift_successes / max(1, len(self.prompts))) * 100.0, 2)
            self._end_level()

    def _advance_level12_prompt(self):
        """Advances to the next target finger prompt in Level 12."""
        self.current_prompt_idx += 1
        now = time.time()
        if self.current_prompt_idx < len(self.prompts):
            self.active_prompt = self.prompts[self.current_prompt_idx]
            self.current_prompt = self.active_prompt
            self.active_prompt.presented_time = now
            self.active_prompt_start = now
            self.card_dwell_start = None
            self.card_contact_progress = 0.0
            self.last_contact_digit = None
        else:
            self.active_prompt = None
            self.current_prompt = None
            self.card_shift_attempts = self.total_attempts
            self.card_shift_successes = self.successful_hits
            self.sequence_completion_rate = round((self.card_shift_successes / max(1, len(self.prompts))) * 100.0, 2)
            self._end_level()

    def _draw_level12(self):
        """
        Draw Level 12: Simple, intuitive Thumb-to-Finger Target Touch.
        One prominent target at a time, clear guidance arrow, and patient-friendly HUD.
        """
        theme = self._get_theme()
        primary = theme.get("primary_color", (0, 220, 255))
        level_name = theme.get("level12_name", "Target Touch")
        now = time.time()
        
        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_banner = pygame.font.SysFont("segoeui", 18, bold=True)
        font_sub_banner = pygame.font.SysFont("segoeui", 13)
        font_node_title = pygame.font.SysFont("segoeui", 13, bold=True)
        font_icon = pygame.font.SysFont("segoeui", 24, bold=True)
        font_hud = pygame.font.SysFont("segoeui", 13, bold=True)
        
        # 1. Title & Patient Instruction Header (Left-aligned, clean below top HUD)
        title_surf = font_head.render("LEVEL 12: TARGET TOUCH", True, primary)
        self.screen.blit(title_surf, (50, 85))
        
        sub_text = "Thumb-to-Finger Target Touch • Move thumb to touch highlighted target"
        sub_surf = font_hint.render(sub_text, True, COLOR_MED_MUTED if 'COLOR_MED_MUTED' in globals() else (140, 175, 205))
        self.screen.blit(sub_surf, (50, 118))
        
        # 2. Large Visual Target Instruction Banner (Top Center, y=148)
        if self.active_prompt:
            target_name = self.active_prompt.target_digit_name
            target_id = self.active_prompt.target_digit_id
            target_meta = self.card_position_meta.get(target_id, {})
            t_icon = target_meta.get("icon", "🎯")
            t_col = self.active_prompt.color
            
            tb_w = 560
            tb_h = 56
            tb_x = (GAME_AREA_WIDTH - tb_w) // 2
            tb_y = 148
            
            # Banner background
            tb_bg = pygame.Surface((tb_w, tb_h), pygame.SRCALPHA)
            tb_bg.fill((*t_col[:3], 35))
            self.screen.blit(tb_bg, (tb_x, tb_y))
            pygame.draw.rect(self.screen, t_col, (tb_x, tb_y, tb_w, tb_h), 2, border_radius=12)
            
            # Instruction line 1: Target callout
            line1_str = f"🎯 TARGET: {target_name}"
            line1_surf = font_banner.render(line1_str, True, (255, 255, 255))
            self.screen.blit(line1_surf, (tb_x + 18, tb_y + 7))
            
            # Instruction line 2: Simple movement & status
            if self.card_dwell_start:
                dwell_frac = min(1.0, (now - self.card_dwell_start) / self.card_dwell_required)
                line2_str = f"HOLD BRIEFLY ✓  ({int(dwell_frac * 100)}%)"
                line2_col = (100, 255, 180)
            else:
                dist = getattr(self, "current_target_distance", 999.0)
                tol = getattr(self, "card_shift_tolerance", 45.0)
                if dist <= tol * 1.5:
                    line2_str = f"Almost there! Touch {t_icon} {target_name}"
                    line2_col = (255, 220, 100)
                else:
                    line2_str = f"👍 Move your thumb  ──────►  {t_icon} {target_name}"
                    line2_col = (200, 230, 255)
                    
            line2_surf = font_sub_banner.render(line2_str, True, line2_col)
            self.screen.blit(line2_surf, (tb_x + 18, tb_y + 32))
            
        # 3. Success Celebration Banner Overlay
        if now - getattr(self, 'card_last_success_time', 0.0) < 0.7:
            great_surf = font_banner.render("🎉 GREAT! Target Touched!", True, (100, 255, 180))
            great_rect = great_surf.get_rect(center=(GAME_AREA_WIDTH // 2, 220))
            self.screen.blit(great_surf, great_rect)
            
        # 4. Central Finger Targets Arena
        cx = GAME_AREA_WIDTH // 2
        cy = 400
        
        node_layout = {
            0: (cx, cy + 95),       # Palm
            2: (cx - 165, cy - 65), # Index
            3: (cx - 55, cy - 125), # Middle
            4: (cx + 55, cy - 125), # Ring
            5: (cx + 165, cy - 65), # Pinky
        }
        
        target_id = self.active_prompt.target_digit_id if self.active_prompt else None
        target_pos = node_layout.get(target_id, (cx, cy)) if target_id is not None else (cx, cy)
        
        # User thumb coordinate
        thumb_pos = getattr(self, 'live_cursor_pos', None) or (cx, cy + 95)
        
        # 4A. Demonstration Arrow (active during first 1.0s of prompt, non-blocking)
        demo_elapsed = now - self.active_prompt_start
        if self.active_prompt and demo_elapsed < 1.0 and target_pos:
            arrow_pulse = (math.sin(now * 10.0) + 1.0) / 2.0
            line_col = (int(50 + 200 * arrow_pulse), 240, 255)
            pygame.draw.line(self.screen, line_col, thumb_pos, target_pos, 3)
            
            # Animated indicator traveling along arrow
            t_anim = (demo_elapsed % 1.0)
            anim_x = int(thumb_pos[0] + (target_pos[0] - thumb_pos[0]) * t_anim)
            anim_y = int(thumb_pos[1] + (target_pos[1] - thumb_pos[1]) * t_anim)
            pygame.draw.circle(self.screen, (255, 255, 255), (anim_x, anim_y), 6)
            pygame.draw.circle(self.screen, line_col, (anim_x, anim_y), 9, 2)
            
        # 4B. Draw Finger Target Nodes
        for pos_id, pos in node_layout.items():
            meta = self.card_position_meta[pos_id]
            is_target = bool(target_id == pos_id)
            n_col = meta["color"]
            
            if is_target:
                # Target: Large, bright, pulsing highlight
                node_r = 42
                pulse = int(5 * math.sin(now * 7.0))
                pygame.draw.circle(self.screen, n_col, pos, node_r + 8 + pulse, 3)
                
                # Active fill
                node_surf = pygame.Surface((node_r * 2 + 4, node_r * 2 + 4), pygame.SRCALPHA)
                node_surf.fill((*n_col[:3], 200))
                self.screen.blit(node_surf, (pos[0] - node_r - 2, pos[1] - node_r - 2))
                pygame.draw.circle(self.screen, (255, 255, 255), pos, node_r, 3)
                
                # Radial Dwell Hold Ring
                if self.card_dwell_start:
                    dwell_frac = min(1.0, (now - self.card_dwell_start) / self.card_dwell_required)
                    arc_rect = pygame.Rect(pos[0] - node_r - 6, pos[1] - node_r - 6, (node_r + 6) * 2, (node_r + 6) * 2)
                    pygame.draw.arc(self.screen, (100, 255, 180), arc_rect, -math.pi / 2, -math.pi / 2 + dwell_frac * 2 * math.pi, 5)
                
                # Large Icon and Target Label
                icon_surf = font_icon.render(meta["icon"], True, (20, 30, 50))
                self.screen.blit(icon_surf, icon_surf.get_rect(center=(pos[0], pos[1] - 8)))
                
                lbl_surf = font_node_title.render("TARGET", True, (255, 255, 255))
                self.screen.blit(lbl_surf, lbl_surf.get_rect(center=(pos[0], pos[1] + 16)))
            else:
                # Non-target: Dimmed, subtle representation
                node_r = 28
                node_surf = pygame.Surface((node_r * 2 + 2, node_r * 2 + 2), pygame.SRCALPHA)
                node_surf.fill((25, 35, 55, 80))
                self.screen.blit(node_surf, (pos[0] - node_r - 1, pos[1] - node_r - 1))
                pygame.draw.circle(self.screen, (55, 75, 105), pos, node_r, 1)
                
                icon_surf = font_sub_banner.render(meta["icon"], True, (130, 155, 180))
                self.screen.blit(icon_surf, icon_surf.get_rect(center=(pos[0], pos[1] - 6)))
                
                lbl_surf = font_sub_banner.render(meta["name"], True, (110, 135, 160))
                self.screen.blit(lbl_surf, lbl_surf.get_rect(center=(pos[0], pos[1] + 10)))
                
        # 4C. Live Thumb Cursor Indicator
        if thumb_pos:
            pygame.draw.circle(self.screen, (0, 230, 255), thumb_pos, 22, 2)
            pygame.draw.circle(self.screen, (18, 25, 45), thumb_pos, 18)
            thumb_icon = font_sub_banner.render("👍", True, (0, 240, 255))
            self.screen.blit(thumb_icon, thumb_icon.get_rect(center=thumb_pos))
            
        # 5. Patient Progress & Accuracy HUD (Bottom Area)
        if self.prompts:
            tot = len(self.prompts)
            curr = min(tot, self.current_prompt_idx + 1)
            acc_val = int((self.accuracy_hits / max(1, self.accuracy_attempts)) * 100) if self.accuracy_attempts > 0 else 100
            
            pb_w = 420
            pb_h = 10
            pb_x = (GAME_AREA_WIDTH - pb_w) // 2
            pb_y = WINDOW_HEIGHT - 65
            
            # Progress text centered cleanly above bar
            prog_txt = font_hud.render(f"Progress:  {curr} / {tot}     •     Accuracy:  {acc_val}%", True, (210, 235, 255))
            self.screen.blit(prog_txt, prog_txt.get_rect(center=(GAME_AREA_WIDTH // 2, pb_y - 14)))
            
            # Progress bar background & fill
            pygame.draw.rect(self.screen, (25, 32, 50), (pb_x, pb_y, pb_w, pb_h), border_radius=5)
            filled_w = int(pb_w * (curr / max(1, tot)))
            if filled_w > 0:
                pygame.draw.rect(self.screen, primary, (pb_x, pb_y, filled_w, pb_h), border_radius=5)
                
        # 6. Countdown Time Window Bar (Bottom)
        if self.active_prompt:
            remain = max(0.0, self.prompt_timeout - (now - self.active_prompt_start))
            frac = remain / max(0.1, self.prompt_timeout)
            b_w = 340
            b_h = 6
            b_x = (GAME_AREA_WIDTH - b_w) // 2
            b_y = WINDOW_HEIGHT - 32
            pygame.draw.rect(self.screen, (20, 26, 40), (b_x, b_y, b_w, b_h), border_radius=3)
            bar_col = (50, 230, 140) if frac > 0.4 else (255, 190, 40) if frac > 0.2 else (255, 75, 95)
            pygame.draw.rect(self.screen, bar_col, (b_x, b_y, int(b_w * frac), b_h), border_radius=3)
            
            sec_txt = font_sub_banner.render(f"Window: {remain:.1f}s", True, (160, 180, 200))
            self.screen.blit(sec_txt, sec_txt.get_rect(center=(b_x + b_w // 2, b_y - 10)))


    def _init_level13(self):
        """
        Initialize Level 13: Finger Isolation Challenge.
        Trains isolated digital motor control of Index (D2), Middle (D3), Ring (D4), and Pinky (D5),
        while suppressing involuntary co-activation and unintended movement in adjacent fingers.
        """
        tier = int(getattr(self, 'difficulty_tier', 3))
        target_scale = float(getattr(self, 'adaptive_target_scale', 1.0))
        
        # Knuckle angle required to consider the target finger "extended/activated" (degrees)
        base_activation_angles = {1: 125.0, 2: 128.0, 3: 130.0, 4: 133.0, 5: 136.0}
        self.isolation_activation_threshold = max(118.0, min(150.0, base_activation_angles.get(tier, 130.0) / target_scale))
        
        # Knuckle angle threshold above which non-target fingers are considered "OPEN" (not closed)
        # Curled fingers produce 40°-105°. When a finger opens, it exceeds 124°-128°.
        base_unintended_angles = {1: 128.0, 2: 126.0, 3: 124.0, 4: 122.0, 5: 120.0}
        self.isolation_unintended_threshold = base_unintended_angles.get(tier, 124.0) * min(1.05, target_scale)
        
        # Required dwell hold duration to confirm stable isolated activation (seconds)
        base_dwell = {1: 0.35, 2: 0.40, 3: 0.45, 4: 0.48, 5: 0.52}
        self.isolation_dwell_required = base_dwell.get(tier, 0.45)
        self.isolation_dwell_start = None
        self.isolation_contact_progress = 0.0
        
        # Prompt response timeout (seconds) - generous for patients to form isolated gesture
        base_timeouts = {1: 12.0, 2: 10.5, 3: 9.0, 4: 8.0, 5: 7.0}
        self.prompt_timeout = base_timeouts.get(tier, 9.0)
        
        # Digit metadata (2=Index, 3=Middle, 4=Ring, 5=Pinky)
        self.isolation_digit_meta = {
            2: {"name": "INDEX", "color": (0, 240, 255), "l_idx": 8, "pip_idx": 6, "mcp_idx": 5, "glyph": "☝️"},
            3: {"name": "MIDDLE", "color": (50, 255, 140), "l_idx": 12, "pip_idx": 10, "mcp_idx": 9, "glyph": "🖕"},
            4: {"name": "RING", "color": (255, 215, 60), "l_idx": 16, "pip_idx": 14, "mcp_idx": 13, "glyph": "💍"},
            5: {"name": "PINKY", "color": (210, 110, 255), "l_idx": 20, "pip_idx": 18, "mcp_idx": 17, "glyph": "🤙"},
        }
        
        # Target sequence generation
        total_prompts = {1: 8, 2: 10, 3: 12, 4: 14, 5: 16}.get(tier, 12)
        if tier == 1:
            seq_order = [2, 3, 4, 5]
            self.isolation_sequence = [seq_order[i % 4] for i in range(total_prompts)]
        elif tier == 2:
            seq_order = [2, 3, 4, 5, 2, 3, 4, 5, 2, 3]
            self.isolation_sequence = [seq_order[i % len(seq_order)] for i in range(total_prompts)]
        else:
            import random
            self.isolation_sequence = []
            prev_d = None
            for _ in range(total_prompts):
                candidates = [d for d in [2, 3, 4, 5] if d != prev_d]
                choice = random.choice(candidates)
                self.isolation_sequence.append(choice)
                prev_d = choice
                
        self.isolation_prompts = []
        now = time.time()
        for idx, digit_id in enumerate(self.isolation_sequence):
            meta = self.isolation_digit_meta[digit_id]
            self.isolation_prompts.append(
                IsolationPrompt(
                    digit_id=digit_id,
                    digit_name=meta["name"],
                    color=meta["color"],
                    landmark_idx=meta["l_idx"],
                    mcp_landmark_idx=meta["mcp_idx"],
                    presented_time=now if idx == 0 else 0.0,
                    timeout_duration=self.prompt_timeout,
                    state="WAITING",
                    dwell_time_required=self.isolation_dwell_required
                )
            )
            
        self.current_prompt_idx = 0
        self.isolation_active_prompt = self.isolation_prompts[0] if self.isolation_prompts else None
        self.active_prompt = self.isolation_active_prompt
        self.current_prompt = self.isolation_active_prompt
        self.isolation_prompt_start = now
        self.last_unintended_time = 0.0
        self.session_time_limit = float(total_prompts * self.prompt_timeout + 15.0)
        
        # Telemetry metrics
        self.index_successes = 0
        self.middle_successes = 0
        self.ring_successes = 0
        self.pinky_successes = 0
        self.index_attempts = 0
        self.middle_attempts = 0
        self.ring_attempts = 0
        self.pinky_attempts = 0
        self.unintended_movement_events = 0
        self.target_activation_times = []
        self.target_activation_time_avg = 0.0
        self.dwell_success_count = 0
        self.dwell_failure_count = 0
        self.live_knuckle_angles = {2: 90.0, 3: 90.0, 4: 90.0, 5: 90.0}
        self.live_unintended_digits = set()

    def _get_digit_activation_threshold(self, digit_id: int) -> float:
        """Returns biomechanically calibrated target activation angle for specific digit."""
        base = float(getattr(self, 'isolation_activation_threshold', 130.0))
        if digit_id == 4:    # Ring finger (bilaterally tethered by juncturae tendinum)
            return max(112.0, base - 12.0)
        elif digit_id == 3:  # Middle finger
            return max(115.0, base - 4.0)
        elif digit_id == 5:  # Pinky finger
            return max(115.0, base - 2.0)
        return max(118.0, base)  # Index finger

    def _get_unintended_threshold(self, target_digit: int, check_digit: int) -> float:
        """Returns unintended co-activation threshold for non-target digits with biomechanical coupling."""
        thresh = float(getattr(self, 'isolation_unintended_threshold', 124.0))
        # Biomechanical juncturae tendinum allowances:
        # Ring (4) is physically bound to Middle (3) and Pinky (5)
        if target_digit == 4 and check_digit in (3, 5):
            thresh += 10.0
        elif target_digit == 3 and check_digit == 4:
            # When Middle is target, Ring MCP is passively elevated by adjacent extensor tendon
            thresh += 9.0
        elif target_digit == 5 and check_digit == 4:
            # When Pinky is target, Ring MCP is passively elevated
            thresh += 8.0
        return thresh

    def _update_level13(self, hand_data: HandData):
        """
        Level 13: Finger Isolation Challenge.
        Accuracy Type: finger_isolation_accuracy
        Evaluates selective single-digit motor activation and monitors co-activation of adjacent fingers.
        """
        if not self.isolation_active_prompt or self.current_prompt_idx >= len(self.isolation_prompts):
            self._end_level()
            return
            
        now = time.time()
        
        # Landmark / fingertip presence check
        if not hand_data or hand_data.index_tip is None:
            return
            
        has_full_lm = bool(getattr(hand_data, 'landmarks', None) and len(hand_data.landmarks) > 0 and hasattr(hand_data.landmarks[0], 'landmark'))
        lm = hand_data.landmarks[0].landmark if has_full_lm else None

        # Extract knuckle angles for the 4 fingers
        angles = {}
        if getattr(hand_data, 'knuckle_angles', None) and len(hand_data.knuckle_angles) >= 4:
            angles = {
                2: float(hand_data.knuckle_angles[0]),
                3: float(hand_data.knuckle_angles[1]),
                4: float(hand_data.knuckle_angles[2]),
                5: float(hand_data.knuckle_angles[3])
            }
        elif lm is not None:
            wrist = (lm[0].x, lm[0].y)
            for d, meta in self.isolation_digit_meta.items():
                mcp = (lm[meta["mcp_idx"]].x, lm[meta["mcp_idx"]].y)
                tip = (lm[meta["l_idx"]].x, lm[meta["l_idx"]].y)
                v1 = (wrist[0] - mcp[0], wrist[1] - mcp[1])
                v2 = (tip[0] - mcp[0], tip[1] - mcp[1])
                dot = v1[0]*v2[0] + v1[1]*v2[1]
                m1 = math.sqrt(v1[0]**2 + v1[1]**2)
                m2 = math.sqrt(v2[0]**2 + v2[1]**2)
                ang = math.degrees(math.acos(max(-1.0, min(1.0, dot / max(1e-6, m1 * m2))))) if m1 > 0 and m2 > 0 else 90.0
                angles[d] = ang
        else:
            angles = {2: 90.0, 3: 90.0, 4: 90.0, 5: 90.0}
            
        self.live_knuckle_angles = angles
        target_d = self.isolation_active_prompt.digit_id
        target_ang = angles.get(target_d, 0.0)
        
        # Check target finger activation with digit-specific biomechanical calibration
        req_target_ang = self._get_digit_activation_threshold(target_d)
        target_active = target_ang >= req_target_ang

        # Check for unintended co-activation in non-target digits (MUST BE CLOSED)
        unintended_digits = set()
        for d in [2, 3, 4, 5]:
            if d != target_d:
                d_ang = angles.get(d, 0.0)
                thresh = self._get_unintended_threshold(target_d, d)
                
                if d_ang >= thresh:
                    # If full landmarks are available from camera, verify if the finger is truly OPEN (straight)
                    # or if the PIP joint is curled (flexed) into palm despite passive MCP elevation
                    is_truly_open = True
                    if lm is not None:
                        meta = self.isolation_digit_meta[d]
                        mcp_pt = lm[meta["mcp_idx"]]
                        pip_pt = lm[meta["pip_idx"]]
                        tip_pt = lm[meta["l_idx"]]
                        
                        # PIP joint angle (MCP -> PIP -> TIP)
                        v_mcp = (mcp_pt.x - pip_pt.x, mcp_pt.y - pip_pt.y)
                        v_tip = (tip_pt.x - pip_pt.x, tip_pt.y - pip_pt.y)
                        dot_pip = v_mcp[0]*v_tip[0] + v_mcp[1]*v_tip[1]
                        mag_mcp = math.sqrt(v_mcp[0]**2 + v_mcp[1]**2)
                        mag_tip = math.sqrt(v_tip[0]**2 + v_tip[1]**2)
                        if mag_mcp > 1e-5 and mag_tip > 1e-5:
                            cos_pip = max(-1.0, min(1.0, dot_pip / (mag_mcp * mag_tip)))
                            pip_ang = math.degrees(math.acos(cos_pip))
                            # When curled into a fist, PIP is sharply bent (pip_ang < 120°).
                            # When straight / open, pip_ang >= 135°.
                            if pip_ang < 120.0 and d_ang < thresh + 16.0:
                                is_truly_open = False
                                
                    if is_truly_open:
                        unintended_digits.add(d)
                    
        self.live_unintended_digits = unintended_digits
        if unintended_digits and (now - self.last_unintended_time > 0.8):
            self.unintended_movement_events += 1
            self.isolation_active_prompt.unintended_count += 1
            self.last_unintended_time = now
            d_names = "/".join(self.isolation_digit_meta[d]["name"] for d in unintended_digits)
            self.correctness_warning = f"Close {d_names}! Keep Still!"
            self.warning_timer = 40
            self.sounds.play('select')
            self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2, 290, f"Close {d_names}!", (255, 140, 50)))
            
        # TARGET IS DETECTED ONLY WHEN:
        # 1. Target finger is extended AND
        # 2. ALL other fingers are closed (unintended_digits is strictly empty)
        # If any other finger is opened, target_detected is False!
        target_detected = target_active and (len(unintended_digits) == 0)
        
        # Dwell hold evaluation
        if target_detected:
            if self.isolation_dwell_start is None:
                self.isolation_dwell_start = now
                self.isolation_contact_progress = 0.05
            else:
                dwell_elapsed = now - self.isolation_dwell_start
                self.isolation_contact_progress = min(1.0, dwell_elapsed / self.isolation_dwell_required)
                
                if dwell_elapsed >= self.isolation_dwell_required:
                    # SUCCESS: Intentional isolated extension sustained with non-target fingers closed!
                    self.dwell_success_count += 1
                    act_time = max(0.1, now - self.isolation_prompt_start)
                    self.target_activation_times.append(act_time)
                    self.target_activation_time_avg = sum(self.target_activation_times) / len(self.target_activation_times)
                    
                    if target_d == 2:
                        self.index_successes += 1
                        self.index_attempts += 1
                    elif target_d == 3:
                        self.middle_successes += 1
                        self.middle_attempts += 1
                    elif target_d == 4:
                        self.ring_successes += 1
                        self.ring_attempts += 1
                    elif target_d == 5:
                        self.pinky_successes += 1
                        self.pinky_attempts += 1
                        
                    self.successful_hits = getattr(self, 'successful_hits', 0) + 1
                    self.accuracy_hits = getattr(self, 'accuracy_hits', 0) + 1
                    self.total_attempts = getattr(self, 'total_attempts', 0) + 1
                    self.accuracy_attempts = getattr(self, 'accuracy_attempts', 0) + 1
                    
                    points = int(20 * getattr(self, 'score_multiplier', 1.0))
                    self.score += points
                    self.combo += 1
                    
                    self.isolation_active_prompt.state = "SUCCESS"
                    self.sounds.play('catch')
                    self.particles.emit(GAME_AREA_WIDTH // 2, 380, self.isolation_active_prompt.color, 30)
                    self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2, 340, f"PERFECT! +{points}", self.isolation_active_prompt.color))
                    
                    self._advance_level13_prompt()
                    return
        else:
            # If target is NOT detected (either target not extended OR other fingers are open):
            if self.isolation_dwell_start is not None:
                if (now - self.isolation_dwell_start) > 0.15:
                    self.dwell_failure_count += 1
                self.isolation_dwell_start = None
            self.isolation_contact_progress = 0.0
                
        # Check prompt timeout
        elapsed_prompt = now - self.isolation_prompt_start
        if elapsed_prompt > self.prompt_timeout:
            self.total_attempts = getattr(self, 'total_attempts', 0) + 1
            self.accuracy_attempts = getattr(self, 'accuracy_attempts', 0) + 1
            if target_d == 2: self.index_attempts += 1
            elif target_d == 3: self.middle_attempts += 1
            elif target_d == 4: self.ring_attempts += 1
            elif target_d == 5: self.pinky_attempts += 1
            
            self.combo = 0
            self.isolation_active_prompt.state = "MISSED"
            self.sounds.play('pop')
            self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2, 340, "TIME OUT", (200, 200, 210)))
            self._advance_level13_prompt()
            return
            
        # Session overall timeout
        if (now - self.session_start > self.session_time_limit) or (now - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            remaining_prompts = self.isolation_prompts[self.current_prompt_idx:]
            for p in remaining_prompts:
                self.total_attempts = getattr(self, 'total_attempts', 0) + 1
                self.accuracy_attempts = getattr(self, 'accuracy_attempts', 0) + 1
                if p.digit_id == 2: self.index_attempts += 1
                elif p.digit_id == 3: self.middle_attempts += 1
                elif p.digit_id == 4: self.ring_attempts += 1
                elif p.digit_id == 5: self.pinky_attempts += 1
            self._end_level()

    def _advance_level13_prompt(self):
        """Advances to the next finger isolation prompt in Level 13."""
        self.current_prompt_idx += 1
        now = time.time()
        if self.current_prompt_idx < len(self.isolation_prompts):
            self.isolation_active_prompt = self.isolation_prompts[self.current_prompt_idx]
            self.active_prompt = self.isolation_active_prompt
            self.current_prompt = self.isolation_active_prompt
            self.isolation_active_prompt.presented_time = now
            self.isolation_prompt_start = now
            self.isolation_dwell_start = None
            self.isolation_contact_progress = 0.0
        else:
            self.isolation_active_prompt = None
            self.active_prompt = None
            self.current_prompt = None
            self._end_level()

    def _draw_level13(self):
        """
        Draw Level 13: Finger Isolation Challenge.
        Clear, patient-friendly visual hand interface separating target from non-target fingers.
        Includes dwell hold progress, unintended movement warnings, and clinical telemetry.
        """
        theme = self._get_theme()
        primary = theme.get("primary_color", (0, 220, 255))
        level_name = theme.get("level13_name", "Finger Isolation Challenge")
        now = time.time()
        
        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_stat_b = getattr(self, 'font_vault', None) or pygame.font.SysFont("segoeui", 12, bold=True)
        font_stat_s = getattr(self, 'font_phase', None) or pygame.font.SysFont("segoeui", 11)
        font_target = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 16, bold=True)
        font_sub = getattr(self, 'font_phase', None) or pygame.font.SysFont("segoeui", 12, bold=True)
        
        # 1. Level Title & Subtitle
        title_surf = font_head.render(f"LEVEL 13: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, (50, 85))
        
        sub_text = "Finger Selective Motor Control • Extend Only Prompted Finger"
        sub_surf = font_hint.render(sub_text, True, COLOR_MED_MUTED if 'COLOR_MED_MUTED' in globals() else (140, 175, 205))
        self.screen.blit(sub_surf, (50, 118))
        
        # 2. Therapist Telemetry Card (Top Right)
        card_w = 260
        card_h = 52
        card_x = GAME_AREA_WIDTH - card_w - 15
        card_y = 82
        card_bg = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        card_bg.fill((18, 25, 42, 220))
        self.screen.blit(card_bg, (card_x, card_y))
        pygame.draw.rect(self.screen, primary, (card_x, card_y, card_w, card_h), 1, border_radius=8)
        
        if self.accuracy_attempts > 0:
            acc_val = (self.accuracy_hits / self.accuracy_attempts) * 100.0
            acc_str = f"Acc: {int(acc_val)}%"
        else:
            acc_str = "Acc: --%"
        stat_l1 = font_stat_b.render(f"{acc_str}   Hits: {self.accuracy_hits}/{self.accuracy_attempts}", True, (220, 235, 250))
        self.screen.blit(stat_l1, (card_x + 12, card_y + 8))
        stat_l2 = font_stat_s.render(f"Unintended: {self.unintended_movement_events}   Avg: {self.target_activation_time_avg:.2f}s", True, (150, 185, 215))
        self.screen.blit(stat_l2, (card_x + 12, card_y + 28))
        
        # 3. Patient Instruction Banner (Center Top)
        if self.isolation_active_prompt:
            t_col = self.isolation_active_prompt.color
            target_name = self.isolation_active_prompt.digit_name
            glyph = self.isolation_digit_meta[self.isolation_active_prompt.digit_id]["glyph"]
            
            tb_w = 520
            tb_h = 42
            tb_x = (GAME_AREA_WIDTH - tb_w) // 2
            tb_y = 146
            
            tb_bg = pygame.Surface((tb_w, tb_h), pygame.SRCALPHA)
            tb_bg.fill((*t_col[:3], 35))
            self.screen.blit(tb_bg, (tb_x, tb_y))
            pygame.draw.rect(self.screen, t_col, (tb_x, tb_y, tb_w, tb_h), 2, border_radius=10)
            
            if self.isolation_dwell_start:
                dwell_frac = min(1.0, (now - self.isolation_dwell_start) / self.isolation_dwell_required)
                status_txt = f"HOLD STEADY... {int(dwell_frac * 100)}%"
                status_col = (100, 255, 180)
            elif self.live_unintended_digits:
                d_names = "/".join(self.isolation_digit_meta[d]["name"] for d in self.live_unintended_digits)
                status_txt = f"⚠️ CLOSE {d_names}! ONLY {target_name} EXTENDED"
                status_col = (255, 140, 50)
            else:
                status_txt = f"EXTEND ONLY {target_name} • KEEP OTHERS CLOSED"
                status_col = (220, 240, 255)
                
            callout_str = f"TARGET: {glyph} {target_name}   •   {status_txt}"
            callout_surf = font_target.render(callout_str, True, status_col)
            self.screen.blit(callout_surf, callout_surf.get_rect(center=(tb_x + tb_w // 2, tb_y + tb_h // 2)))

        # 4. Interactive 4-Finger Isolation Visualization Arena
        cx = GAME_AREA_WIDTH // 2
        cy = 400
        
        col_w = 110
        col_gap = 25
        total_arena_w = col_w * 4 + col_gap * 3
        start_arena_x = cx - total_arena_w // 2
        
        digit_order = [2, 3, 4, 5]  # Index, Middle, Ring, Pinky
        for i, d_id in enumerate(digit_order):
            meta = self.isolation_digit_meta[d_id]
            is_target = bool(self.isolation_active_prompt and self.isolation_active_prompt.digit_id == d_id)
            is_unintended = d_id in getattr(self, 'live_unintended_digits', set())
            
            d_x = start_arena_x + i * (col_w + col_gap)
            d_y = cy - 140
            d_h = 240
            
            # Base panel surface
            f_surf = pygame.Surface((col_w, d_h), pygame.SRCALPHA)
            if is_target:
                fill_col = (*meta["color"][:3], 55)
                border_col = meta["color"]
                border_w = 3
            elif is_unintended:
                fill_col = (255, 80, 40, 55)
                border_col = (255, 110, 50)
                border_w = 2
            else:
                fill_col = (20, 28, 44, 180)
                border_col = (45, 60, 85)
                border_w = 1
                
            f_surf.fill(fill_col)
            self.screen.blit(f_surf, (d_x, d_y))
            pygame.draw.rect(self.screen, border_col, (d_x, d_y, col_w, d_h), border_w, border_radius=12)
            
            # Target pulsing glow
            if is_target:
                pulse = int(5 * math.sin(now * 8.0))
                pygame.draw.rect(self.screen, meta["color"], (d_x - 3 - pulse, d_y - 3 - pulse, col_w + 6 + pulse*2, d_h + 6 + pulse*2), 2, border_radius=15)
                
                # Dynamic Dwell Radial / Linear Progress
                if self.isolation_dwell_start:
                    dwell_frac = min(1.0, (now - self.isolation_dwell_start) / self.isolation_dwell_required)
                    bar_pad = 8
                    fill_h = int((d_h - bar_pad * 2) * dwell_frac)
                    d_fill_rect = pygame.Rect(d_x + bar_pad, d_y + d_h - bar_pad - fill_h, col_w - bar_pad * 2, fill_h)
                    pygame.draw.rect(self.screen, (100, 255, 180), d_fill_rect, border_radius=8)
            
            # Finger Title & Glyph
            glyph_surf = font_head.render(meta["glyph"], True, meta["color"] if is_target else (170, 190, 210))
            self.screen.blit(glyph_surf, glyph_surf.get_rect(center=(d_x + col_w // 2, d_y + 35)))
            
            name_surf = font_sub.render(meta["name"], True, (255, 255, 255) if is_target else (150, 175, 200))
            self.screen.blit(name_surf, name_surf.get_rect(center=(d_x + col_w // 2, d_y + 75)))
            
            # Angle Meter / Extension Indicator
            cur_ang = self.live_knuckle_angles.get(d_id, 90.0)
            ang_surf = font_stat_s.render(f"{int(cur_ang)}°", True, (200, 225, 250) if is_target else (120, 150, 180))
            self.screen.blit(ang_surf, ang_surf.get_rect(center=(d_x + col_w // 2, d_y + 115)))
            
            # Status Badge at bottom of column
            if is_target:
                target_ang = self.live_knuckle_angles.get(d_id, 0.0)
                req_ang = self._get_digit_activation_threshold(d_id)
                if target_ang >= req_ang:
                    if self.live_unintended_digits:
                        status_badge = font_stat_b.render("WAIT OTHERS", True, (255, 200, 60))
                    else:
                        status_badge = font_stat_b.render("✓ EXTENDED", True, (100, 255, 180))
                else:
                    status_badge = font_stat_b.render("ACTIVE TARGET", True, meta["color"])
            elif is_unintended:
                status_badge = font_stat_b.render("⚠️ OPEN! CLOSE", True, (255, 100, 50))
            else:
                status_badge = font_stat_s.render("✓ CLOSED", True, (80, 220, 140))
            self.screen.blit(status_badge, status_badge.get_rect(center=(d_x + col_w // 2, d_y + d_h - 22)))
            
        # 5. Patient Progress Indicator & Response Bar
        if self.isolation_prompts:
            tot = len(self.isolation_prompts)
            done = self.current_prompt_idx
            prog_txt = font_hint.render(f"🎯 PROGRESS: {done} / {tot} COMPLETED", True, (200, 230, 255))
            self.screen.blit(prog_txt, prog_txt.get_rect(center=(cx, WINDOW_HEIGHT - 65)))
            
            # Progress bar
            pb_w = 420
            pb_h = 8
            pb_x = (GAME_AREA_WIDTH - pb_w) // 2
            pb_y = WINDOW_HEIGHT - 48
            pygame.draw.rect(self.screen, (25, 32, 50), (pb_x, pb_y, pb_w, pb_h), border_radius=4)
            filled_pb = int(pb_w * (done / max(1, tot)))
            if filled_pb > 0:
                pygame.draw.rect(self.screen, primary, (pb_x, pb_y, filled_pb, pb_h), border_radius=4)
                
        # Prompt Countdown Bar
        if self.isolation_active_prompt:
            remain = max(0.0, self.prompt_timeout - (now - self.isolation_prompt_start))
            frac = remain / max(0.1, self.prompt_timeout)
            c_w = 340
            c_h = 6
            c_x = (GAME_AREA_WIDTH - c_w) // 2
            c_y = WINDOW_HEIGHT - 22
            pygame.draw.rect(self.screen, (20, 26, 40), (c_x, c_y, c_w, c_h), border_radius=3)
            bar_col = (50, 230, 140) if frac > 0.4 else (255, 190, 40) if frac > 0.2 else (255, 75, 95)
            pygame.draw.rect(self.screen, bar_col, (c_x, c_y, int(c_w * frac), c_h), border_radius=3)

    def _init_level14(self):
        """
        Initialize Level 14: Wrist Flexion-Extension Control.
        Evaluates controlled sagittal wrist positioning, target-zone acquisition,
        stability dwell hold, target error, overshoot, and movement time using
        a webcam-derived wrist movement proxy.
        """
        tier = int(getattr(self, 'difficulty_tier', 3))
        target_scale = float(getattr(self, 'adaptive_target_scale', 1.0))

        # Target angular zone tolerance (half-width, degrees)
        # Wider at lower tiers for gentle guidance; narrower at higher tiers for precision.
        base_tolerances = {1: 12.0, 2: 10.0, 3: 8.0, 4: 6.5, 5: 5.0}
        self.wrist_target_tolerance = max(4.0, min(16.0, base_tolerances.get(tier, 8.0) * target_scale))

        # Required dwell hold duration to confirm stable target acquisition (seconds)
        base_dwell = {1: 0.60, 2: 0.75, 3: 0.85, 4: 1.00, 5: 1.20}
        self.wrist_dwell_required = base_dwell.get(tier, 0.85)

        # Prompt response timeout (seconds)
        base_timeouts = {1: 12.0, 2: 10.5, 3: 9.0, 4: 8.0, 5: 7.0}
        self.prompt_timeout = base_timeouts.get(tier, 9.0)

        # Target sequence generation (alternating EXTENSION and FLEXION)
        total_targets = {1: 8, 2: 10, 3: 12, 4: 14, 5: 16}.get(tier, 12)
        self.wrist_targets = []
        now = time.time()
        for i in range(total_targets):
            ttype = "EXTENSION" if (i % 2 == 0) else "FLEXION"
            tangle = 24.0 if ttype == "EXTENSION" else -24.0
            self.wrist_targets.append(
                WristControlTarget(
                    target_id=i,
                    target_type=ttype,
                    target_angle=tangle,
                    tolerance=self.wrist_target_tolerance,
                    presented_time=now if i == 0 else 0.0,
                    timeout_duration=self.prompt_timeout,
                    dwell_time_required=self.wrist_dwell_required,
                    state="WAITING"
                )
            )

        self.current_target_idx = 0
        self.wrist_active_target = self.wrist_targets[0] if self.wrist_targets else None
        self.active_prompt = self.wrist_active_target
        self.current_prompt = self.wrist_active_target
        self.wrist_target_start = now
        self.wrist_dwell_start = None
        self.wrist_contact_progress = 0.0
        self.wrist_entry_time = None
        self.wrist_dwell_samples = []
        self.session_time_limit = float(total_targets * self.prompt_timeout + 15.0)

        # Research & Performance Metrics
        self.extension_successes = 0
        self.extension_attempts = 0
        self.flexion_successes = 0
        self.flexion_attempts = 0
        self.trial_movement_times = []
        self.trial_target_errors = []
        self.trial_overshoots = []
        self.trial_hold_stabilities = []
        self.trial_direction_correct = []
        self.average_movement_time = 0.0
        self.average_target_error = 0.0
        self.average_overshoot = 0.0
        self.average_hold_stability = 0.0
        self.direction_accuracy = 100.0
        self.dwell_success_count = 0
        self.dwell_failure_count = 0
        self.live_wrist_pitch = 0.0
        self.live_target_error = 0.0
        self.live_in_zone = False
        self.wrist_completed_targets = 0
        self.wrist_pitch_baseline = 0.0
        self.wrist_y_baseline = 0.5
        self.wrist_baseline_calibrated = False
        self._baseline_samples = []
        self._baseline_y_samples = []

    def _update_level14(self, hand_data: HandData):
        """
        Level 14: Wrist Flexion-Extension Control.
        Accuracy Type: wrist_target_accuracy
        Evaluates controlled positioning into target angular zones using a
        software-derived wrist flexion/extension performance proxy.
        """
        if not self.wrist_active_target or self.current_target_idx >= len(self.wrist_targets):
            self._end_level()
            return

        now = time.time()
        if not hand_data or hand_data.index_tip is None:
            return

        # Extract current wrist flexion/extension pitch proxy (degrees from neutral)
        if hasattr(hand_data, 'wrist_flexion_extension_angle'):
            raw_pitch = float(hand_data.wrist_flexion_extension_angle)
        elif getattr(hand_data, 'landmarks', None) and len(hand_data.landmarks) > 0 and hasattr(hand_data.landmarks[0], 'landmark'):
            lm = hand_data.landmarks[0].landmark
            wrist_pt = lm[0]
            mcp_pt = lm[9]
            tip_pt = lm[12] if len(lm) > 12 else mcp_pt
            idx_pt = lm[5] if len(lm) > 5 else mcp_pt
            pky_pt = lm[17] if len(lm) > 17 else mcp_pt
            
            dz_mcp = mcp_pt.z - wrist_pt.z
            dz_tip = tip_pt.z - mcp_pt.z
            palm_h = math.sqrt((mcp_pt.x - wrist_pt.x)**2 + (mcp_pt.y - wrist_pt.y)**2 + 1e-6)
            cross_z = (mcp_pt.x - wrist_pt.x) * (pky_pt.y - idx_pt.y) - (mcp_pt.y - wrist_pt.y) * (pky_pt.x - idx_pt.x)
            palm_dir = 1.0 if cross_z >= 0 else -1.0
            dz_eff = (0.7 * dz_mcp + 0.3 * dz_tip) * palm_dir
            raw_pitch = float(np.clip(math.degrees(math.atan2(dz_eff, palm_h)) * 2.2, -60.0, 60.0))
        else:
            raw_pitch = 0.0

        # Hand vertical position proxy (in normalized coordinates where 0 is top, 1 is bottom)
        if getattr(hand_data, 'landmarks', None) and len(hand_data.landmarks) > 0 and hasattr(hand_data.landmarks[0], 'landmark'):
            lm = hand_data.landmarks[0].landmark
            hand_norm_y = (lm[0].y + lm[9].y) / 2.0
        elif hand_data.wrist:
            hand_norm_y = hand_data.wrist[1] / float(WINDOW_HEIGHT)
        else:
            hand_norm_y = 0.5

        # Auto-calibrate neutral baseline from the first few resting frames in live webcam sessions
        if not getattr(self, 'wrist_baseline_calibrated', False) and getattr(hand_data, 'landmarks', None):
            if not hasattr(self, '_baseline_samples'):
                self._baseline_samples = []
            if not hasattr(self, '_baseline_y_samples'):
                self._baseline_y_samples = []
            self._baseline_samples.append(raw_pitch)
            self._baseline_y_samples.append(hand_norm_y)
            if len(self._baseline_samples) >= 6:
                self.wrist_pitch_baseline = sum(self._baseline_samples) / len(self._baseline_samples)
                self.wrist_y_baseline = sum(self._baseline_y_samples) / len(self._baseline_y_samples)
                self.wrist_baseline_calibrated = True
            else:
                self.wrist_pitch_baseline = self._baseline_samples[0]
                self.wrist_y_baseline = self._baseline_y_samples[0]

        delta_angle = raw_pitch - getattr(self, 'wrist_pitch_baseline', 0.0)
        
        # Vertical elevation component: lifting hand up (hand_norm_y decreases) adds positive angle; lowering hand adds negative angle
        delta_y_deg = 0.0
        if getattr(self, 'wrist_baseline_calibrated', False):
            delta_y = getattr(self, 'wrist_y_baseline', hand_norm_y) - hand_norm_y
            delta_y_deg = float(delta_y * 140.0)  # ~100px lift translates to ~21 degrees

        # Composite pitch: responds both to wrist tilt in depth/2D and vertical hand elevation
        current_pitch = float(np.clip(delta_angle + delta_y_deg, -60.0, 60.0))

        self.live_wrist_pitch = current_pitch
        target = self.wrist_active_target
        t_angle = target.target_angle
        tol = target.tolerance

        # Target zone boundary evaluation
        in_zone = (t_angle - tol <= current_pitch <= t_angle + tol)
        self.live_in_zone = in_zone

        # Target error: absolute deviation from target center (degrees)
        current_error = abs(current_pitch - t_angle)
        self.live_target_error = current_error

        # Direction accuracy: moved toward target side (> +2° for Extension, < -2° for Flexion)
        is_correct_dir = (current_pitch > 2.0) if t_angle > 0 else (current_pitch < -2.0)

        # Overshoot error: angular extension beyond far edge of target zone
        if t_angle > 0:
            overshoot = max(0.0, current_pitch - (t_angle + tol))
        else:
            overshoot = max(0.0, (t_angle - tol) - current_pitch)

        # Target Zone Entry & Dwell Hold
        if in_zone:
            if self.wrist_entry_time is None:
                self.wrist_entry_time = now

            if self.wrist_dwell_start is None:
                self.wrist_dwell_start = now
                self.wrist_dwell_samples = [current_pitch]
                self.wrist_contact_progress = 0.05
                target.state = "DWELLING"
            else:
                self.wrist_dwell_samples.append(current_pitch)
                dwell_elapsed = now - self.wrist_dwell_start
                self.wrist_contact_progress = min(1.0, dwell_elapsed / self.wrist_dwell_required)

                if dwell_elapsed >= self.wrist_dwell_required:
                    # SUCCESS: Target reached and sustained stably throughout dwell duration!
                    self.dwell_success_count += 1
                    m_time = max(0.1, self.wrist_entry_time - self.wrist_target_start)

                    # Hold stability calculation: 100 * (1.0 - std_deviation / tolerance)
                    if len(self.wrist_dwell_samples) > 1:
                        mean_ang = sum(self.wrist_dwell_samples) / len(self.wrist_dwell_samples)
                        var_ang = sum((x - mean_ang)**2 for x in self.wrist_dwell_samples) / len(self.wrist_dwell_samples)
                        std_ang = math.sqrt(var_ang)
                        stability = max(0.0, min(1.0, 1.0 - (std_ang / max(1.0, tol)))) * 100.0
                    else:
                        stability = 100.0

                    self.trial_movement_times.append(m_time)
                    self.trial_target_errors.append(current_error)
                    self.trial_overshoots.append(overshoot)
                    self.trial_hold_stabilities.append(stability)
                    self.trial_direction_correct.append(1 if is_correct_dir else 0)

                    self.average_movement_time = sum(self.trial_movement_times) / len(self.trial_movement_times)
                    self.average_target_error = sum(self.trial_target_errors) / len(self.trial_target_errors)
                    self.average_overshoot = sum(self.trial_overshoots) / len(self.trial_overshoots)
                    self.average_hold_stability = sum(self.trial_hold_stabilities) / len(self.trial_hold_stabilities)
                    self.direction_accuracy = (sum(self.trial_direction_correct) / len(self.trial_direction_correct)) * 100.0

                    self.successful_hits = getattr(self, 'successful_hits', 0) + 1
                    self.accuracy_hits = getattr(self, 'accuracy_hits', 0) + 1
                    self.total_attempts = getattr(self, 'total_attempts', 0) + 1
                    self.accuracy_attempts = getattr(self, 'accuracy_attempts', 0) + 1
                    self.wrist_completed_targets += 1

                    if t_angle > 0:
                        self.extension_successes += 1
                        self.extension_attempts += 1
                    else:
                        self.flexion_successes += 1
                        self.flexion_attempts += 1

                    points = int(20 * getattr(self, 'score_multiplier', 1.0))
                    self.score += points
                    self.combo += 1

                    target.state = "SUCCESS"
                    target.target_error = current_error
                    target.overshoot = overshoot
                    target.movement_time = m_time
                    target.hold_stability = stability / 100.0

                    self.sounds.play('catch')
                    self.particles.emit(GAME_AREA_WIDTH // 2, 380, (50, 230, 140), 25)
                    self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2, 340, f"TARGET HELD! +{points}", (50, 230, 140)))

                    self._advance_level14_target()
                    return
        else:
            # Dropped out of target zone during dwell hold
            if self.wrist_dwell_start is not None:
                if (now - self.wrist_dwell_start) > 0.15:
                    self.dwell_failure_count += 1
                self.wrist_dwell_start = None
                self.wrist_contact_progress = 0.0
                self.wrist_dwell_samples.clear()
                target.state = "WAITING"

        # Check prompt timeout
        elapsed_prompt = now - self.wrist_target_start
        if elapsed_prompt > self.prompt_timeout:
            self.total_attempts = getattr(self, 'total_attempts', 0) + 1
            self.accuracy_attempts = getattr(self, 'accuracy_attempts', 0) + 1
            self.combo = 0

            if t_angle > 0:
                self.extension_attempts += 1
            else:
                self.flexion_attempts += 1

            self.trial_movement_times.append(self.prompt_timeout)
            self.trial_target_errors.append(current_error)
            self.trial_overshoots.append(overshoot)
            self.trial_hold_stabilities.append(0.0)
            self.trial_direction_correct.append(1 if is_correct_dir else 0)

            self.average_movement_time = sum(self.trial_movement_times) / len(self.trial_movement_times)
            self.average_target_error = sum(self.trial_target_errors) / len(self.trial_target_errors)
            self.average_overshoot = sum(self.trial_overshoots) / len(self.trial_overshoots)
            self.average_hold_stability = sum(self.trial_hold_stabilities) / len(self.trial_hold_stabilities)
            self.direction_accuracy = (sum(self.trial_direction_correct) / len(self.trial_direction_correct)) * 100.0

            target.state = "MISSED"
            target.target_error = current_error
            target.overshoot = overshoot
            target.movement_time = self.prompt_timeout
            target.hold_stability = 0.0

            self.sounds.play('pop')
            self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2, 340, "TIME OUT", (200, 200, 210)))
            self._advance_level14_target()
            return

        # Overall session timeout
        if (now - self.session_start > self.session_time_limit) or (now - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            remaining = self.wrist_targets[self.current_target_idx:]
            for t in remaining:
                self.total_attempts = getattr(self, 'total_attempts', 0) + 1
                self.accuracy_attempts = getattr(self, 'accuracy_attempts', 0) + 1
                if t.target_angle > 0:
                    self.extension_attempts += 1
                else:
                    self.flexion_attempts += 1
            self._end_level()

    def _advance_level14_target(self):
        """Advance to next target zone in Level 14."""
        self.current_target_idx += 1
        now = time.time()
        if self.current_target_idx < len(self.wrist_targets):
            self.wrist_active_target = self.wrist_targets[self.current_target_idx]
            self.active_prompt = self.wrist_active_target
            self.current_prompt = self.wrist_active_target
            self.wrist_active_target.presented_time = now
            self.wrist_target_start = now
            self.wrist_dwell_start = None
            self.wrist_contact_progress = 0.0
            self.wrist_entry_time = None
            self.wrist_dwell_samples.clear()
        else:
            self.wrist_active_target = None
            self.active_prompt = None
            self.current_prompt = None
            self._end_level()

    def _draw_level14(self):
        """
        Draw Level 14: Wrist Flexion-Extension Control.
        Shows patient-friendly vertical control meter, active target zone,
        moving indicator, dwell progress, and clinical performance telemetry.
        """
        theme = self._get_theme()
        primary = theme.get("primary_color", (0, 200, 255))
        level_name = theme.get('level14_name', 'Wrist Flexion-Extension Control')

        now = time.time()
        font_head = getattr(self, 'font_head', None) or pygame.font.SysFont("segoeui", 26, bold=True)
        font_hint = getattr(self, 'font_hint', None) or pygame.font.SysFont("segoeui", 14)
        font_stat_b = getattr(self, 'font_vault', None) or pygame.font.SysFont("segoeui", 12, bold=True)
        font_stat_s = getattr(self, 'font_phase', None) or pygame.font.SysFont("segoeui", 11)
        font_target = getattr(self, 'font_tiny', None) or pygame.font.SysFont("segoeui", 16, bold=True)

        # 1. Title & Clinical Guidance Subtitle
        title_surf = font_head.render(f"LEVEL 14: {level_name.upper()}", True, primary)
        self.screen.blit(title_surf, (50, 85))

        sub_text = "Controlled Wrist Flexion & Extension • Reach and Hold Target Zones"
        sub_surf = font_hint.render(sub_text, True, COLOR_MED_MUTED if 'COLOR_MED_MUTED' in globals() else (140, 175, 205))
        self.screen.blit(sub_surf, (50, 118))

        # 2. Performance Telemetry Card (Top Right)
        card_w = 270
        card_h = 54
        card_x = GAME_AREA_WIDTH - card_w - 15
        card_y = 82
        card_bg = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        card_bg.fill((18, 25, 42, 220))
        self.screen.blit(card_bg, (card_x, card_y))
        pygame.draw.rect(self.screen, primary, (card_x, card_y, card_w, card_h), 1, border_radius=8)

        if self.accuracy_attempts > 0:
            acc_val = (self.accuracy_hits / self.accuracy_attempts) * 100.0
            acc_str = f"Acc: {int(acc_val)}%"
        else:
            acc_str = "Acc: --%"
        stat_l1 = font_stat_b.render(f"{acc_str}   Hits: {self.accuracy_hits}/{self.accuracy_attempts}   Err: {self.average_target_error:.1f}°", True, (220, 235, 250))
        self.screen.blit(stat_l1, (card_x + 10, card_y + 8))
        stat_l2 = font_stat_s.render(f"Stability: {self.average_hold_stability:.0f}%   Overshoot: {self.average_overshoot:.1f}°   Dir: {self.direction_accuracy:.0f}%", True, (150, 185, 215))
        self.screen.blit(stat_l2, (card_x + 10, card_y + 30))

        # 3. Patient Instruction Banner (Top Center)
        if self.wrist_active_target:
            ttype = self.wrist_active_target.target_type
            is_ext = (ttype == "EXTENSION")
            arrow_icon = "↑" if is_ext else "↓"
            action_name = "MOVE UP (EXTENSION)" if is_ext else "MOVE DOWN (FLEXION)"
            banner_col = (50, 220, 255) if is_ext else (255, 160, 50)

            tb_w = 520
            tb_h = 42
            tb_x = (GAME_AREA_WIDTH - tb_w) // 2
            tb_y = 146

            tb_bg = pygame.Surface((tb_w, tb_h), pygame.SRCALPHA)
            tb_bg.fill((*banner_col[:3], 35))
            self.screen.blit(tb_bg, (tb_x, tb_y))
            pygame.draw.rect(self.screen, banner_col, (tb_x, tb_y, tb_w, tb_h), 2, border_radius=10)

            if self.wrist_dwell_start:
                dwell_frac = min(1.0, (now - self.wrist_dwell_start) / self.wrist_dwell_required)
                status_txt = f"HOLD STEADY... {int(dwell_frac * 100)}%"
                status_col = (100, 255, 180)
            elif self.live_in_zone:
                status_txt = "IN TARGET! HOLD POSITION"
                status_col = (100, 255, 180)
            else:
                status_txt = "Slowly tilt wrist into target zone"
                status_col = (220, 240, 255)

            callout_str = f"🎯 {arrow_icon} {action_name}   •   {status_txt}"
            callout_surf = font_target.render(callout_str, True, status_col)
            self.screen.blit(callout_surf, callout_surf.get_rect(center=(tb_x + tb_w // 2, tb_y + tb_h // 2)))

        # 4. Large Vertical Control Meter
        meter_w = 200
        meter_h = 320
        meter_x = (GAME_AREA_WIDTH - meter_w) // 2
        meter_y = 210

        # Meter background surface
        m_surf = pygame.Surface((meter_w, meter_h), pygame.SRCALPHA)
        m_surf.fill((16, 22, 36, 220))
        self.screen.blit(m_surf, (meter_x, meter_y))
        pygame.draw.rect(self.screen, (40, 58, 85), (meter_x, meter_y, meter_w, meter_h), 2, border_radius=14)

        # Center Neutral Guideline (0 degrees)
        cy_meter = meter_y + meter_h // 2
        pygame.draw.line(self.screen, (70, 95, 130), (meter_x + 10, cy_meter), (meter_x + meter_w - 10, cy_meter), 1)
        neutral_lbl = font_stat_s.render("— NEUTRAL (0°) [Press 'C' to Zero] —", True, (110, 135, 165))
        self.screen.blit(neutral_lbl, neutral_lbl.get_rect(center=(meter_x + meter_w // 2, cy_meter - 10)))

        # Top/Bottom Zone Labels
        ext_lbl = font_stat_b.render("↑ EXTENSION (UP)", True, (50, 220, 255))
        self.screen.blit(ext_lbl, ext_lbl.get_rect(center=(meter_x + meter_w // 2, meter_y + 16)))

        flex_lbl = font_stat_b.render("↓ FLEXION (DOWN)", True, (255, 160, 50))
        self.screen.blit(flex_lbl, flex_lbl.get_rect(center=(meter_x + meter_w // 2, meter_y + meter_h - 16)))

        # Angular range mapping: -45° (bottom) to +45° (top)
        scale_px = (meter_h // 2 - 35) / 45.0

        # Draw Target Zone Box
        if self.wrist_active_target:
            t = self.wrist_active_target
            t_angle = t.target_angle
            tol = t.tolerance

            top_y = cy_meter - int((t_angle + tol) * scale_px)
            bot_y = cy_meter - int((t_angle - tol) * scale_px)
            zone_h = max(18, bot_y - top_y)
            zone_rect = pygame.Rect(meter_x + 15, top_y, meter_w - 30, zone_h)

            zone_col = (50, 230, 140) if self.live_in_zone else ((50, 220, 255) if t_angle > 0 else (255, 160, 50))
            z_surf = pygame.Surface((zone_rect.width, zone_rect.height), pygame.SRCALPHA)
            z_surf.fill((*zone_col[:3], 65 if self.live_in_zone else 40))
            self.screen.blit(z_surf, zone_rect.topleft)
            pygame.draw.rect(self.screen, zone_col, zone_rect, 2, border_radius=8)

            # Target 🎯 Icon inside zone
            tgt_icon = font_target.render("🎯 TARGET ZONE", True, (255, 255, 255) if self.live_in_zone else zone_col)
            self.screen.blit(tgt_icon, tgt_icon.get_rect(center=zone_rect.center))

        # Draw Current Wrist Position Indicator
        pitch_val = getattr(self, 'live_wrist_pitch', 0.0)
        clamped_pitch = max(-45.0, min(45.0, pitch_val))
        cursor_y = int(cy_meter - clamped_pitch * scale_px)
        cursor_x = meter_x + meter_w // 2

        # Cursor glow and orb
        orb_col = (100, 255, 180) if self.live_in_zone else (255, 220, 100)
        pygame.draw.circle(self.screen, (*orb_col[:3],), (cursor_x, cursor_y), 12)
        pygame.draw.circle(self.screen, (255, 255, 255), (cursor_x, cursor_y), 5)

        # Draw Dwell Hold Radial / Ring if in zone
        if self.wrist_dwell_start and self.wrist_active_target:
            dwell_frac = min(1.0, (now - self.wrist_dwell_start) / self.wrist_dwell_required)
            ring_r = 22
            ring_rect = pygame.Rect(cursor_x - ring_r, cursor_y - ring_r, ring_r * 2, ring_r * 2)
            pygame.draw.arc(self.screen, (100, 255, 180), ring_rect, 0, dwell_frac * 2 * math.pi, 3)

        # 5. Patient Progress Indicator & Response Bar
        if self.wrist_targets:
            tot = len(self.wrist_targets)
            done = self.current_target_idx
            prog_txt = font_hint.render(f"🎯 PROGRESS: {done} / {tot} COMPLETED", True, (200, 230, 255))
            self.screen.blit(prog_txt, prog_txt.get_rect(center=(GAME_AREA_WIDTH // 2, WINDOW_HEIGHT - 65)))

            # Progress bar
            pb_w = 420
            pb_h = 8
            pb_x = (GAME_AREA_WIDTH - pb_w) // 2
            pb_y = WINDOW_HEIGHT - 48
            pygame.draw.rect(self.screen, (25, 32, 50), (pb_x, pb_y, pb_w, pb_h), border_radius=4)
            filled_pb = int(pb_w * (done / max(1, tot)))
            if filled_pb > 0:
                pygame.draw.rect(self.screen, primary, (pb_x, pb_y, filled_pb, pb_h), border_radius=4)

        # Countdown Bar
        if self.wrist_active_target:
            remain = max(0.0, self.prompt_timeout - (now - self.wrist_target_start))
            frac = remain / max(0.1, self.prompt_timeout)
            c_w = 340
            c_h = 6
            c_x = (GAME_AREA_WIDTH - c_w) // 2
            c_y = WINDOW_HEIGHT - 22
            pygame.draw.rect(self.screen, (20, 26, 40), (c_x, c_y, c_w, c_h), border_radius=3)
            bar_col = (50, 230, 140) if frac > 0.4 else (255, 190, 40) if frac > 0.2 else (255, 75, 95)
            pygame.draw.rect(self.screen, bar_col, (c_x, c_y, int(c_w * frac), c_h), border_radius=3)

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
        elif self.state == GameState.LEVEL12_THUMB_OPPOSITION or self.state == GameState.LEVEL12_CARD_SHIFT:
            return "Move your thumb to touch the highlighted finger target!"
        elif self.state == GameState.LEVEL13_FINGER_ISOLATION:
            return "Extend only the prompted finger while keeping other fingers steady"
        elif self.state == GameState.LEVEL14_WRIST_CONTROL:
            return "Perform controlled wrist flexion and extension to reach and hold target zones"
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
        if getattr(self, "current_level", 0) == 14:
            return int(getattr(self, "wrist_completed_targets", 0))
        return int(getattr(self, "accuracy_hits", 0))

    def _get_session_elapsed(self) -> float:
        if self.session_start:
            return max(0.0, time.time() - self.session_start)
        return 0.0

    def _get_correctness_label(self, hand_data: HandData) -> str:
        """
        Evaluates real-time movement quality, alignment, and clinical correctness
        across all 11 games to provide constructive, accurate patient feedback.
        """
        # 1. Hand presence validation
        if hand_data is None or (hand_data.index_tip is None and hand_data.wrist is None and hand_data.palm_center is None):
            return "Incorrect - hand missing"

        # 2. Non-gameplay screens (Menus, calibration, results, history, etc.)
        if self.state in (GameState.MAIN_MENU, GameState.RESULTS, GameState.HISTORY,
                          GameState.PAIN_SCALE, GameState.PATIENT_REGISTRATION,
                          GameState.AGE_SELECT, GameState.CLOUD_SYNC, GameState.THERAPIST_DASHBOARD):
            return "Ready - tracking active"

        if self.state == GameState.CALIBRATION:
            if getattr(hand_data, 'finger_extension', 0) > 120:
                return "Correct - open hand wide"
            return "Ready - calibrate hand"

        # 3. Active warning overrides from gameplay logic
        warning = getattr(self, "correctness_warning", "")
        warning_timer = getattr(self, "warning_timer", 0)
        if warning and warning_timer > 0:
            w_lower = warning.lower()
            if "lost" in w_lower:
                return "Incorrect - return to start"
            if "deviation" in w_lower or "boundary" in w_lower:
                return "Adjust - stay inside path"
            if "follow" in w_lower:
                return "Adjust - follow dot sequence"
            if "good" in w_lower:
                return "Correct - good control"
            if "adjust" in w_lower:
                return warning
            return f"Adjust - {warning}"

        # 4. Compensation detection feedback
        if hasattr(self, 'compensation_detector') and getattr(self.compensation_detector, 'warning_text', ''):
            if time.time() - getattr(self.compensation_detector, 'last_triggered_time', 0.0) < 2.0:
                if self.state in (GameState.LEVEL7_WRIST_MECHANICS, GameState.LEVEL8_SMART_ASSEMBLY):
                    return "Adjust - rotate wrist, not arm"
                return "Adjust - steady controlled motion"

        # 5. Game-specific clinical movement evaluation
        lvl = getattr(self, "current_level", 0)

        # LEVEL 1: FLEXIBILITY (Bubble Pop / Reach & Extension)
        if self.state == GameState.LEVEL1_FLEXIBILITY or lvl == 1:
            if getattr(hand_data, 'is_fist', False):
                return "Adjust - open hand to reach"
            return "Correct - reach for bubbles"

        # LEVEL 2: STRENGTH (The Basket / Catch Falling Items)
        elif self.state == GameState.LEVEL2_STRENGTH or lvl == 2:
            if hand_data.palm_center and hand_data.palm_center[1] < 140:
                return "Adjust - lower hand to basket"
            return "Correct - catch falling items"

        # LEVEL 3: FINE MOTOR (Seed Pinch & Drop in Pot)
        elif self.state == GameState.LEVEL3_FINEMOTOR or lvl == 3:
            active_seed = getattr(self, "active_seed", None)
            if active_seed is not None and getattr(active_seed, 'is_dragged', False):
                pot_rect = getattr(self, "pot_rect", None)
                if pot_rect and pot_rect.collidepoint((active_seed.x, active_seed.y)):
                    return "Correct - release into pot"
                return "Correct - carry to pot"
            if getattr(hand_data, 'is_pinching', False):
                return "Correct - pinch grasp active"
            return "Ready - pinch seed to pick"

        # LEVEL 4: COORDINATION (Moving Target Tracking)
        elif self.state == GameState.LEVEL4_COORDINATION or lvl == 4:
            tx = getattr(self, "target_x", 0)
            ty = getattr(self, "target_y", 0)
            tr = getattr(self, "target_radius", 40)
            if hand_data.index_tip:
                d = distance(hand_data.index_tip, (tx, ty))
                if d <= tr * 1.6:
                    return "Correct - smooth tracking"
                return "Adjust - follow moving target"
            return "Ready - track target"

        # LEVEL 5: GRIP & RELEASE (Fist Pump Cycles)
        elif self.state == GameState.LEVEL5_GRIP_RELEASE or lvl == 5:
            pump_state = getattr(self, "pump_state", 0)
            if pump_state == 0:
                if getattr(hand_data, 'is_fist', False):
                    return "Correct - squeeze detected"
                return "Adjust - squeeze into fist"
            else:
                if not getattr(hand_data, 'is_fist', False) and getattr(hand_data, 'finger_extension', 0) > 110:
                    return "Correct - release detected"
                return "Adjust - open hand fully"

        # LEVEL 6: FINGER TAPS (Memory / Sequence)
        elif self.state == GameState.LEVEL6_FINGER_TAPS or lvl == 6:
            if getattr(self, "simon_state", "") == "SHOW":
                return "Ready - watch sequence"
            return "Correct - tap target pad"

        # LEVEL 7: WRIST MECHANICS (Rotation Orbit & Hold)
        elif self.state == GameState.LEVEL7_WRIST_MECHANICS or lvl == 7:
            target_norm = getattr(self, 'wrist_target_angle', 0.0) % 360
            curr_rot = getattr(hand_data, 'wrist_rotation_angle', 0.0)
            if curr_rot is None:
                curr_rot = 0.0
            base_rot = getattr(self, 'wrist_rotation_baseline', None)
            if base_rot is None:
                base_rot = curr_rot
            relative_rot = curr_rot - base_rot
            current_norm = (relative_rot * 2.0) % 360
            diff = abs(current_norm - target_norm)
            if diff > 180:
                diff = 360 - diff
            tol = getattr(self, 'rotation_tolerance', 25.0)
            if diff <= tol:
                return "Correct - holding rotation"
            return "Adjust - rotate wrist to target"

        # LEVEL 8: SMART ASSEMBLY (Tool Rotation & Slot Insertion)
        elif self.state == GameState.LEVEL8_SMART_ASSEMBLY or lvl == 8:
            parts = getattr(self, "assembly_parts", [])
            grabbed = [p for p in parts if getattr(p, 'is_grabbed', False)]
            if grabbed:
                p = grabbed[0]
                ang_diff = abs(getattr(p, 'current_angle', 0.0) - getattr(p, 'target_angle', 0.0)) % 360
                if ang_diff > 180:
                    ang_diff = 360 - ang_diff
                ang_tol = getattr(self, 'assembly_angle_tolerance', 30.0)
                if ang_diff > ang_tol:
                    return "Adjust - rotate to match slot"
                return "Correct - align part into slot"
            return "Ready - pinch part to grab"

        # LEVEL 9: PRECISION PATH (Connect Numbered Dots)
        elif self.state == GameState.LEVEL9_PRECISION_PATH or lvl == 9:
            dot_idx = getattr(self, "precision_current_dot", 0)
            return f"Correct - moving to dot #{dot_idx + 1}"

        # LEVEL 10: PRECISION PATHWAY (Corridor Tracing)
        elif self.state == GameState.LEVEL10_PRECISION_PATHWAY or lvl == 10:
            if not getattr(self, "pathway_grabbed", False):
                return "Ready - touch start marker"
            return "Correct - centered in pathway"

        # LEVEL 11: COIN VAULT (In-Hand Manipulation)
        elif self.state == GameState.LEVEL11_COIN_VAULT or lvl == 11:
            m_state = getattr(self, "manipulation_state", "READY")
            if m_state in ("READY", "COIN_PRESENTED"):
                if getattr(hand_data, 'is_pinching', False):
                    return "Correct - coin picked up"
                return "Ready - pinch coin to pick"
            elif m_state == "IN_HAND_TRANSLATION":
                return "Correct - translate into palm"
            elif m_state == "IN_HAND_REPOSITION":
                return "Correct - reposition coin"
            elif m_state == "VAULT_PLACEMENT":
                return "Correct - place in matching vault"
            return "Correct - good control"

        # LEVEL 12: CARD SHIFT CHALLENGE (In-Hand Manipulation)
        elif self.state == GameState.LEVEL12_THUMB_OPPOSITION or self.state == GameState.LEVEL12_CARD_SHIFT or lvl == 12:
            prompt = getattr(self, "active_prompt", None)
            if prompt:
                dist = getattr(self, "current_target_distance", 999.0)
                tol = getattr(self, "card_shift_tolerance", 45.0)
                if dist <= tol:
                    return f"Correct - holding {prompt.target_digit_name}"
                return f"Adjust - touch {prompt.target_digit_name}"
            return "Correct - good control"

        # LEVEL 13: FINGER ISOLATION CHALLENGE
        elif self.state == GameState.LEVEL13_FINGER_ISOLATION or lvl == 13:
            prompt = getattr(self, "isolation_active_prompt", None)
            if prompt:
                target_name = prompt.digit_name
                if getattr(self, "live_unintended_digits", None):
                    return f"Adjust - keep other fingers still"
                if getattr(self, "isolation_dwell_start", None):
                    return f"Correct - holding {target_name}"
                return f"Adjust - extend only {target_name}"
            return "Correct - good control"

        # LEVEL 14: WRIST FLEXION-EXTENSION CONTROL
        elif self.state == GameState.LEVEL14_WRIST_CONTROL or lvl == 14:
            target = getattr(self, "wrist_active_target", None)
            if target:
                ttype = target.target_type
                if getattr(self, "wrist_dwell_start", None):
                    return f"Correct - holding {ttype.lower()}"
                if getattr(self, "live_in_zone", False):
                    return f"Correct - in {ttype.lower()} zone"
                return f"Adjust - tilt wrist to {ttype.lower()}"
            return "Correct - good control"

        return "Correct - good control"

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
        self.successful_hits = 0
        self.total_attempts = 0
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
            11: "manipulation_success_rate",
            12: "completion_rate",
            13: "finger_isolation_accuracy",
            14: "wrist_target_accuracy"
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
            self.seeds.clear()
            self._spawn_seed()
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
        elif lv == 12:
            self.state = GameState.LEVEL12_CARD_SHIFT
            self._init_level12()
            VOICE.speak("Level 12: Target Touch. Move your thumb to touch each highlighted finger.")
        elif lv == 13:
            self.state = GameState.LEVEL13_FINGER_ISOLATION
            self._init_level13()
            VOICE.speak("Level 13: Finger Isolation Challenge. Raise only the highlighted finger while keeping other fingers still.")
        elif lv == 14:
            self.state = GameState.LEVEL14_WRIST_CONTROL
            self._init_level14()
            VOICE.speak("Level 14: Wrist Flexion-Extension Control. Tilt your wrist upward or downward to reach and hold each target zone.")
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


