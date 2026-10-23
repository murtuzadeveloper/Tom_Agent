"""
Application entry point for murtuzadeveloper Smart Leads.
AI-Powered Screen Intelligence & Contact Extraction for Windows 11.
"""

import sys
import os
import traceback
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from config import CONFIG
from app.database.db import init_db
from app.services.csv_service import CSVService
from app.utils.logger import logger
from app.ui.main_window import MainWindow

def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to capture unhandled crashes."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.critical(f"Unhandled Exception:\n{err_msg}")
    print(f"CRITICAL ERROR: {err_msg}", file=sys.stderr)

def main():
    """Bootstraps database, configures Qt runtime, and displays main interface."""
    sys.excepthook = handle_exception

    logger.info(f"Starting {CONFIG.app_name} v{CONFIG.version}...")
    logger.info(f"Workspace root: {PROJECT_ROOT}")

    # Initialize SQLite database
    init_db(CONFIG.db_path)

    # Pre-initialize CSV file on Desktop
    csv_service = CSVService(CONFIG.csv_path)
    logger.info(f"Target CSV file ready at: {CONFIG.csv_path}")

    # High DPI Scaling Setup
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName(CONFIG.app_name)
    app.setOrganizationName(CONFIG.author)

    window = MainWindow()
    window.show()

    logger.info("Main application window displayed.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
