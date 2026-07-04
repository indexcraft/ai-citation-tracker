#!/usr/bin/env python3
"""
Entry point. Run this file to execute a full tracking pass.

Usage:
    python run_tracker.py
"""

from dotenv import load_dotenv
from citation_tracker.tracker import run

if __name__ == "__main__":
    load_dotenv()  # pulls API keys from .env into environment variables
    run(config_path="config.yaml", output_dir="reports")
