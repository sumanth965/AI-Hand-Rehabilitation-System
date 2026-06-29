import os

with open('zero_keyboard_physio.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

update7 = '''
    def _update_level7(self, hand_data: HandData):
        """Level 7: Advanced Wrist Mechanics"""
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        
        if not getattr(self, 'wrist_mode', None):
            self.wrist_mode = "rotation"
            self.wrist_target_angle = 45.0
            self.wrist_hold_time = 0.0

        if not hand_data.index_tip or not hand_data.wrist: return
        
        current_angle = hand_data.wrist_rotation_angle if self.wrist_mode == "rotation" else hand_data.wrist_deviation_angle
        diff = abs(current_angle - self.wrist_target_angle)
        
        if diff < 20.0:
            self.wrist_hold_time += 1/30.0
            if self.wrist_hold_time > 1.5:
                self.score += int(10 * getattr(self, 'score_multiplier', 1.0))
                self.accuracy_hits += 1
                self.accuracy_attempts += 1
                self.particles.emit(cx, cy, (0,255,0), 20)
                self.sounds.play('catch')
                self.popups.append(ScorePopup(cx, cy - 80, "PERFECT!", (0,255,0)))
                
                self.wrist_hold_time = 0.0
                import random
                if random.random() > 0.5:
                    self.wrist_mode = "rotation"
                    self.wrist_target_angle = random.choice([-80, -45, 0, 45, 80])
                else:
                    self.wrist_mode = "deviation"
                    self.wrist_target_angle = random.choice([-30, -15, 0, 15, 30])
                    
                self.combo += 1
                if self.combo % 2 == 0:
                    self._trigger_feedback()
        else:
            self.wrist_hold_time = max(0.0, self.wrist_hold_time - 1/60.0)
            
        import time
        if (time.time() - self.session_start > 30) or (time.time() - getattr(self, 'level_wall_start', 0.0) > 45.0):
            self.accuracy_attempts = max(self.accuracy_attempts, 5)
            self._end_level()
'''

draw7 = '''
    def _draw_level7(self):
        """Draw Level 7: Wrist Dial"""
        theme = self._get_theme()
        primary = theme['primary_color']
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        
        if not getattr(self, 'wrist_mode', None):
            self.wrist_mode = "rotation"
            self.wrist_target_angle = 45.0
            self.wrist_hold_time = 0.0

        level_name = theme.get('level7_name', 'Wrist Dial')
        title = getattr(self, 'font_medium').render(f"LEVEL 7: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))
        
        import math
        import pygame
        pygame.draw.circle(self.screen, (30, 40, 50), (cx, cy), 150, 4)
        
        tgt_rad = math.radians(self.wrist_target_angle)
        tx = cx + int(math.cos(tgt_rad) * 150)
        ty = cy + int(math.sin(tgt_rad) * 150)
        pygame.draw.line(self.screen, (0,255,0), (cx, cy), (tx, ty), 4)
        pygame.draw.circle(self.screen, (0,255,0), (tx, ty), 10)
        
        if getattr(self, 'engine', None) and self.engine.hand_data:
            current_angle = self.engine.hand_data.wrist_rotation_angle if self.wrist_mode == "rotation" else self.engine.hand_data.wrist_deviation_angle
            cur_rad = math.radians(current_angle)
            lx = cx + int(math.cos(cur_rad) * 150)
            ly = cy + int(math.sin(cur_rad) * 150)
            pygame.draw.line(self.screen, primary, (cx, cy), (lx, ly), 6)
            pygame.draw.circle(self.screen, primary, (lx, ly), 8)
            
            if self.wrist_hold_time > 0:
                prog = min(1.0, self.wrist_hold_time / 1.5)
                arc_rect = pygame.Rect(cx-170, cy-170, 340, 340)
                pygame.draw.arc(self.screen, primary, arc_rect, -math.pi/2, -math.pi/2 + (2*math.pi*prog), 8)
                
        mode_text = "ROTATE WRIST (Pronation/Supination)" if self.wrist_mode == "rotation" else "BEND WRIST (Radial/Ulnar Deviation)"
        inst = getattr(self, 'font_small').render(mode_text, True, (200, 200, 200))
        self.screen.blit(inst, inst.get_rect(center=(cx, cy + 200)))
'''

for i, line in enumerate(lines):
    if 'def _draw_cyber_grid' in line:
        lines.insert(i, update7 + '\n')
        break

for i, line in enumerate(lines):
    if 'def _get_level_goals' in line:
        lines.insert(i, draw7 + '\n')
        break

with open('zero_keyboard_physio.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
