"""ClinicalMixin implementation for PhysioSystem."""

from .shared import *


class ClinicalMixin:
    def _end_level(self):
        try:
            pending_summary = getattr(self, "_pending_session_summary", None)
            if pending_summary is None:
                duration = time.time() - self.session_start
                avg_accuracy = (self.accuracy_hits / self.accuracy_attempts * 100) if self.accuracy_attempts > 0 else 0
                avg_hand_angle = sum(self.angle_history) / len(self.angle_history) if len(self.angle_history) > 0 else 0
                self._pending_session_summary = {
                    "duration": duration,
                    "avg_accuracy": avg_accuracy,
                    "avg_hand_angle": avg_hand_angle,
                    "score": self.score,
                    "max_extension": self.max_extension,
                    "reach_distance": self.reach_distance,
                    "accuracy_hits": self.accuracy_hits,
                    "accuracy_attempts": self.accuracy_attempts,
                    "angle_history": list(self.angle_history),
                    "pain_before_session": int(getattr(self, "pain_before_session", self.pain_level)),
                }
                self.pain_after_session = int(getattr(self, "pain_before_session", self.pain_level))
                self.state = GameState.PAIN_AFTER_SESSION
                VOICE.speak("Please rate your pain level after completing today's exercises.")
                return

            duration = pending_summary["duration"]
            avg_accuracy = pending_summary["avg_accuracy"]
            avg_hand_angle = pending_summary["avg_hand_angle"]
            self.score = pending_summary["score"]
            self.max_extension = pending_summary["max_extension"]
            self.reach_distance = pending_summary["reach_distance"]
            pain_before_session = int(pending_summary.get("pain_before_session", self.pain_level))
            pain_after_session = int(getattr(self, "pain_after_session", pain_before_session))
            pain_difference = pain_after_session - pain_before_session
            movement_smoothness = 0.7
            if isinstance(getattr(self, "forearm_assessment", None), dict):
                movement_smoothness = float(self.forearm_assessment.get("smoothness", 0.7))
            recovery_score_value = functional_recovery_score(
                avg_hand_angle,
                avg_accuracy,
                pain_after_session,
                1.0,
                movement_smoothness,
            )
            recovery_category_value = recovery_category(recovery_score_value)
            self.pain_before_session = pain_before_session
            self.pain_after_session = pain_after_session
            self.pain_difference = pain_difference
            self.functional_recovery_score = recovery_score_value
            self.recovery_category = recovery_category_value

            qm_metrics = self.quality_tracker.calculate_metrics(self.calibrated_max_angle)
            movement_quality_score = qm_metrics["overall"]
            sub_smoothness = qm_metrics["smoothness"]
            sub_accuracy = qm_metrics["accuracy"]
            sub_rom = qm_metrics["rom"]
            sub_stability = qm_metrics["stability"]

            self.db.save_session(
                self.current_level, self.score, duration,
                avg_accuracy, self.max_extension,
                self.reach_distance, avg_hand_angle,
                pain_level=pain_before_session, patient_id=self.patient_name,
                pain_before_session=pain_before_session,
                pain_after_session=pain_after_session,
                functional_recovery_score=recovery_score_value,
                recovery_category=recovery_category_value,
                movement_smoothness=movement_smoothness,
                movement_quality_score=movement_quality_score,
                sub_smoothness=sub_smoothness,
                sub_accuracy=sub_accuracy,
                sub_rom=sub_rom,
                sub_stability=sub_stability,
            )
            session_id = getattr(self.db, 'last_session_id', None)
            
            # Generate and securely store clinical summary
            self._generate_and_save_clinical_summary(
                session_id, duration, avg_accuracy, avg_hand_angle,
                pain_before_session, pain_after_session, recovery_score_value,
                qm_metrics
            )

            rotation_smoothness = 0.7
            if isinstance(getattr(self, 'forearm_assessment', None), dict):
                rotation_smoothness = float(self.forearm_assessment.get('smoothness', 0.7))
                try:
                    self.forearm_classifier.save_assessment(
                        self.db.db_path,
                        self.patient_name or "Unknown",
                        self.current_level,
                        self.forearm_assessment,
                        session_id=session_id,
                    )
                except Exception as exc:
                    print(f"Forearm assessment save failed: {exc}")

            movement_quality = movement_quality_score / 100.0
            fatigue_index = 0.0
            if duration > 0 and self.accuracy_attempts > 0:
                fatigue_index = min(1.0, max(0.0, (duration / max(getattr(self, 'session_time_limit', LEVEL_DURATION), 1.0) - 1.0) * 0.5))
            if self.pain_level >= 6:
                fatigue_index = max(fatigue_index, min(1.0, self.pain_level / 10.0))

            try:
                recovery_prediction = self._get_recovery_prediction()
                next_prescription = self.adaptive_engine.recommend(
                    self.patient_name or "Unknown",
                    self.current_level,
                    avg_accuracy,
                    avg_hand_angle,
                    self.pain_level,
                    duration,
                    self.score,
                    movement_quality=movement_quality,
                    fatigue_index=fatigue_index,
                    rotation_smoothness=rotation_smoothness,
                    session_id=session_id,
                    recovery_prediction=recovery_prediction,
                    functional_recovery_score=recovery_score_value,
                )
                self.adaptive_recommendation = next_prescription
                sensei_message = self.adaptive_engine.coaching_message(
                    self.patient_name or "Unknown",
                    self.current_level,
                    next_prescription,
                    avg_accuracy,
                    avg_hand_angle,
                    self.pain_level,
                    fatigue_index=fatigue_index,
                    recovery_prediction=recovery_prediction,
                    session_id=session_id,
                )
                self.adaptive_sensei_message = sensei_message
                VOICE.speak(sensei_message)
            except Exception as exc:
                print(f"Adaptive recommendation failed: {exc}")

            self.session_data = self.db.get_last_session()
            if not self.session_data:
                self.session_data = {
                    'level': self.current_level,
                    'score': self.score,
                    'duration': duration,
                    'avg_accuracy': avg_accuracy,
                    'max_extension': self.max_extension,
                    'reach_distance': self.reach_distance,
                    'avg_hand_angle': avg_hand_angle
                }
            if self.session_data:
                self.session_data['summary_text'] = self.current_clinical_summary
                self.session_data['ai_recommendation'] = self.current_clinical_recommendation
            self.best_data    = self.db.get_all_time_best()
            
            # Generate Session Charts (Pie/Histogram)
            self.summary_screen.generate_session_charts(
                self.accuracy_hits, self.accuracy_attempts, list(self.angle_history)
            )

            # Auto-save text, HTML, and PDF reports
            try:
                import os
                os.makedirs("reports", exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                sd = self.session_data or {}
                
                # 1. Text Report Card
                fname = f"reports/report_L{self.current_level}_{ts}.txt"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(f"AI Hand Rehabilitation — Session Report\n")
                    f.write(f"{'='*45}\n")
                    f.write(f"Patient  : {self.patient_name or 'Unknown'}\n")
                    f.write(f"Date     : {datetime.now().strftime('%d %B %Y  %H:%M')}\n")
                    f.write(f"Level    : {self.current_level}\n")
                    f.write(f"Pain Before: {pain_before_session}/10\n")
                    f.write(f"Pain After : {pain_after_session}/10\n")
                    f.write(f"Pain Change: {pain_difference:+d}\n")
                    f.write(f"Recovery Score: {recovery_score_value:.1f}/100 ({recovery_category_value})\n")
                    f.write(f"Movement Quality: {movement_quality_score:.1f}% ({qm_metrics['rating']})\n")
                    f.write(f"  - Smoothness: {sub_smoothness:.1f}%\n")
                    f.write(f"  - Accuracy: {sub_accuracy:.1f}%\n")
                    f.write(f"  - Range of Motion: {sub_rom:.1f}%\n")
                    f.write(f"  - Stability: {sub_stability:.1f}%\n")
                    f.write(f"\n-- Clinical Summary & Recommendation --\n")
                    f.write(f"Summary: {self.current_clinical_summary}\n")
                    f.write(f"Recommendation: {self.current_clinical_recommendation}\n")
                    f.write(f"\n-- Performance --\n")
                    f.write(f"Score    : {sd.get('score', self.score)}\n")
                    f.write(f"Accuracy : {sd.get('avg_accuracy', 0):.1f}%\n")
                    f.write(f"ROM Angle: {sd.get('avg_hand_angle', 0):.1f}°\n")
                    f.write(f"Duration : {sd.get('duration', 0):.0f}s\n")
                    f.write(f"\n-- All-Time Best --\n")
                    bd = self.best_data or {}
                    f.write(f"Best Score   : {bd.get('score', 0)}\n")
                    f.write(f"Best Accuracy: {bd.get('accuracy', 0):.1f}%\n")
                    f.write(f"Best ROM     : {bd.get('angle', 0):.1f}°\n")
                print(f"Text Report saved: {fname}")

                # 2. Premium Clinical HTML Report Card
                html_fname = f"reports/session_report_L{self.current_level}_{ts}.html"
                
                LEVEL_NAMES = [
                    "Flexibility - Pop the Bubbles",
                    "Flexibility - Pop the Bubbles", 
                    "Strength & Speed - Catch the Apples", 
                    "Fine Motor - Plant the Seeds", 
                    "Coordination - Trace the Path", 
                    "Grip & Release - Balloon Pump", 
                    "Cognitive Precision - Simon Pattern Tap"
                ]
                level_name_str = LEVEL_NAMES[self.current_level] if self.current_level < len(LEVEL_NAMES) else "Therapeutic Training"
                
                acc_val = sd.get('avg_accuracy', 0)
                rom_val = sd.get('avg_hand_angle', 0)
                dur_val = sd.get('duration', 0)
                
                suggestions_list = []
                if acc_val >= 85:
                    suggestions_list.append("Patient demonstrated exceptional target accuracy. Recommend advancing to the next difficulty tier or level.")
                elif acc_val >= 60:
                    suggestions_list.append("Good neuromuscular accuracy. Continue with the current protocol to build muscle memory and control.")
                else:
                    suggestions_list.append("Target accuracy is low. Encourage slower, more deliberate hand movements. Consider a pediatric or senior mode to expand target radii.")

                if rom_val >= 45:
                    suggestions_list.append("Average finger flexion is excellent, showing deep range of motion. Joint flexibility is healthy.")
                else:
                    suggestions_list.append("Reduced range of motion (ROM) detected. Incorporate warm-up finger stretching exercises before sessions.")

                if self.pain_level >= 5:
                    suggestions_list.append("WARNING: High patient pain level reported. Shorten session duration, encourage regular pauses, and consult with the attending therapist.")
                else:
                    suggestions_list.append("Patient reported minimal pain during this session. Good tolerability of the motor exercises.")
                
                suggestions_html = "\n".join([f"<li>{s}</li>" for s in suggestions_list])
                
                html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Therapy Session Report - L{self.current_level}</title>
    <style>
        :root {{
            --bg-color: #080c16;
            --card-bg: rgba(13, 22, 42, 0.7);
            --border-color: rgba(0, 255, 204, 0.2);
            --accent-glow: #00ffcc;
            --accent-blue: #0088ff;
            --text-primary: #ffffff;
            --text-secondary: #8fa0c0;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .report-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 40px;
            width: 100%;
            max-width: 800px;
            box-shadow: 0 8px 32px 0 rgba(0, 255, 204, 0.08);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            position: relative;
            overflow: hidden;
        }}
        .report-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-glow));
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(143, 160, 192, 0.15);
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 26px;
            font-weight: 700;
            letter-spacing: 1px;
            background: linear-gradient(90deg, #ffffff, var(--accent-glow));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header-meta {{
            text-align: right;
            color: var(--text-secondary);
            font-size: 14px;
        }}
        .patient-info {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .info-item {{
            display: flex;
            flex-direction: column;
        }}
        .info-label {{
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }}
        .info-value {{
            font-size: 18px;
            font-weight: 600;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 25px;
            margin-bottom: 35px;
        }}
        .metric-card {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 25px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .metric-details h3 {{
            margin: 0 0 5px 0;
            font-size: 14px;
            color: var(--text-secondary);
            text-transform: uppercase;
        }}
        .metric-details .value {{
            font-size: 28px;
            font-weight: 700;
            color: var(--accent-glow);
        }}
        .radial-indicator {{
            position: relative;
            width: 70px;
            height: 70px;
            border-radius: 50%;
            background: conic-gradient(var(--accent-glow) {acc_val}%, rgba(255, 255, 255, 0.08) 0);
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .radial-indicator::after {{
            content: '{acc_val:.1f}%';
            position: absolute;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: #0d162a;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            font-weight: 600;
        }}
        .clinical-suggestions {{
            background: rgba(0, 255, 204, 0.04);
            border: 1px dashed var(--border-color);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
        }}
        .clinical-suggestions h2 {{
            margin-top: 0;
            font-size: 18px;
            color: var(--accent-glow);
            letter-spacing: 0.5px;
        }}
        .clinical-suggestions ul {{
            margin: 0;
            padding-left: 20px;
            color: var(--text-secondary);
            line-height: 1.6;
        }}
        .clinical-suggestions li {{
            margin-bottom: 8px;
        }}
        .footer {{
            text-align: center;
            color: var(--text-secondary);
            font-size: 12px;
            border-top: 1px solid rgba(143, 160, 192, 0.15);
            padding-top: 20px;
        }}
        @media print {{
            body {{
                background: #fff;
                color: #000;
                padding: 0;
            }}
            .report-card {{
                border: none;
                box-shadow: none;
                background: none;
                padding: 0;
                backdrop-filter: none;
            }}
            .report-card::before {{
                display: none;
            }}
            .metric-card, .patient-info {{
                border: 1px solid #ddd;
                background: #fff;
                color: #000;
            }}
            .metric-details .value {{
                color: #000;
            }}
            .radial-indicator::after {{
                background: #fff;
                color: #000;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-card">
        <div class="header">
            <div>
                <h1>CLINICAL THERAPY REPORT</h1>
                <span style="color: var(--accent-glow); font-size: 12px; letter-spacing: 2px;">NEURAL BIO-FEEDBACK SUITE</span>
            </div>
            <div class="header-meta">
                <div>SESSION TIMESTAMP</div>
                <div>{datetime.now().strftime('%d %B %Y %H:%M')}</div>
            </div>
        </div>

        <div class="patient-info">
            <div class="info-item">
                <span class="info-label">Patient Name</span>
                <span class="info-value">{self.patient_name or 'Unknown'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Demographic</span>
                <span class="info-value">{self.age_group.value if self.age_group else 'Adult'} (Age {self.patient_age or '30'})</span>
            </div>
            <div class="info-item">
                <span class="info-label">Therapy Protocol</span>
                <span class="info-value">Level {self.current_level} - {level_name_str}</span>
            </div>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Performance Score</h3>
                    <div class="value">{sd.get('score', self.score)}</div>
                </div>
                <div style="font-size: 24px;">🏆</div>
            </div>
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Target Accuracy</h3>
                    <div class="value">{acc_val:.1f}%</div>
                </div>
                <div class="radial-indicator"></div>
            </div>
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Range of Motion (ROM)</h3>
                    <div class="value">{rom_val:.1f}°</div>
                </div>
                <div style="font-size: 24px; color: var(--accent-glow);">📐</div>
            </div>
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Pain Before / After</h3>
                    <div class="value">{pain_before_session}/10 to {pain_after_session}/10 <span style="font-size: 16px; font-weight: normal; color: var(--text-secondary);">({pain_difference:+d})</span></div>
                </div>
                <div style="font-size: 24px;">⚡</div>
            </div>
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Movement Quality</h3>
                    <div class="value">{movement_quality_score:.1f}%</div>
                    <div style="font-size: 11px; color: var(--text-secondary); line-height: 1.4; margin-top: 4px;">
                        Smoothness: {sub_smoothness:.1f}% | ROM: {sub_rom:.1f}%<br>
                        Accuracy: {sub_accuracy:.1f}% | Stability: {sub_stability:.1f}%
                    </div>
                </div>
                <div style="font-size: 24px; color: var(--accent-glow);">⭐</div>
            </div>
        </div>

        <div class="clinical-suggestions">
            <h2>CLINICAL OBSERVATIONS & SUGGESTIONS</h2>
            <ul>
                {suggestions_html}
            </ul>
        </div>

        <div class="clinical-suggestions" style="background: rgba(0, 136, 255, 0.04); border-color: rgba(0, 136, 255, 0.2);">
            <h2>AI CLINICAL SUMMARY</h2>
            <p style="color: var(--text-secondary); line-height: 1.6; margin-bottom: 15px;">{self.current_clinical_summary}</p>
            <h2 style="color: var(--accent-blue);">THERAPEUTIC RECOMMENDATION</h2>
            <p style="color: var(--text-primary); font-weight: 600; margin: 0;">{self.current_clinical_recommendation}</p>
        </div>

        <div class="footer">
            Generated by Zero-Keyboard AI Hand Rehabilitation System | Confidential Medical Record
        </div>
    </div>
</body>
</html>"""
                with open(html_fname, "w", encoding="utf-8") as f:
                    f.write(html_template)
                print(f"HTML Report saved: {html_fname}")
                VOICE.speak("Clinical report exported to reports folder.")
                
                # 3. PDF Generation (with fixed imports and variables)
                try:
                    from reportlab.pdfgen import canvas
                    from reportlab.lib.pagesizes import letter
                    pdf_fname = f"reports/report_L{self.current_level}_{ts}.pdf"
                    c = canvas.Canvas(pdf_fname, pagesize=letter)
                    c.setFont("Helvetica-Bold", 24)
                    c.setFillColorRGB(0, 0.4, 0.6)
                    c.drawString(50, 750, "AI Hand Rehabilitation - Clinical Report")
                    
                    c.setFont("Helvetica", 12)
                    c.setFillColorRGB(0, 0, 0)
                    c.drawString(50, 710, f"Patient Name: {self.patient_name or 'Unknown'}")
                    c.drawString(50, 690, f"Date: {datetime.now().strftime('%d %B %Y  %H:%M')}")
                    c.drawString(50, 670, f"Diagnostic Level: {self.current_level}")
                    c.drawString(50, 650, f"Pain Before Session: {pain_before_session}/10")
                    c.drawString(50, 632, f"Pain After Session: {pain_after_session}/10")
                    c.drawString(50, 614, f"Pain Difference: {pain_difference:+d}")
                    
                    c.setFont("Helvetica-Bold", 16)
                    c.setFillColorRGB(0, 0.3, 0.5)
                    c.drawString(50, 585, "Session Telemetry")
                    
                    c.setFont("Helvetica", 12)
                    c.setFillColorRGB(0, 0, 0)
                    c.drawString(50, 565, f"Final Score: {sd.get('score', self.score)}")
                    c.drawString(50, 545, f"Target Accuracy: {acc_val:.1f}%")
                    c.drawString(50, 525, f"Average Range of Motion: {rom_val:.1f} degrees")
                    c.drawString(50, 505, f"Therapy Duration: {dur_val:.0f} seconds")
                    c.drawString(50, 485, f"Functional Recovery Score: {recovery_score_value:.1f}/100 ({recovery_category_value})")
                    c.drawString(50, 465, f"Movement Quality Score: {movement_quality_score:.1f}% ({qm_metrics['rating']})")
                    c.setFont("Helvetica-Oblique", 10)
                    c.drawString(70, 448, f"Smoothness: {sub_smoothness:.1f}% | Hold Stability: {sub_stability:.1f}% | Accuracy: {sub_accuracy:.1f}% | ROM: {sub_rom:.1f}%")
                    
                    c.setFont("Helvetica-Bold", 14)
                    c.setFillColorRGB(0, 0.3, 0.5)
                    c.drawString(50, 420, "AI Clinical Summary & Recommendation")
                    
                    c.setFont("Helvetica-Oblique", 11)
                    c.setFillColorRGB(0.15, 0.15, 0.15)
                    summary_lines = []
                    words = self.current_clinical_summary.split()
                    line = ""
                    for w in words:
                        test_line = line + w + " "
                        if len(test_line) > 85:
                            summary_lines.append(line)
                            line = w + " "
                        else:
                            line = test_line
                    if line:
                        summary_lines.append(line)
                        
                    curr_y = 402
                    for sl in summary_lines:
                        c.drawString(50, curr_y, sl)
                        curr_y -= 15
                        
                    curr_y -= 5
                    c.setFont("Helvetica-Bold", 11)
                    c.setFillColorRGB(0.1, 0.5, 0.3)
                    c.drawString(50, curr_y, "Therapeutic Recommendation:")
                    curr_y -= 15
                    c.setFont("Helvetica", 11)
                    c.setFillColorRGB(0, 0, 0)
                    
                    rec_lines = []
                    words = self.current_clinical_recommendation.split()
                    line = ""
                    for w in words:
                        test_line = line + w + " "
                        if len(test_line) > 85:
                            rec_lines.append(line)
                            line = w + " "
                        else:
                            line = test_line
                    if line:
                        rec_lines.append(line)
                        
                    for rl in rec_lines:
                        c.drawString(50, curr_y, rl)
                        curr_y -= 15
                    
                    c.save()
                    print(f"PDF Report saved: {pdf_fname}")
                except Exception as pdf_e:
                    print(f"PDF save warning: {pdf_e}")
                    
            except Exception as re:
                print(f"Report save warning: {re}")

            # Big celebration burst

            cx = GAME_AREA_WIDTH // 2
            for _ in range(5):
                self.particles.emit(cx + random.randint(-200, 200),
                                    WINDOW_HEIGHT // 2,
                                    random.choice([(255,215,0),(0,220,120),(0,200,255),(255,100,150)]),
                                    30)

            # Go to LEVEL_COMPLETE celebration screen first
            self._pending_session_summary = None
            self._level_complete_time = time.time()
            self.state = GameState.LEVEL_COMPLETE
            self.sounds.play('level_complete')
            self.screen_shake = 25

        except Exception as e:
            print(f"Error in _end_level: {e}")
            self.state = GameState.MAIN_MENU
            self._reset_game()

    def _generate_and_save_clinical_summary(self, session_id, duration, avg_accuracy, avg_hand_angle, pain_before, pain_after, recovery_score, qm_metrics):
        try:
            # Gather compensation events
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT compensation_type, severity FROM compensation_events WHERE session_id = ?", (session_id,))
            comp_rows = cursor.fetchall()
            conn.close()
            
            comp_summary = ""
            if comp_rows:
                comp_counts = {}
                for r in comp_rows:
                    comp_counts[r[0]] = comp_counts.get(r[0], 0) + 1
                comp_summary = " Compensations: " + ", ".join([f"{k} (x{v})" for k, v in comp_counts.items()]) + "."
            else:
                comp_summary = " No significant compensation detected."
                
            pain_delta = pain_after - pain_before
            pain_text = f"Pain was stable at {pain_after}/10." if pain_delta == 0 else (
                f"Pain increased by {pain_delta} to {pain_after}/10." if pain_delta > 0 else
                f"Pain decreased by {abs(pain_delta)} to {pain_after}/10."
            )
            
            summary_text = (
                f"Completed Level {self.current_level} in {duration:.1f}s. "
                f"Movement Quality was {qm_metrics['overall']:.1f}% ({qm_metrics['rating']}), "
                f"featuring {qm_metrics['smoothness']:.1f}% smoothness, {qm_metrics['stability']:.1f}% hold stability. "
                f"Average joint flexion reached {avg_hand_angle:.1f}° with {avg_accuracy:.1f}% target hit accuracy."
                f"{comp_summary} {pain_text} Functional Recovery Score: {recovery_score:.1f}%."
            )
            
            # Formulate AI Recommendation
            if qm_metrics['overall'] >= 85 and pain_after <= 3:
                ai_rec = f"Increase difficulty. Patient displays high compliance and stable joint control. Recommend advancing to Level {min(8, self.current_level + 1)}."
            elif pain_after >= 6:
                ai_rec = "Reduce intensity. Elevated pain scores detected. Incorporate warm-up stretches and longer pause intervals."
            else:
                ai_rec = "Maintain current training pace. Continue tracking range of motion and focus on smoothness to reduce compensatory patterns."
                
            # Encrypt securely using non-deterministic encryption
            enc_summary = security_utils.encrypt_non_deterministic(summary_text)
            enc_rec = security_utils.encrypt_non_deterministic(ai_rec)
            
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO clinical_summaries (session_id, summary_text, ai_recommendation)
                VALUES (?, ?, ?)
            """, (session_id, enc_summary, enc_rec))
            conn.commit()
            conn.close()
            
            self.current_clinical_summary = summary_text
            self.current_clinical_recommendation = ai_rec
            print("[SUCCESS] Clinical summary generated and stored securely.")
        except Exception as e:
            print(f"Error generating clinical summary: {e}")
            self.current_clinical_summary = "Report summary telemetry compilation in progress."
            self.current_clinical_recommendation = "Maintain standard recovery protocol."

    def _run_clinical_analysis(self, hand_data):
        gameplay_states = [
            GameState.LEVEL1_FLEXIBILITY,
            GameState.LEVEL2_STRENGTH,
            GameState.LEVEL3_FINEMOTOR,
            GameState.LEVEL4_COORDINATION,
            GameState.LEVEL5_GRIP_RELEASE,
            GameState.LEVEL6_FINGER_TAPS,
            GameState.LEVEL7_WRIST_MECHANICS,
            GameState.LEVEL8_SMART_ASSEMBLY
        ]
        if self.state in gameplay_states and hand_data and hand_data.index_tip is not None:
            active_hold = False
            if self.state == GameState.LEVEL3_FINEMOTOR and hand_data.is_pinching:
                active_hold = True
            elif self.state == GameState.LEVEL5_GRIP_RELEASE and hand_data.is_fist:
                active_hold = True
            elif self.state == GameState.LEVEL7_WRIST_MECHANICS and hasattr(self, 'hold_timer') and getattr(self, 'hold_timer', 0) > 0:
                active_hold = True
                
            self.quality_tracker.update(hand_data, is_active_session=True, active_hold=active_hold)
            self.quality_tracker.record_accuracy(self.accuracy_hits, self.accuracy_attempts)
            
            # Analyze compensation
            detected, comp_type, desc, severity = self.compensation_detector.analyze(hand_data, self.current_level)
            if detected:
                self.sounds.play('select')
                self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2 - 100, WINDOW_HEIGHT // 2, "COMPENSATION DETECTED!", (255, 50, 50)))
                session_id = getattr(self.db, 'last_session_id', None)
                try:
                    conn = sqlite3.connect(self.db.db_path)
                    cursor = conn.cursor()
                    enc_patient = security_utils.encrypt_deterministic(self.patient_name or "Unknown")
                    cursor.execute("""
                        INSERT INTO compensation_events (patient_id, session_id, exercise, compensation_type, severity)
                        VALUES (?, ?, ?, ?, ?)
                    """, (enc_patient, session_id, LEVEL_DISPLAY_NAMES.get(self.current_level, "Unknown"), comp_type, severity))
                    conn.commit()
                    conn.close()
                except Exception as exc:
                    print(f"Failed to log compensation event: {exc}")

    def _update_readiness_and_difficulty(self):
        if not self.patient_name:
            self.readiness_score = 50.0
            self.recommended_difficulty = "Moderate"
            self.recommended_difficulty_explanation = "Ready for baseline therapy."
            return
            
        try:
            enc_name = security_utils.encrypt_deterministic(self.patient_name)
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT avg_accuracy, avg_hand_angle, pain_after_session, movement_quality_score, duration
                FROM sessions WHERE patient_id = ? ORDER BY id DESC LIMIT 5
            """, (enc_name,))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                self.readiness_score = 65.0
                self.recommended_difficulty = "Moderate"
                self.recommended_difficulty_explanation = "Initial baseline. Calibrated ROM will adjust game scale."
                return
                
            avg_acc = sum(r[0] for r in rows) / len(rows)
            avg_rom = sum(r[1] for r in rows) / len(rows)
            avg_pain = sum(r[2] for r in rows) / len(rows)
            avg_mq = sum(r[3] for r in rows) / len(rows) * 100.0 if rows[0][3] is not None else 75.0
            avg_dur = sum(r[4] for r in rows) / len(rows)
            
            fatigue = min(100.0, max(0.0, (avg_dur / 45.0) * 20.0 + avg_pain * 5.0))
            
            rom_factor = min(100.0, (avg_rom / 90.0) * 100.0)
            acc_factor = avg_acc
            mq_factor = avg_mq
            pain_penalty = avg_pain * 8.0
            fatigue_penalty = fatigue * 0.4
            
            readiness = (rom_factor * 0.4 + acc_factor * 0.3 + mq_factor * 0.3) - pain_penalty - fatigue_penalty
            readiness = max(10.0, min(100.0, readiness))
            self.readiness_score = round(readiness, 1)
            
            if readiness >= 80.0:
                self.recommended_difficulty = "Hard"
                self.recommended_difficulty_explanation = f"Patient shows excellent coordination ({avg_acc:.0f}% accuracy) and high ROM ({avg_rom:.0f}°) with low pain ({avg_pain:.1f}/10). Recommended to increase challenge."
            elif readiness >= 50.0:
                self.recommended_difficulty = "Moderate"
                self.recommended_difficulty_explanation = f"Patient is stable with moderate ROM ({avg_rom:.0f}°) and tolerable pain ({avg_pain:.1f}/10). Recommended to maintain current difficulty pace."
            else:
                self.recommended_difficulty = "Easy"
                self.recommended_difficulty_explanation = f"Low readiness ({readiness:.1f}) detected due to high pain ({avg_pain:.1f}/10) or limited movement quality. Recommended easy setting for clinical safety."
                
        except Exception as e:
            print(f"Error calculating readiness: {e}")
            self.readiness_score = 55.0
            self.recommended_difficulty = "Moderate"
            self.recommended_difficulty_explanation = "Maintained moderate baseline due to telemetry calculation fallback."


    
    def _run_virtual_sensei(self, hand_data: HandData):
        """AI-driven therapeutic coaching"""
        if self.state not in [GameState.LEVEL1_FLEXIBILITY, GameState.LEVEL2_STRENGTH, GameState.LEVEL3_FINEMOTOR, GameState.LEVEL4_COORDINATION, GameState.LEVEL5_GRIP_RELEASE, GameState.LEVEL6_FINGER_TAPS]:
            return
            
        now = time.time()
        if now - self.last_coach_time < self.coaching_cooldown:
            return
            
        # 1. Performance Feedback
        accuracy = (self.accuracy_hits / self.accuracy_attempts * 100) if self.accuracy_attempts > 0 else 100
        
        # Check for poor ROM
        if hand_data.finger_extension > 0 and hand_data.finger_extension < 120:
            VOICE.speak("Try to open your hand fully to improve range of motion.")
            self.last_coach_time = now
            return

        # Check for poor accuracy
        if self.accuracy_attempts > 10 and accuracy < 50:
            VOICE.speak("Slow down and focus on the center of the targets.")
            self.last_coach_time = now
            return

        # Check for great performance (encouragement)
        if self.combo > 8:
            VOICE.speak("Excellent control! Your motor precision is improving.")
            self.last_coach_time = now
            return

        # Check for steady progress
        if now - self.session_start > 20:
            VOICE.speak("Stay focused. You are doing a great job today.")
            self.last_coach_time = now


