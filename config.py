import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "").strip()

# Verification / Test Number (useful for Twilio Trial accounts)
TEST_DRIVER_PHONE = os.getenv("TEST_DRIVER_PHONE", "").strip()

# Application Settings
REMINDER_WINDOW_MINUTES = int(os.getenv("REMINDER_WINDOW_MINUTES", "30"))
WINDOW_TOLERANCE_MINUTES = int(os.getenv("WINDOW_TOLERANCE_MINUTES", "5")) # check window e.g. 25-35 min
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))

# Base URL for Webhooks (e.g. ngrok URL or public domain)
BASE_WEBHOOK_URL = os.getenv("BASE_WEBHOOK_URL", "").rstrip("/")

# Data source configuration
CSV_FILE_PATH = os.getenv("CSV_FILE_PATH", str(BASE_DIR / "rides_data.csv"))
GOOGLE_SHEET_CSV_URL = os.getenv("GOOGLE_SHEET_CSV_URL", "").strip()

# Server Settings
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

def is_twilio_configured() -> bool:
    """Check if valid Twilio credentials are provided."""
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER and not TWILIO_ACCOUNT_SID.startswith("your_"))
