"""Vercel serverless entry point for the Flask webapp."""

import sys
import os
from pathlib import Path

# Set project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# On Vercel, use /tmp for writable SQLite
if os.environ.get("VERCEL"):
    os.environ["RELOADING_DB_PATH"] = "/tmp/reloading.db"

from webapp.app import app

# Vercel needs the Flask app exposed as `app`
