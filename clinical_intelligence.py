"""
Clinical Intelligence & Rehabilitation Analytics Layer

Provides advanced clinical decision support by analyzing raw session data,
classifying recovery stages, detecting risks, and generating human-readable
insights and recommendations for therapists.
"""

import sqlite3
import security_utils
import math
from typing import Any, Dict, List
from datetime import datetime

class ClinicalIntelligenceLayer:
    def __init__(self, db_path: str = "rehab_data.db"):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _query(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(sql, params).fetchall()

    def _number(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def get_clinical_profile(self, patient_id: str) -> Dict[str, Any]:
        """Generates the full clinical profile for a patient."""
        enc_patient = security_utils.encrypt_deterministic(patient_id)
        sessions = self._query(
            "SELECT * FROM sessions WHERE patient_id = ? ORDER BY id DESC LIMIT 60",
            (enc_patient,)
        )
        upper_limb = self._query(
            "SELECT * FROM upper_limb_assessments WHERE patient_id = ? ORDER BY id DESC LIMIT 30",
            (enc_patient,)
        )
        
        if not sessions:
            return {
                "health_score": 0,
                "recovery_stage": "Unknown",
                "risk_level": "Unknown",
                "trend": "No Data",
                "insights": ["Not enough data to generate insights."],
                "recommendations": ["Conduct initial assessment session."],
                "detected_risks": []
            }

        # Reverse to chronological order for trend analysis
        chrono_sessions = list(reversed(sessions))
        chrono_upper_limb = list(reversed(upper_limb))

        health_score = self.calculate_health_score(chrono_sessions, chrono_upper_limb)
        stage = self.classify_stage(chrono_sessions)
        risks = self.detect_risks(chrono_sessions, chrono_upper_limb)
        trend = self.analyze_recovery(chrono_sessions)
        
        insights = self.generate_insights(chrono_sessions, chrono_upper_limb, trend)
        recommendations = self.generate_recommendations(risks, stage, trend, chrono_sessions)
        
        # Determine overall risk level
        risk_level = "Low"
        if len(risks) > 0:
            risk_level = "Moderate"
        if len(risks) >= 2 or "High Pain Risk" in risks or "Dropout Risk" in risks:
            risk_level = "High"

        return {
            "health_score": health_score,
            "recovery_stage": stage,
            "risk_level": risk_level,
            "trend": trend,
            "insights": insights,
            "recommendations": recommendations,
            "detected_risks": risks
        }

    def calculate_health_score(self, sessions: List[sqlite3.Row], upper_limb: List[sqlite3.Row]) -> int:
        """
        Calculates a 0-100 score based on ROM, Accuracy, Consistency, minus Pain/Compensation penalties.
        """
        if not sessions: return 0
        recent = sessions[-5:]
        
        avg_rom = sum(self._number(s["avg_hand_angle"]) for s in recent) / len(recent)
        avg_acc = sum(self._number(s["avg_accuracy"]) for s in recent) / len(recent)
        avg_pain = sum(self._number(s["pain_level"]) for s in recent) / len(recent)
        
        avg_comp = 0.0
        if upper_limb:
            recent_ul = upper_limb[-3:]
            avg_comp = sum(self._number(u["compensation_score"]) for u in recent_ul) / len(recent_ul)

        # Base score out of 100
        rom_score = min(100.0, (avg_rom / 90.0) * 100) * 0.5  # 50% weight
        acc_score = avg_acc * 0.5  # 50% weight
        
        base_score = rom_score + acc_score
        
        # Penalties
        pain_penalty = (avg_pain / 10.0) * 20.0  # Up to -20 points
        comp_penalty = avg_comp * 25.0           # Up to -25 points
        
        final_score = base_score - pain_penalty - comp_penalty
        return int(max(0, min(100, final_score)))

    def classify_stage(self, sessions: List[sqlite3.Row]) -> str:
        """Classifies the patient's recovery phase."""
        if not sessions: return "Unknown"
        
        recent_rom = sum(self._number(s["avg_hand_angle"]) for s in sessions[-3:]) / min(3, len(sessions))
        
        if recent_rom < 45.0:
            return "Early Recovery"
        elif recent_rom < 75.0:
            return "Intermediate Recovery"
        else:
            return "Advanced Recovery"

    def analyze_recovery(self, sessions: List[sqlite3.Row]) -> str:
        """Determines the overarching recovery trend."""
        if len(sessions) < 3:
            return "Stabilizing (Insufficient Data)"
            
        first_half = sessions[:max(1, len(sessions)//2)]
        second_half = sessions[max(1, len(sessions)//2):]
        
        rom_1 = sum(self._number(s["avg_hand_angle"]) for s in first_half) / len(first_half)
        rom_2 = sum(self._number(s["avg_hand_angle"]) for s in second_half) / len(second_half)
        
        if rom_2 > rom_1 + 5.0:
            return "Improving"
        elif rom_2 < rom_1 - 5.0:
            return "Declining"
        else:
            return "Stable"

    def detect_risks(self, sessions: List[sqlite3.Row], upper_limb: List[sqlite3.Row]) -> List[str]:
        """Detects clinical risks from session data."""
        risks = []
        if not sessions: return risks
        
        recent = sessions[-3:]
        
        # High Pain Risk
        avg_pain = sum(self._number(s["pain_level"]) for s in recent) / len(recent)
        if avg_pain >= 6.0:
            risks.append("High Pain Risk")
            
        # Overtraining Risk
        # (High session count + declining accuracy + high pain)
        if len(recent) == 3:
            acc_decline = self._number(recent[0]["avg_accuracy"]) > self._number(recent[-1]["avg_accuracy"]) + 10.0
            if acc_decline and avg_pain >= 4.0:
                risks.append("Overtraining Risk")
                
        # Dropout Risk
        try:
            last_date = datetime.fromisoformat(str(sessions[-1]["timestamp"]))
            days_since = (datetime.now() - last_date).days
            if days_since > 10:
                risks.append("Dropout Risk")
        except ValueError:
            pass
            
        # Compensation Dependency
        if upper_limb:
            recent_ul = upper_limb[-3:]
            avg_comp = sum(self._number(u["compensation_score"]) for u in recent_ul) / len(recent_ul)
            if avg_comp >= 0.40:
                risks.append("Compensation Dependency")
                
        return risks

    def generate_insights(self, sessions: List[sqlite3.Row], upper_limb: List[sqlite3.Row], trend: str) -> List[str]:
        """Generates natural language insights based on data."""
        insights = []
        if len(sessions) >= 2:
            first_rom = self._number(sessions[0]["avg_hand_angle"])
            last_rom = self._number(sessions[-1]["avg_hand_angle"])
            rom_change = last_rom - first_rom
            
            if rom_change > 0:
                insights.append(f"ROM has improved by {rom_change:.1f}° since beginning therapy.")
            elif rom_change < 0:
                insights.append(f"ROM has decreased by {abs(rom_change):.1f}° since beginning therapy.")
                
            acc_change = self._number(sessions[-1]["avg_accuracy"]) - self._number(sessions[0]["avg_accuracy"])
            if acc_change > 0:
                insights.append(f"Task accuracy is trending upwards (+{acc_change:.1f}%).")
                
        if upper_limb:
            comp_score = self._number(upper_limb[-1]["compensation_score"])
            if comp_score > 0.3:
                insights.append(f"High level of compensatory movement detected in upper limb ({(comp_score*100):.0f}%).")
            else:
                insights.append("Upper limb posture is stable with minimal compensation.")
                
        if not insights:
            insights.append("Continuous monitoring is active. More data needed for deeper insights.")
            
        return insights

    def generate_recommendations(self, risks: List[str], stage: str, trend: str, sessions: List[sqlite3.Row]) -> List[str]:
        """Suggests actionable advice for the therapist."""
        recs = []
        
        if "High Pain Risk" in risks:
            recs.append("Reduce exercise difficulty and frequency. Assess patient for inflammation.")
        if "Overtraining Risk" in risks:
            recs.append("Increase rest periods. Patient shows signs of fatigue affecting accuracy.")
        if "Dropout Risk" in risks:
            recs.append("Patient hasn't completed a session in over 10 days. Follow up to encourage adherence.")
        if "Compensation Dependency" in risks:
            recs.append("Focus heavily on movement quality. Recommend postural correction exercises before progressing ROM.")
            
        if trend == "Declining" and "High Pain Risk" not in risks:
            recs.append("Review exercise execution. Decline in performance may require regressing to easier tiers.")
            
        if stage == "Early Recovery":
            recs.append("Prioritize gentle, pain-free ROM expansion. Keep repetitions low.")
        elif stage == "Advanced Recovery" and trend == "Improving":
            recs.append("Patient is ready for complex coordination tasks and resistance/strength training.")
            
        if not recs:
            recs.append("Maintain current rehabilitation plan. Progress is steady.")
            
        return recs
