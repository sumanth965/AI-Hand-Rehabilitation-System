"""
AI Hand Rehabilitation System - Root Application Entry Point

Launches the Zero-Keyboard AI Physiotherapy patient application by default,
or the Therapist Admin Dashboard if invoked with the `--dashboard` flag.
"""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="AI Hand Rehabilitation System (Zero-Keyboard Physiotherapy)"
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Launch the Therapist Admin Dashboard instead of the patient application"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8081,
        help="Port for the Therapist Admin Dashboard (default: 8081)"
    )
    args = parser.parse_args()

    if args.dashboard:
        from admin_dashboard.server import run_server
        print("Starting Therapist Admin Dashboard...")
        run_server(port=args.port)
    else:
        from zero_keyboard_physio import main as run_patient_app
        print("Starting AI Hand Rehabilitation System (Patient Application)...")
        run_patient_app()


if __name__ == "__main__":
    main()
