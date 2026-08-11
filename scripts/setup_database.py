import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from app.db import init_db

if __name__ == "__main__":
    init_db()
    print("Database schema created successfully.")
