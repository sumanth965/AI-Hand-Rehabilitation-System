import os

with open('zero_keyboard_physio.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

def insert_before(pattern, code):
    global lines
    for i, line in enumerate(lines):
        if pattern in line:
            lines.insert(i, code)
            return True
    return False

# 1. Add AssemblyPart
dataclass_code = '''
from dataclasses import dataclass, field
from typing import Optional, Tuple, List

@dataclass
class AssemblyPart:
    name: str
    target_pos: tuple
    target_angle: float
    current_pos: list
    current_angle: float
    color: tuple
    shape: list
    is_grabbed: bool = False
    is_locked: bool = False

'''
insert_before('class Bubble:', dataclass_code)

# 2. Add Level 8 to Level Select UI
for i, line in enumerate(lines):
    if 'LevelButton(col1_x, 485, bw, 80, "LEVEL 7", 7, ring_radius=48)' in line:
        lines[i] = line.replace('ring_radius=48)', 'ring_radius=48),\n            LevelButton(col2_x, 485, bw, 80, "LEVEL 8", 8, ring_radius=48)')
        break

# 3. Add Level 8 initialization to _start_level
start_level_code = '''        elif lv == 8:
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
'''
insert_before("        self.sounds.play('select')", start_level_code)

# 4. Add _update_level8
update_level8_code = '''
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
                    if dist < 80:
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
                    
                    if dist < 50 and ang_diff < 30:
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
        if (time.time() - self.session_start > 120):
            self.accuracy_attempts += 1
            self._end_level()

'''
insert_before('    def _draw_cyber_grid', update_level8_code)

# 5. Add _draw_level8
draw_level8_code = '''
    def _draw_level8(self):
        """Draw Level 8: Smart Assembly"""
        theme = self._get_theme()
        primary = theme['primary_color']
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        
        level_name = theme.get('level8_name', 'Toy Builder')
        title = getattr(self, 'font_medium').render(f"LEVEL 8: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))
        
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

'''
insert_before('    def _get_level_goals', draw_level8_code)

# 6. Add game loop calls
for i, line in enumerate(lines):
    if 'elif self.state == GameState.LEVEL7_WRIST_MECHANICS:' in line:
        lines.insert(i+3, '        elif self.state == GameState.LEVEL8_SMART_ASSEMBLY:\n            if not getattr(self, \'tracking_lost\', False):\n                self._update_level8(hand_data)\n')
        break

for i, line in enumerate(lines):
    if 'elif self.state == GameState.LEVEL7_WRIST_MECHANICS:' in line and 'self._draw_level7()' in lines[i+1]:
        lines.insert(i+2, '        elif self.state == GameState.LEVEL8_SMART_ASSEMBLY:\n            self._draw_level8()\n')
        break

with open('zero_keyboard_physio.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
