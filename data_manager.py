import csv
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
import requests
import config

DATE_FORMATS = [
    "%d-%b-%Y %I:%M %p",    # 21-Aug-2026 09:00 am
    "%d-%b-%Y %I:%M%p",     # 21-Aug-2026 09:00am
    "%d-%b-%Y %H:%M",       # 21-Aug-2026 09:00
    "%Y-%m-%d %H:%M:%S",   # 2026-08-21 09:00:00
    "%Y-%m-%d %H:%M",      # 2026-08-21 09:00
    "%Y-%m-%d %I:%M %p",   # 2026-08-21 09:00 am
    "%d/%m/%Y %H:%M",      # 21/08/2026 09:00
    "%d/%m/%Y %I:%M %p",   # 21/08/2026 09:00 am
]

@dataclass
class Ride:
    id: int
    driver_name: str
    driver_phone: str
    pickup_location: str
    scheduled_pickup_time_raw: str
    scheduled_pickup_time: Optional[datetime]
    reminder_status: str = "Pending"
    call_sid: str = ""
    last_attempted_at: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "driver_name": self.driver_name,
            "driver_phone": self.driver_phone,
            "pickup_location": self.pickup_location,
            "scheduled_pickup_time_raw": self.scheduled_pickup_time_raw,
            "scheduled_pickup_time": self.scheduled_pickup_time.isoformat() if self.scheduled_pickup_time else None,
            "reminder_status": self.reminder_status,
            "call_sid": self.call_sid,
            "last_attempted_at": self.last_attempted_at,
            "notes": self.notes,
            "minutes_until_pickup": self.get_minutes_until(datetime.now()) if self.scheduled_pickup_time else None,
        }

    def get_minutes_until(self, current_time: datetime) -> Optional[float]:
        if not self.scheduled_pickup_time:
            return None
        delta = self.scheduled_pickup_time - current_time
        return round(delta.total_seconds() / 60.0, 1)

def parse_pickup_datetime(dt_str: str) -> Optional[datetime]:
    """Parse various datetime string formats into a Python datetime object."""
    if not dt_str:
        return None
    cleaned = dt_str.strip()
    # Normalize multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    # Try ISO parsing as fallback
    try:
        return datetime.fromisoformat(cleaned)
    except Exception:
        return None

class DataManager:
    def __init__(self, csv_path: str = config.CSV_FILE_PATH):
        self.csv_path = csv_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.csv_path):
            self.reset_to_default_sample()

    def reset_to_default_sample(self):
        sample_rows = [
            ["Driver Name", "Driver Phone Number", "Pickup Location", "Scheduled Pickup Time", "Reminder Status", "Call SID", "Last Attempted At", "Notes"],
            ["Ramesh Kumar", "+91 98765 43210", "DLF Cyber City, Gurugram", "21-Aug-2026 09:00 am", "Pending", "", "", ""],
            ["Suresh Yadav", "+91 91234 56780", "Indira Gandhi Intl Airport, T3", "21-Aug-2026 09:45 am", "Pending", "", "", ""],
            ["Amit Sharma", "+91 99887 66554", "Cyberhub, Sector 24, Gurugram", "21-Aug-2026 10:30 am", "Pending", "", "", ""],
            ["Vikram Singh", "+91 90123 45678", "Connaught Place, New Delhi", "21-Aug-2026 11:15 am", "Pending", "", "", ""],
            ["Rajesh Verma", "+91 98111 22334", "Sector 62, Noida", "21-Aug-2026 12:00 pm", "Pending", "", "", ""],
        ]
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(sample_rows)

    def load_rides(self) -> List[Ride]:
        """Load all rides from CSV or Google Sheet CSV export if configured."""
        rides = []
        rows = []

        # If a Google Sheet public CSV URL is configured, try fetching first
        if config.GOOGLE_SHEET_CSV_URL:
            try:
                resp = requests.get(config.GOOGLE_SHEET_CSV_URL, timeout=5)
                if resp.status_code == 200:
                    lines = resp.text.splitlines()
                    reader = csv.reader(lines)
                    rows = list(reader)
            except Exception as e:
                print(f"[DataManager] Warning: Failed to fetch Google Sheet CSV: {e}. Falling back to local CSV.")

        if not rows:
            if not os.path.exists(self.csv_path):
                self._ensure_file_exists()
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)

        if not rows:
            return []

        header = [h.strip().lower() for h in rows[0]]
        
        # Determine column indexes
        def find_idx(candidates, default=-1):
            for cand in candidates:
                for i, h in enumerate(header):
                    if cand in h:
                        return i
            return default

        idx_name = find_idx(["driver name", "driver", "name"], 0)
        idx_phone = find_idx(["phone", "mobile", "contact"], 1)
        idx_loc = find_idx(["location", "pickup location", "pickup"], 2)
        idx_time = find_idx(["time", "scheduled", "pickup time"], 3)
        idx_status = find_idx(["status", "reminder status"], 4)
        idx_sid = find_idx(["call sid", "sid"], 5)
        idx_attempt = find_idx(["attempt", "last attempted"], 6)
        idx_notes = find_idx(["notes", "note"], 7)

        for i, row in enumerate(rows[1:], start=1):
            if not row or not any(row):
                continue
            
            def get_val(idx):
                return row[idx].strip() if 0 <= idx < len(row) else ""

            raw_time = get_val(idx_time)
            parsed_time = parse_pickup_datetime(raw_time)

            ride = Ride(
                id=i,
                driver_name=get_val(idx_name) or f"Driver {i}",
                driver_phone=get_val(idx_phone),
                pickup_location=get_val(idx_loc) or "Pickup Location",
                scheduled_pickup_time_raw=raw_time,
                scheduled_pickup_time=parsed_time,
                reminder_status=get_val(idx_status) or "Pending",
                call_sid=get_val(idx_sid),
                last_attempted_at=get_val(idx_attempt),
                notes=get_val(idx_notes)
            )
            rides.append(ride)

        return rides

    def save_rides(self, rides: List[Ride]):
        """Persist rides back to CSV."""
        headers = [
            "Driver Name", "Driver Phone Number", "Pickup Location", 
            "Scheduled Pickup Time", "Reminder Status", "Call SID", 
            "Last Attempted At", "Notes"
        ]
        rows = [headers]
        for r in rides:
            rows.append([
                r.driver_name,
                r.driver_phone,
                r.pickup_location,
                r.scheduled_pickup_time_raw,
                r.reminder_status,
                r.call_sid,
                r.last_attempted_at,
                r.notes
            ])
        
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    def update_ride_status(self, ride_id: int, status: str, call_sid: str = "", notes: str = "") -> Optional[Ride]:
        """Update a specific ride's reminder status, call SID, and timestamp."""
        rides = self.load_rides()
        target_ride = None
        now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")

        for r in rides:
            if r.id == ride_id or (call_sid and r.call_sid == call_sid):
                r.reminder_status = status
                if call_sid:
                    r.call_sid = call_sid
                r.last_attempted_at = now_str
                if notes:
                    r.notes = notes
                target_ride = r
                break

        if target_ride:
            self.save_rides(rides)
        return target_ride

    def get_due_rides(self, current_time: Optional[datetime] = None, window_minutes: int = 30, tolerance_minutes: int = 5) -> List[Ride]:
        """
        Find rides where pickup is within the reminder window (e.g. 30 ± tolerance minutes)
        or past due within the day and still marked 'Pending'.
        """
        if current_time is None:
            current_time = datetime.now()

        rides = self.load_rides()
        due_rides = []

        min_lead = window_minutes - tolerance_minutes # e.g. 25 min
        max_lead = window_minutes + tolerance_minutes # e.g. 35 min

        for r in rides:
            # Skip if reminder already triggered or completed
            if r.reminder_status not in ["Pending", "", None]:
                continue

            if not r.scheduled_pickup_time:
                continue

            # Calculate difference in minutes between scheduled pickup and current time
            delta = (r.scheduled_pickup_time - current_time).total_seconds() / 60.0

            # Match if within the 30-min window (e.g. 25 to 35 mins away)
            # Or if it's due soon (between 0 and 30 mins) and wasn't reminded yet
            if 0 <= delta <= max_lead:
                due_rides.append(r)

        return due_rides

    def add_ride(self, driver_name: str, driver_phone: str, pickup_location: str, pickup_time_str: str) -> Ride:
        """Add a new ride entry."""
        rides = self.load_rides()
        new_id = len(rides) + 1
        parsed = parse_pickup_datetime(pickup_time_str)
        new_ride = Ride(
            id=new_id,
            driver_name=driver_name.strip(),
            driver_phone=driver_phone.strip(),
            pickup_location=pickup_location.strip(),
            scheduled_pickup_time_raw=pickup_time_str.strip(),
            scheduled_pickup_time=parsed,
            reminder_status="Pending",
            call_sid="",
            last_attempted_at="",
            notes="Added via API/UI"
        )
        rides.append(new_ride)
        self.save_rides(rides)
        return new_ride
