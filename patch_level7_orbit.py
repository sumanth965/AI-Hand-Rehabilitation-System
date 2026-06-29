import os

with open('zero_keyboard_physio.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

def replace_function(lines, func_name, new_code):
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(lines):
        if line.startswith(f"    def {func_name}"):
            start_idx = i
            break
            
    if start_idx != -1:
        # Find end of function
        for i in range(start_idx + 1, len(lines)):
            if lines[i].startswith("    def ") or lines[i].startswith("class "):
                end_idx = i
                break
        if end_idx == -1:
            end_idx = len(lines)
            
        del lines[start_idx:end_idx]
        lines.insert(start_idx, new_code)
        return True
    return False

# 1. Update Voice Prompt in _start_level
for i, line in enumerate(lines):
    if 'VOICE.speak("Level 7: Wrist Mechanics.' in line:
        lines[i] = '            VOICE.speak("Level 7: Rotation Orbit. Rotate your forearm to align the satellite with the orbital target.")\n'
        break

# 2. Rewrite _update_level7
update_level7_code = '''    def _update_level7(self, hand_data: HandData):
        """Level 7: Rotation Orbit (Forearm Pronation/Supination)"""
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        
        if not getattr(self, 'wrist_mode', None):
            self.wrist_mode = "rotation"
            self.wrist_target_angle = 45.0 # Starting orbital target
            self.wrist_hold_time = 0.0

        if not hand_data.index_tip or not hand_data.wrist: return
        
        # We scale the physical rotation (-90 to +90) into a 360 degree orbit
        # Physical rotation is usually smaller, so * 2 gives a full circle feel
        current_angle = hand_data.wrist_rotation_angle * 2.0
        
        # Normalize angles to 0-360 for comparison
        target_norm = self.wrist_target_angle % 360
        current_norm = current_angle % 360
        
        diff = abs(current_norm - target_norm)
        if diff > 180: diff = 360 - diff
        
        if diff < 25.0: # 25 degree tolerance for "locking on"
            self.wrist_hold_time += 1/30.0
            if self.wrist_hold_time > 1.5:
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
        if (time.time() - getattr(self, 'session_start', 0)) > 60:
            self.accuracy_attempts += 1
            self._end_level()

'''
replace_function(lines, "_update_level7", update_level7_code)

# 3. Rewrite _draw_level7
draw_level7_code = '''    def _draw_level7(self):
        """Draw Level 7: Rotation Orbit"""
        import math
        import pygame
        theme = self._get_theme()
        primary = theme['primary_color']
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        orbit_radius = 200
        
        level_name = theme.get('level7_name', 'Rotation Orbit')
        title = getattr(self, 'font_medium').render(f"LEVEL 7: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))
        
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

'''
replace_function(lines, "_draw_level7", draw_level7_code)

# Wait, we need to make sure _update_level7 saves self.satellite_angle so _draw_level7 can use it.
# Let's modify the update code slightly to add it.
for i, line in enumerate(lines):
    if 'current_angle = hand_data.wrist_rotation_angle * 2.0' in line:
        lines.insert(i+1, '        self.satellite_angle = current_angle\n')
        break

with open('zero_keyboard_physio.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
