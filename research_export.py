"""
Research Dataset Exporter for AI Hand Rehabilitation System
Extracts authentic session metrics directly from SQLite database into research_dataset.csv.
"""

import os
import sqlite3
import argparse
import csv
from typing import Optional, Dict, Any, List
import security_utils

DEFAULT_DB_PATH = "rehab_data.db"
DEFAULT_OUTPUT_CSV = "research_dataset.csv"

EXERCISE_NAMES = {
    1: "Bubble Pop",
    2: "Fruit Catch",
    3: "Pinch & Drop",
    4: "Path Tracing",
    5: "Grip & Release",
    6: "Memory Sequence",
    7: "Rotation Orbit",
    8: "Smart Assembly",
    9: "Precision Dots",
    10: "Precision Pathway",
    11: "Coin Vault",
    12: "Card Shift Challenge",
    13: "Finger Isolation",
    14: "Wrist Flexion-Extension Control"
}

ACCURACY_TYPES = {
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

CSV_HEADERS = [
    "Patient_ID",
    "Session_ID",
    "Date",
    "Exercise",
    "Level",
    "Difficulty",
    "Accuracy_Type",
    "Successful_Hits",
    "Total_Attempts",
    "Accuracy",
    "Tracking_Quality",
    "ROM",
    "Movement_Quality",
    "Smoothness",
    "Compensation_Events",
    "Pain_Before",
    "Pain_After",
    "Pain_Delta",
    "Completion_Time",
    "Active_Engagement_Time",
    "Tracking_Valid_Time",
    "Readiness",
    "Target_Scale",
    "Speed_Scale",
    "Session_Time_Limit",
    "Hold_Duration",
    "Rotation_Tolerance",
    "Assembly_Tolerance",
    "Corridor_Width",
    "Successful_Pickups",
    "Pickup_Attempts",
    "Successful_Translations",
    "Translation_Attempts",
    "Successful_Placements",
    "Placement_Attempts",
    "Unintended_Drops",
    "Manipulation_Time_Avg",
    "Placement_Time_Avg",
    "Correction_Count",
    "D2_Contacts",
    "D3_Contacts",
    "D4_Contacts",
    "D5_Contacts",
    "Opposition_Latency_Avg",
    "Index_Successes",
    "Middle_Successes",
    "Ring_Successes",
    "Pinky_Successes",
    "Index_Attempts",
    "Middle_Attempts",
    "Ring_Attempts",
    "Pinky_Attempts",
    "Unintended_Movement_Events",
    "Target_Activation_Time_Avg",
    "Dwell_Success_Count",
    "Dwell_Failure_Count",
    "Movement_Time",
    "Target_Error",
    "Overshoot",
    "Hold_Stability",
    "Direction_Accuracy",
    "Card_Shift_Successes",
    "Card_Shift_Attempts",
    "Average_Shift_Latency",
    "Median_Shift_Latency",
    "Maximum_Shift_Latency",
    "Incorrect_Finger_Events",
    "Target_Timeouts",
    "Sequence_Completion_Rate",
    "Previous_Accuracy",
    "Previous_Readiness",
    "Previous_Difficulty",
    "New_Difficulty",
    "Session_Aborted",
    "Quality_Flag"
]


def export_research_dataset(
    db_path: str = DEFAULT_DB_PATH,
    output_csv: str = DEFAULT_OUTPUT_CSV,
    pseudonymize: bool = True,
    valid_only: bool = False
) -> int:
    """
    Exports authentic clinical/research sessions from SQLite into research_dataset.csv.
    
    Args:
        db_path: Path to rehab_data.db
        output_csv: Output CSV filename
        pseudonymize: If True, replaces patient IDs with P001, P002... for IRB/HIPAA compliance
        valid_only: If True, only includes sessions where quality_flag == 'VALID'
        
    Returns:
        Number of exported rows
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query all sessions ordered chronologically by patient and timestamp
    sessions_query = """
        SELECT * FROM sessions
        ORDER BY patient_id, datetime(timestamp) ASC, id ASC
    """
    cursor.execute(sessions_query)
    sessions = cursor.fetchall()

    # Query compensation events count by session_id
    comp_counts = {}
    try:
        cursor.execute("""
            SELECT session_id, COUNT(*) as comp_count
            FROM compensation_events
            WHERE session_id IS NOT NULL
            GROUP BY session_id
        """)
        comp_counts = {row["session_id"]: row["comp_count"] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        comp_counts = {}

    # Query adaptive prescriptions by session_id
    prescriptions_by_session = {}
    try:
        cursor.execute("""
            SELECT session_id, difficulty_tier, readiness_score
            FROM adaptive_prescriptions
            WHERE session_id IS NOT NULL
            ORDER BY id ASC
        """)
        for row in cursor.fetchall():
            prescriptions_by_session[row["session_id"]] = {
                "difficulty_tier": row["difficulty_tier"],
                "readiness_score": row["readiness_score"]
            }
    except sqlite3.OperationalError:
        prescriptions_by_session = {}

    conn.close()

    patient_mapping: Dict[str, str] = {}
    next_patient_idx = 1
    rows_written = 0

    # Track patient history across chronological rows for transition metrics
    patient_history: Dict[str, Dict[str, Any]] = {}

    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)

        for s in sessions:
            enc_patient_id = s["patient_id"]
            dec_patient_id = security_utils.decrypt_deterministic(enc_patient_id) if enc_patient_id else "Unknown"

            if pseudonymize:
                if dec_patient_id not in patient_mapping:
                    patient_mapping[dec_patient_id] = f"P{next_patient_idx:03d}"
                    next_patient_idx += 1
                patient_display_id = patient_mapping[dec_patient_id]
            else:
                patient_display_id = dec_patient_id

            session_id = s["id"]
            timestamp = s["timestamp"]
            level = s["level"] or 1
            exercise = s["exercise_name"] or EXERCISE_NAMES.get(level, f"Level {level}")
            acc_type = s["accuracy_type"] or ACCURACY_TYPES.get(level, "hit_rate")
            
            successful_hits = s["successful_hits"] if s["successful_hits"] is not None else 0
            total_attempts = s["total_attempts"] if s["total_attempts"] is not None else 0
            raw_accuracy = s["avg_accuracy"]
            accuracy_str = f"{raw_accuracy:.2f}" if raw_accuracy is not None else ""

            tracking_quality = s["tracking_quality"]
            tracking_str = f"{tracking_quality:.1f}" if tracking_quality is not None else ""

            rom = f"{s['max_finger_extension']:.1f}" if s["max_finger_extension"] is not None else ""
            mov_quality = f"{s['movement_quality_score']:.1f}" if s["movement_quality_score"] is not None else ""
            smoothness = f"{s['movement_smoothness']:.2f}" if s["movement_smoothness"] is not None else ""
            comp_events = comp_counts.get(session_id, 0)

            pain_before = s["pain_before_session"] if s["pain_before_session"] is not None else s["pain_level"]
            pain_after = s["pain_after_session"] if s["pain_after_session"] is not None else pain_before
            pain_delta = s["pain_difference"] if s["pain_difference"] is not None else (pain_after - pain_before)

            completion_time = f"{s['duration']:.1f}" if s["duration"] is not None else ""
            session_aborted = s["session_aborted"] if s["session_aborted"] is not None else 0
            quality_flag = s["quality_flag"] or "VALID"

            if valid_only and quality_flag != "VALID":
                continue

            # Prescription data
            rx = prescriptions_by_session.get(session_id, {})
            current_diff = rx.get("difficulty_tier", "STANDARD")
            readiness = f"{rx.get('readiness_score', 50.0):.1f}" if "readiness_score" in rx else ""

            # Transition metrics (previous vs new)
            prev_data = patient_history.get(dec_patient_id, {})
            prev_acc = prev_data.get("accuracy", "")
            prev_readiness = prev_data.get("readiness", "")
            prev_diff = prev_data.get("difficulty", "")
            new_diff = current_diff

            active_engagement = f"{s['active_engagement_duration']:.1f}" if ('active_engagement_duration' in s.keys() and s['active_engagement_duration'] is not None and s['active_engagement_duration'] > 0) else completion_time
            tracking_valid = f"{s['tracking_valid_duration']:.1f}" if ('tracking_valid_duration' in s.keys() and s['tracking_valid_duration'] is not None and s['tracking_valid_duration'] > 0) else completion_time
            target_scale = f"{s['target_scale']:.2f}" if ('target_scale' in s.keys() and s['target_scale'] is not None) else "1.00"
            speed_scale = f"{s['speed_scale']:.2f}" if ('speed_scale' in s.keys() and s['speed_scale'] is not None) else "1.00"
            session_time_limit = f"{s['session_time_limit']:.0f}" if ('session_time_limit' in s.keys() and s['session_time_limit'] is not None) else "30"
            hold_duration = f"{s['hold_duration']:.1f}" if ('hold_duration' in s.keys() and s['hold_duration'] is not None) else "1.5"
            rotation_tolerance = f"{s['rotation_tolerance']:.1f}" if ('rotation_tolerance' in s.keys() and s['rotation_tolerance'] is not None) else "25.0"
            assembly_tolerance = f"{s['assembly_position_tolerance']:.1f}" if ('assembly_position_tolerance' in s.keys() and s['assembly_position_tolerance'] is not None) else "50.0"
            corridor_width = f"{s['corridor_width']:.1f}" if ('corridor_width' in s.keys() and s['corridor_width'] is not None) else "60.0"
            
            succ_pickups = s["successful_pickups"] if ('successful_pickups' in s.keys() and s["successful_pickups"] is not None) else ""
            pickup_att = s["pickup_attempts"] if ('pickup_attempts' in s.keys() and s["pickup_attempts"] is not None) else ""
            succ_trans = s["successful_translations"] if ('successful_translations' in s.keys() and s["successful_translations"] is not None) else ""
            trans_att = s["translation_attempts"] if ('translation_attempts' in s.keys() and s["translation_attempts"] is not None) else ""
            succ_place = s["successful_placements"] if ('successful_placements' in s.keys() and s["successful_placements"] is not None) else ""
            place_att = s["placement_attempts"] if ('placement_attempts' in s.keys() and s["placement_attempts"] is not None) else ""
            unintended_drops = s["unintended_drops"] if ('unintended_drops' in s.keys() and s["unintended_drops"] is not None) else ""
            manip_time_avg = f"{s['manipulation_time_avg']:.2f}" if ('manipulation_time_avg' in s.keys() and s['manipulation_time_avg'] is not None and s['manipulation_time_avg'] > 0) else ""
            place_time_avg = f"{s['placement_time_avg']:.2f}" if ('placement_time_avg' in s.keys() and s['placement_time_avg'] is not None and s['placement_time_avg'] > 0) else ""
            correction_count = s["correction_count"] if ('correction_count' in s.keys() and s["correction_count"] is not None) else ""
            d2_contacts = s["d2_contacts"] if ('d2_contacts' in s.keys() and s["d2_contacts"] is not None) else ""
            d3_contacts = s["d3_contacts"] if ('d3_contacts' in s.keys() and s["d3_contacts"] is not None) else ""
            d4_contacts = s["d4_contacts"] if ('d4_contacts' in s.keys() and s["d4_contacts"] is not None) else ""
            d5_contacts = s["d5_contacts"] if ('d5_contacts' in s.keys() and s["d5_contacts"] is not None) else ""
            opp_lat_avg = f"{s['opposition_latency_avg']:.2f}" if ('opposition_latency_avg' in s.keys() and s['opposition_latency_avg'] is not None and s['opposition_latency_avg'] > 0) else ""

            idx_succ = s["index_successes"] if ('index_successes' in s.keys() and s["index_successes"] is not None) else ""
            mid_succ = s["middle_successes"] if ('middle_successes' in s.keys() and s["middle_successes"] is not None) else ""
            ring_succ = s["ring_successes"] if ('ring_successes' in s.keys() and s["ring_successes"] is not None) else ""
            pinky_succ = s["pinky_successes"] if ('pinky_successes' in s.keys() and s["pinky_successes"] is not None) else ""
            idx_att = s["index_attempts"] if ('index_attempts' in s.keys() and s["index_attempts"] is not None) else ""
            mid_att = s["middle_attempts"] if ('middle_attempts' in s.keys() and s["middle_attempts"] is not None) else ""
            ring_att = s["ring_attempts"] if ('ring_attempts' in s.keys() and s["ring_attempts"] is not None) else ""
            pinky_att = s["pinky_attempts"] if ('pinky_attempts' in s.keys() and s["pinky_attempts"] is not None) else ""
            unintended_events = s["unintended_movement_events"] if ('unintended_movement_events' in s.keys() and s["unintended_movement_events"] is not None) else ""
            act_time_avg = f"{s['target_activation_time_avg']:.2f}" if ('target_activation_time_avg' in s.keys() and s['target_activation_time_avg'] is not None and s['target_activation_time_avg'] > 0) else ""
            dwell_succ = s["dwell_success_count"] if ('dwell_success_count' in s.keys() and s["dwell_success_count"] is not None) else ""
            dwell_fail = s["dwell_failure_count"] if ('dwell_failure_count' in s.keys() and s["dwell_failure_count"] is not None) else ""
            mov_time = f"{s['average_movement_time']:.2f}" if ('average_movement_time' in s.keys() and s['average_movement_time'] is not None and s['average_movement_time'] > 0) else ""
            tgt_err = f"{s['average_target_error']:.2f}" if ('average_target_error' in s.keys() and s['average_target_error'] is not None) else ""
            overshoot = f"{s['average_overshoot']:.2f}" if ('average_overshoot' in s.keys() and s['average_overshoot'] is not None) else ""
            hold_stab = f"{s['average_hold_stability']:.2f}" if ('average_hold_stability' in s.keys() and s['average_hold_stability'] is not None) else ""
            dir_acc = f"{s['direction_accuracy']:.2f}" if ('direction_accuracy' in s.keys() and s['direction_accuracy'] is not None) else ""
            cs_succ = s["card_shift_successes"] if ('card_shift_successes' in s.keys() and s["card_shift_successes"] is not None) else ""
            cs_att = s["card_shift_attempts"] if ('card_shift_attempts' in s.keys() and s["card_shift_attempts"] is not None) else ""
            avg_shift_lat = f"{s['average_shift_latency']:.2f}" if ('average_shift_latency' in s.keys() and s['average_shift_latency'] is not None and s['average_shift_latency'] > 0) else ""
            med_shift_lat = f"{s['median_shift_latency']:.2f}" if ('median_shift_latency' in s.keys() and s['median_shift_latency'] is not None and s['median_shift_latency'] > 0) else ""
            max_shift_lat = f"{s['maximum_shift_latency']:.2f}" if ('maximum_shift_latency' in s.keys() and s['maximum_shift_latency'] is not None and s['maximum_shift_latency'] > 0) else ""
            inc_events = s["incorrect_finger_events"] if ('incorrect_finger_events' in s.keys() and s["incorrect_finger_events"] is not None) else ""
            timeouts = s["target_timeouts"] if ('target_timeouts' in s.keys() and s["target_timeouts"] is not None) else ""
            seq_comp = f"{s['sequence_completion_rate']:.2f}" if ('sequence_completion_rate' in s.keys() and s['sequence_completion_rate'] is not None) else ""

            row = [
                patient_display_id,
                session_id,
                timestamp,
                exercise,
                level,
                current_diff,
                acc_type,
                successful_hits,
                total_attempts,
                accuracy_str,
                tracking_str,
                rom,
                mov_quality,
                smoothness,
                comp_events,
                pain_before,
                pain_after,
                pain_delta,
                completion_time,
                active_engagement,
                tracking_valid,
                readiness,
                target_scale,
                speed_scale,
                session_time_limit,
                hold_duration,
                rotation_tolerance,
                assembly_tolerance,
                corridor_width,
                succ_pickups,
                pickup_att,
                succ_trans,
                trans_att,
                succ_place,
                place_att,
                unintended_drops,
                manip_time_avg,
                place_time_avg,
                correction_count,
                d2_contacts,
                d3_contacts,
                d4_contacts,
                d5_contacts,
                opp_lat_avg,
                idx_succ,
                mid_succ,
                ring_succ,
                pinky_succ,
                idx_att,
                mid_att,
                ring_att,
                pinky_att,
                unintended_events,
                act_time_avg,
                dwell_succ,
                dwell_fail,
                mov_time,
                tgt_err,
                overshoot,
                hold_stab,
                dir_acc,
                cs_succ,
                cs_att,
                avg_shift_lat,
                med_shift_lat,
                max_shift_lat,
                inc_events,
                timeouts,
                seq_comp,
                prev_acc,
                prev_readiness,
                prev_diff,
                new_diff,
                session_aborted,
                quality_flag
            ]

            writer.writerow(row)
            rows_written += 1

            # Update history for this patient
            patient_history[dec_patient_id] = {
                "accuracy": accuracy_str,
                "readiness": readiness,
                "difficulty": current_diff
            }

    print(f"[SUCCESS] Exported {rows_written} research session records to {output_csv}")
    if pseudonymize:
        print(f"[PRIVACY] Pseudonymized {len(patient_mapping)} patient profiles.")
    return rows_written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export research dataset from AI Rehabilitation SQLite DB")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to rehab_data.db")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_CSV, help="Output CSV path")
    parser.add_argument("--no-pseudonymize", action="store_true", help="Keep decrypted patient names (not recommended for publication)")
    parser.add_argument("--valid-only", action="store_true", help="Include only sessions with quality_flag == VALID")
    args = parser.parse_args()

    export_research_dataset(
        db_path=args.db,
        output_csv=args.output,
        pseudonymize=not args.no_pseudonymize,
        valid_only=args.valid_only
    )
