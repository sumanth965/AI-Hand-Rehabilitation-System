"""Screen rendering and interaction helpers for PhysioSystem."""

from ..shared import *


class ResultsScreenMixin:
    def _draw_level_complete(self):
        """Full-screen 2.5-second celebration screen between gameplay and report"""
        t   = time.time()
        cx  = GAME_AREA_WIDTH // 2
        cy  = WINDOW_HEIGHT // 2
        elapsed = t - self._level_complete_time

        # Dark overlay
        self.screen.fill((5, 12, 28))

        # Spinning confetti ring
        n_dots = 24
        ring_r = 180 + int(20 * math.sin(t * 4))
        for i in range(n_dots):
            angle = (2 * math.pi * i / n_dots) + t * 2
            dx = int(cx + ring_r * math.cos(angle))
            dy = int(cy + ring_r * math.sin(angle))
            col = [
                (255, 215, 0), (0, 220, 120), (0, 200, 255),
                (255, 100, 180), (200, 160, 255)
            ][i % 5]
            pygame.draw.circle(self.screen, col, (dx, dy), 8)

        # Inner glow
        glow = int(60 + 30 * abs(math.sin(t * 3)))
        pygame.draw.circle(self.screen, (0, glow, glow // 2), (cx, cy), 130)
        pygame.draw.circle(self.screen, (0, 180, 220), (cx, cy), 130, 3)

        # Level complete text
        lc1 = self.font_large.render("LEVEL COMPLETE!", True, (50, 220, 120))
        self.screen.blit(lc1, lc1.get_rect(center=(cx, cy - 60)))

        # Stars
        acc = (self.accuracy_hits / max(self.accuracy_attempts, 1)) * 100
        stars = 3 if acc >= 80 else (2 if acc >= 55 else 1)
        star_col = [(220,60,60),(255,180,0),(50,220,120)][stars-1]
        star_str = "★" * stars + "☆" * (3 - stars)
        ss = self.font_large.render(star_str, True, star_col)
        self.screen.blit(ss, ss.get_rect(center=(cx, cy)))

        # Score
        sc = self.font_medium.render(f"Score: {self.score}", True, (255, 255, 255))
        self.screen.blit(sc, sc.get_rect(center=(cx, cy + 60)))

        # Countdown
        remaining = max(0, 2.5 - elapsed)
        cd_col = (100, 200, 255) if remaining > 1.0 else (255, 180, 0)
        cd = self.font_small.render(f"Report in {remaining:.1f}s ...", True, cd_col)
        self.screen.blit(cd, cd.get_rect(center=(cx, cy + 110)))

        # Particle burst every 0.3s
        if int(elapsed * 10) % 3 == 0:
            self.particles.emit(
                cx + random.randint(-150, 150),
                cy + random.randint(-100, 100),
                random.choice([(255,215,0),(0,220,120),(0,200,255),(255,100,150)]),
                8
            )
        self.particles.update()
        self.particles.draw(self.screen)

    def _draw_progress_chart(self):
        """Draws a compact 'Last 6 Sessions' progress bar chart in the sidebar area"""
        sessions = self.db.get_recent_sessions(6)
        if not sessions:
            return

        # Panel sits in the right sidebar strip, below camera & hand status (starting at panel_y=352)
        panel_x = GAME_AREA_WIDTH + 4
        panel_y = 352
        panel_w = SIDEBAR_WIDTH - 8
        panel_h = WINDOW_HEIGHT - panel_y - 12

        # Background
        pygame.draw.rect(self.screen, (5, 12, 24),
                         pygame.Rect(panel_x, panel_y, panel_w, panel_h), border_radius=8)
        pygame.draw.rect(self.screen, (0, 180, 220),
                         pygame.Rect(panel_x, panel_y, panel_w, panel_h), 1, border_radius=8)

        # CRT Grid in chart area
        chart_x = panel_x + 14
        chart_y = panel_y + 45
        chart_w = panel_w - 28
        chart_h = 130
        
        pygame.draw.rect(self.screen, (2, 8, 15),
                         pygame.Rect(chart_x, chart_y, chart_w, chart_h), border_radius=4)
        
        for gy in range(chart_y, chart_y + chart_h, 20):
            pygame.draw.line(self.screen, (10, 25, 40), (chart_x, gy), (chart_x + chart_w, gy))
        for gx in range(chart_x, chart_x + chart_w, 25):
            pygame.draw.line(self.screen, (10, 25, 40), (gx, chart_y), (gx, chart_y + chart_h))

        # Header
        hdr = self.font_hud.render("ANALYTICS MONITOR", True, (0, 255, 180))
        self.screen.blit(hdr, hdr.get_rect(center=(panel_x + panel_w // 2, panel_y + 14)))
        sub = self.font_tiny.render("PATIENT PERFORMANCE HISTORY", True, (0, 150, 120))
        self.screen.blit(sub, sub.get_rect(center=(panel_x + panel_w // 2, panel_y + 30)))

        n = len(sessions)
        bar_w = (chart_w - (n - 1) * 6) // n

        for i, (level, acc, angle, score, date) in enumerate(sessions):
            bx = chart_x + i * (bar_w + 6)
            bar_h = int(chart_h * min(acc / 100, 1.0))
            by = chart_y + chart_h - bar_h

            # CRT Phosphorus Green for all bars, highlight latest
            base_green = (0, 200, 100)
            if i == n - 1:
                pygame.draw.rect(self.screen, (0, 255, 150), pygame.Rect(bx, by, bar_w, bar_h), border_radius=2)
                pygame.draw.rect(self.screen, (255, 255, 255), pygame.Rect(bx, by, bar_w, bar_h), 1, border_radius=2)
            else:
                pygame.draw.rect(self.screen, (0, 120, 60), pygame.Rect(bx, by, bar_w, bar_h), border_radius=2)
            
            # Glow effect for bars
            if bar_h > 5:
                pygame.draw.line(self.screen, (100, 255, 200), (bx, by), (bx + bar_w, by), 1)

            # Accuracy label on bar
            if bar_h > 20:
                lbl = self.font_hint.render(f"{acc:.0f}%", True, (255, 255, 255))
                self.screen.blit(lbl, lbl.get_rect(center=(bx + bar_w // 2, by + 10)))

            # Date label below
            dl = self.font_hint.render(date or f"S{i+1}", True, (100, 130, 170))
            self.screen.blit(dl, dl.get_rect(center=(bx + bar_w // 2,
                                                      chart_y + chart_h + 10)))

        # 75% goal line
        goal_y = chart_y + chart_h - int(chart_h * 0.75)
        pygame.draw.line(self.screen, (255, 200, 60),
                         (chart_x, goal_y), (chart_x + chart_w, goal_y), 1)
        gl = self.font_hint.render("75% goal", True, (255, 200, 60))
        self.screen.blit(gl, (chart_x + 2, goal_y - 14))

        # Level trend info below chart
        y2 = chart_y + chart_h + 24
        if len(sessions) >= 2:
            latest_acc  = sessions[-1][1]
            prev_acc    = sessions[-2][1]
            delta       = latest_acc - prev_acc
            trend_str   = f"Trend: {'+' if delta >= 0 else ''}{delta:.1f}% vs last"
            trend_col   = (50, 220, 120) if delta >= 0 else (255, 120, 80)
            ts = self.font_hint.render(trend_str, True, trend_col)
            self.screen.blit(ts, ts.get_rect(center=(panel_x + panel_w // 2, y2)))
            y2 += 16

        # Sessions per level breakdown
        level_counts = {}
        for s in sessions:
            level_counts[s[0]] = level_counts.get(s[0], 0) + 1
        for lv, cnt in sorted(level_counts.items()):
            lcolors = [(100,160,255),(0,220,120),(255,150,80)]
            lc = self.font_hint.render(f"L{lv}: {cnt} session{'s' if cnt>1 else ''}",
                                        True, lcolors[min(lv-1, 2)])
            self.screen.blit(lc, (chart_x, y2))
            y2 += 16

    def _draw_results(self):
        """Draw post-game clinical report screen"""
        if self.session_data:
            self.summary_screen.draw(
                self.screen, self.session_data, self.best_data,
                patient_name=self.patient_name or "Patient"
            )
            
            # PLAY AGAIN, NEXT, MAIN MENU, CLOSE buttons
            self.menu_button.draw(self.screen, self.font_small, text="PLAY AGAIN", base_col=(25,40,25), hov_col=(40,80,40))
            if hasattr(self, 'next_button') and getattr(self, 'current_level', 1) < 8:
                self.next_button.draw(self.screen, self.font_small, text="NEXT GAME", base_col=(25,25,50), hov_col=(40,40,80))
            self.home_button.draw(self.screen, self.font_small, text="MAIN MENU", base_col=(60,30,90), hov_col=(100,50,150))
            self.close_button.draw(self.screen, self.font_small)

    def _draw_cloud_sync(self):
        """Draw fake cloud sync animation"""
        self.screen.fill((10, 15, 25))
        cx, cy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
        
        t = time.time()
        elapsed = t - getattr(self, 'sync_start', t)
        progress = min(elapsed / 2.0, 1.0)
        
        # Draw rotating rings
        for i in range(3):
            radius = 100 + i * 30
            angle = t * (2 + i)
            pygame.draw.arc(self.screen, (0, 200, 255), 
                            (cx - radius, cy - radius, radius*2, radius*2),
                            angle, angle + math.pi, 4)
                            
        # Text
        txt = self.font_large.render("Syncing Securely to Medical Database...", True, (255, 255, 255))
        self.screen.blit(txt, txt.get_rect(center=(cx, cy + 180)))
        
        # Progress Bar
        bar_w = 400
        bar_x = cx - bar_w // 2
        pygame.draw.rect(self.screen, (40, 50, 70), (bar_x, cy + 240, bar_w, 10), border_radius=5)
        if progress > 0:
            pygame.draw.rect(self.screen, (50, 255, 150), (bar_x, cy + 240, int(bar_w * progress), 10), border_radius=5)
            
        hand_data = self.hand_engine.get_hand_data()
        self._draw_cursor(hand_data)

    def _update_therapist_dashboard(self, hand_data):
        if not hasattr(self, 'admin_back_button'):
            self.admin_back_button = LevelButton(50, 150, 250, 80, "EXIT ADMIN", 0)
            self.admin_purge_button = LevelButton(50, 270, 350, 80, "PURGE ALL PATIENT DATA", 99)
            self.admin_timer_button = LevelButton(50, 390, 350, 80, f"LEVEL DURATION: {self.session_time_limit}s", 88)
            
        if self.admin_purge_button.update(hand_data.index_tip):
            try:
                self.db.cursor.execute("DELETE FROM sessions")
                self.db.conn.commit()
                self.sounds.play('level_complete')
            except: pass
            
        if self.admin_timer_button.update(hand_data.index_tip):
            self.session_time_limit = 60 if self.session_time_limit == 30 else 30
            self.admin_timer_button.text = f"LEVEL DURATION: {self.session_time_limit}s"
            self.sounds.play('select')

    def _draw_therapist_dashboard(self):
        self.screen.fill((20, 10, 15)) # Dark red/black to indicate admin mode
        title = self.font_large.render("THERAPIST CONFIGURATION PANEL", True, (255, 100, 100))
        self.screen.blit(title, (50, 50))
        
        self.admin_back_button.draw(self.screen, self.font_medium, base_col=(100, 40, 40), hov_col=(150, 50, 50))
        self.admin_purge_button.draw(self.screen, self.font_medium, base_col=(180, 20, 20), hov_col=(255, 40, 40))
        self.admin_timer_button.draw(self.screen, self.font_medium, base_col=(40, 100, 40), hov_col=(60, 150, 60))
        
        hand_data = self.hand_engine.get_hand_data()
        self._draw_cursor(hand_data)

# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    print("=" * 70)
    print("ZERO-KEYBOARD AI PHYSIOTHERAPY SYSTEM")
    print("=" * 70)
    print("\nFeatures:")
    print("  * Split-screen layout (75% game, 25% medical sidebar)")
    print("  * Total hand control - no keyboard/mouse needed")
    print("  * Hover-to-click with selection rings")
    print("  * Fist-hold to pause/quit (2 seconds)")
    print("  * Threaded camera for 60 FPS performance")
    print("  * Weighted average smoothing")
    print("  * Real-time joint angles and analytics")
    print("\nLevels:")
    print("  1. Flexibility - Pop bubbles in corners")
    print("  2. Strength - Catch falling items with palm")
    print("  3. Fine Motor - Pinch seeds and drop in pot")
    print("\nStarting system...")
    print("=" * 70)
    
    app = PhysioSystem()
    app.run()
    
    print("\n* System closed successfully")

if __name__ == "__main__":
    main()

