#!/usr/bin/env python3
"""Daily morning report script.

Run via cron at 6am Pacific:
0 6 * * * /usr/bin/python3 /path/to/personal-assistant/scripts/daily_report.py
"""

import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.report import ReportGenerator
from src.storage import TaskStorage


def main():
    """Generate and send daily report."""
    # Initialize storage and report generator
    storage = TaskStorage()
    generator = ReportGenerator(storage)
    
    # Generate report
    report = generator.generate_daily_report()
    
    # Print to stdout (will be captured by cron/logger)
    print(report)
    
    # TODO: Send via WhatsApp/Telegram using OpenClaw message tool
    # This requires integration with the agent system
    # For now, stdout output can be piped to a notification script
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
