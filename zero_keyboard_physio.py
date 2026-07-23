"""
Zero-Keyboard AI Physiotherapy System
Complete hand control with split-screen medical sidebar

This is a thin entry-point wrapper. All code now lives in the `physio/` package.
"""

from physio import main
from physio.database import DatabaseManager

__all__ = ["main", "DatabaseManager"]

if __name__ == "__main__":
    main()
