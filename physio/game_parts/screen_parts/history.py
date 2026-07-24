"""Screen rendering and interaction helpers for PhysioSystem."""

from ..shared import *


class HistoryScreenMixin:
    def _update_history(self, hand_data: HandData):
        """Fist 2s returns to menu; otherwise just idle"""
        # Purge button logic
        if self.purge_button.update(hand_data.index_tip):
            self.db.clear_all_history()
            self.dashboard_surf = None # Force chart redraw
            self.dashboard_loading = True
            
            def load_async():
                try:
                    surf = self.db.render_matplotlib_dashboard(self.patient_name)
                    self.dashboard_surf = surf
                except Exception as e:
                    print(f"Failed loading async chart on purge: {e}")
                finally:
                    self.dashboard_loading = False

            threading.Thread(target=load_async, daemon=True).start()
            self.purge_button.hover_start = None
            self.sounds.play('pop')

        # Back button logic
        if self.history_back_button.update(hand_data.index_tip):
            self.state = GameState.MAIN_MENU
            self.sounds.play('pop')

        # Use home_icon fist detection to return
        if hand_data.is_fist:
            if not hasattr(self, '_hist_fist_t'):
                self._hist_fist_t = time.time()
            elif time.time() - self._hist_fist_t > 1.5:
                self.state = GameState.MAIN_MENU
                del self._hist_fist_t
        else:
            if hasattr(self, '_hist_fist_t'):
                del self._hist_fist_t

    def _draw_history(self):
        """Full-screen session history + ROM trend line chart"""
        self.screen.fill((8, 14, 30))
        cx = WINDOW_WIDTH // 2

        # Header
        pygame.draw.rect(self.screen, (10, 20, 50),
                         pygame.Rect(0, 0, WINDOW_WIDTH, 70))
        p_name = self.patient_name.upper() if self.patient_name else "UNKNOWN"
        h1 = self.font_large.render(f"SESSION HISTORY: {p_name}", True, (0, 200, 255))
        self.screen.blit(h1, h1.get_rect(center=(cx, 35)))

        sessions = self.db.get_session_history(15, patient_id=self.patient_name)
        rom_data  = self.db.get_rom_trend(10, patient_id=self.patient_name)

        # ── Left: Session Table ──────────────────────────────────────
        table_x = 20
        table_y = 80
        col_w   = [40, 160, 40, 70, 70, 70, 60, 50]  # id,date,lvl,score,acc,rom,dur,pain
        headers = ["ID", "Date/Time", "Lv", "Score", "Acc%", "ROM°", "Sec", "Pain"]
        header_col = (0, 255, 180)

        # Table background (CRT Terminal Style)
        pygame.draw.rect(self.screen, (5, 10, 20), pygame.Rect(table_x - 10, table_y - 10, sum(col_w) + 20, WINDOW_HEIGHT - 120), border_radius=5)
        pygame.draw.rect(self.screen, (0, 120, 100), pygame.Rect(table_x - 10, table_y - 10, sum(col_w) + 20, WINDOW_HEIGHT - 120), 1, border_radius=5)

        header_col = (0, 255, 180)
        x = table_x
        for h, w in zip(headers, col_w):
            hs = self.font_hint.render(h, True, header_col)
            self.screen.blit(hs, (x, table_y))
            x += w
        pygame.draw.line(self.screen, (0, 100, 80),
                         (table_x, table_y + 18),
                         (table_x + sum(col_w), table_y + 18), 1)

        pain_colors = [(50,220,120),(80,220,100),(130,220,80),(180,220,60),
                       (220,220,40),(255,200,0),(255,160,0),(255,100,0),
                       (240,60,60),(220,30,30),(200,0,0)]

        for row_i, row in enumerate(sessions):
            try:
                sid, dt, level, score, acc, rom, dur, pain = row
                def safe_float(v, default=0.0):
                    try: return float(v)
                    except (ValueError, TypeError): return default

                acc_val = safe_float(acc)
                rom_val = safe_float(rom)
                dur_val = safe_float(dur)
                pain_val = int(safe_float(pain))

                dt = dt or "Unknown"
                score = score or 0
                level = level or 1
                
                ry = table_y + 25 + row_i * 24
                if ry > WINDOW_HEIGHT - 60:
                    break
                # Alternating bg
                if row_i % 2 == 0:
                    pygame.draw.rect(self.screen, (15, 22, 40),
                                     pygame.Rect(table_x, ry - 2, sum(col_w), 22))
                acc_c  = (50,220,120) if acc_val >= 75 else (255,180,0) if acc_val >= 50 else (220,60,60)
                pain_c = pain_colors[min(pain_val, 10)]
                vals   = [str(sid), str(dt)[:16], str(level),
                          str(score), f"{acc_val:.0f}%", f"{rom_val:.0f}°",
                          f"{dur_val:.0f}s", str(pain_val)]
                cols_v = [(200,200,200),(180,180,180),(180,200,255),
                          (255,255,255), acc_c, (100,200,255),
                          (160,160,160), pain_c]
                x = table_x
                for v, vc, w in zip(vals, cols_v, col_w):
                    vs = self.font_hint.render(v, True, vc)
                    self.screen.blit(vs, (x, ry))
                    x += w
            except Exception as e:
                print(f"Error drawing history row {row}: {e}")

        # ── Right: Matplotlib Therapist Dashboard ──────────────────────
        chart_x = 600
        chart_y = 90
        chart_w = WINDOW_WIDTH - chart_x - 20
        chart_h = WINDOW_HEIGHT - 160

        pygame.draw.rect(self.screen, (12, 20, 40),
                         pygame.Rect(chart_x, chart_y, chart_w, chart_h), border_radius=8)
        pygame.draw.rect(self.screen, (0, 100, 160),
                         pygame.Rect(chart_x, chart_y, chart_w, chart_h), 2, border_radius=8)

        if getattr(self, "dashboard_surf", None):
            scaled_dash = pygame.transform.scale(self.dashboard_surf, (chart_w - 4, chart_h - 4))
            self.screen.blit(scaled_dash, (chart_x + 2, chart_y + 2))
        elif getattr(self, "dashboard_loading", False):
            # Pulsing loader text for high contrast and dynamic feedback (clamping values to 0-255)
            pulse = int(127 + 127 * math.sin(time.time() * 5))
            c_r = max(0, min(pulse, 255))
            c_g = max(0, min(pulse + 50, 255))
            c_b = max(0, min(pulse + 128, 255))
            no_data = self.font_medium.render("Generating Dashboard... Please wait.", True, (c_r, c_g, c_b))
            self.screen.blit(no_data, no_data.get_rect(
                center=(chart_x + chart_w//2, chart_y + chart_h//2)))
        else:
            no_data = self.font_medium.render("Awaiting Patient Data for Clinical Dashboard", True, (100, 120, 150))
            self.screen.blit(no_data, no_data.get_rect(
                center=(chart_x + chart_w//2, chart_y + chart_h//2)))
        
        # Display ML Progress Prediction below chart
        pred_pct = self.db.predict_recovery_progress(self.patient_name)
        if pred_pct < 0:
            pred_text = self.font_hud.render("Collecting more data...", True, (255, 200, 100))
        else:
            pred_text = self.font_hud.render(f"7-Day ML Prediction: {pred_pct:.1f}% Recovery", True, (255, 200, 100))
        self.screen.blit(pred_text, (chart_x + 20, chart_y + chart_h + 10))

        # CRT Static / Scanlines for History
        scan_y = int((time.time() * 150) % WINDOW_HEIGHT)
        pygame.draw.line(self.screen, (0, 255, 150, 30), (0, scan_y), (WINDOW_WIDTH, scan_y), 1)

        # Back instruction
        inst = self.font_small.render("Make a FIST for 1.5s to return to Main Menu", True, (120, 160, 200))
        self.screen.blit(inst, inst.get_rect(center=(cx, WINDOW_HEIGHT - 22)))

        # Cursor
        hand_data = self.hand_engine.get_hand_data()
        self.purge_button.draw(self.screen, self.font_tiny)
        self.history_back_button.draw(self.screen, self.font_tiny)
        self._draw_cursor(hand_data)

