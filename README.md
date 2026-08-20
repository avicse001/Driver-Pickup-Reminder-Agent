# 🚖 Mr. Cabie — Driver Pickup Reminder Agent (v1)

> **Automated Voice Dispatch System to Eliminate Late & Missed Pickups**  
> *Onboarding Test Task — Founder's Office Intern*

---

## 📌 Executive Summary & Problem Breakdown

Late pickups and missed customer communications happen primarily because drivers lose track of time or fail to contact the passenger prior to departure. Manually following up with dozens of drivers across a fleet is unscalable and error-prone for operations teams.

**Mr. Cabie Reminder Agent** is an automated voice dispatch system that:
1. Monitors scheduled rides from the operations sheet / database.
2. Identifies rides **30 minutes prior to scheduled pickup time**.
3. Automatically places an outbound phone call to the driver via **Twilio Voice**.
4. Delivers a clear text-to-speech message instructing them to:
   - Call/message the customer immediately to confirm pickup.
   - Begin driving to the pickup location to arrive on time.
5. Marks the ride record as `Reminder Sent` (with call timestamp & SID) to **prevent duplicate calls**.
6. Logs unanswered or failed calls with complete visibility for operations.

---

## 🎥 Project Demo Video (MP4)
An automated HD recording of the full working system is included directly in this repository:
- **File**: [`demo_recording.mp4`](file:///c:/Users/avics/OneDrive/Desktop/Mr.%20Cabie/demo_recording.mp4) (H.264 720p HD)
- **What it showcases**:
  1. Live operations dashboard with the sample Google Sheet rides.
  2. Automated 30-minute reminder scan trigger (Ramesh Kumar at 8:30 AM for 9:00 AM ride).
  3. Real-time status update to `Reminder Sent` with call SID and timestamp logging.
  4. Subsequent ride reminders & manual on-demand call triggers.
  5. Audio preview of the synthesized voice message spoken to drivers.

To re-record or customize the video at any time:
```bash
python record_demo_video.py
```

---

## ⚡ Quick Start: How to Run

### 1. Install Dependencies
Ensure Python 3.9+ is installed, then run:
```bash
pip install -r requirements.txt
```

---

### 2. Configure Environment (Optional for Live Twilio Calls)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Inside `.env`, configure your Twilio trial credentials:
```ini
TWILIO_ACCOUNT_SID=ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX

# If using a Twilio Free Trial account, set your verified phone number here:
TEST_DRIVER_PHONE=+919876543210
```
> 💡 **No Twilio account yet?** No problem! The system automatically defaults to **Simulation Mode**, allowing you to test full end-to-end scanning, status updates, and audio previews immediately without credentials.

---

### 3. Run the Interactive Web Dashboard & Webhook Server
Launch the local web server:
```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser to access:
- **Live Scheduled Rides Table** with real-time status badges.
- **Time Machine Simulator**: Test 30-min triggers for any date/time (e.g. `21-Aug-2026 08:30 am`).
- **Live Call Activity Feed**: View call timestamps and Twilio SIDs.
- **Text-to-Speech Voice Preview**: Listen to the exact audio reminder played to drivers.
- **Manual "Call Now" Trigger**: On-demand dispatch button.

---

### 4. Run via Command Line Interface (CLI)

- **Single Scan (Current Time)**:
  ```bash
  python reminder_agent.py --run-now
  ```

- **Simulate a Specific Time (e.g., 8:30 AM for Ramesh Kumar's 9:00 AM pickup)**:
  ```bash
  python reminder_agent.py --simulate-time "21-Aug-2026 08:30 am"
  ```

- **Run Continuous Background Daemon (polls every 30s)**:
  ```bash
  python reminder_agent.py --daemon
  ```

- **Manually Trigger a Specific Ride (e.g. Ride #1)**:
  ```bash
  python reminder_agent.py --trigger-ride 1
  ```

- **Reset Rides Data back to Original Sample**:
  ```bash
  python reminder_agent.py --reset-data
  ```

---

### 5. Run Automated Tests
```bash
python -m unittest test_agent.py
```

---

## 🏗️ Architecture & How It Works

```
┌────────────────────────────────────────────────────────┐
│                   Data Layer                           │
│  rides_data.csv / Google Sheet Export                  │
│  - Driver Name | Phone | Location | Scheduled Time     │
│  - Reminder Status | Call SID | Attempt Timestamp     │
└──────────────────────────┬─────────────────────────────┘
                           │ 1. Read scheduled rides
                           ▼
┌────────────────────────────────────────────────────────┐
│               Reminder Agent Engine                    │
│  - Filters rides where: pickup_time - now ≈ 30 mins    │
│  - Idempotency check: status == "Pending"              │
│  - Updates status to "Triggering Call..."              │
└──────────────────────────┬─────────────────────────────┘
                           │ 2. Dispatch call
                           ▼
┌────────────────────────────────────────────────────────┐
│               Twilio Voice Service                     │
│  - Generates dynamic TwiML voice XML                   │
│  - Initiates outbound call to driver                   │
│  - Webhook callback receives ringing/answered/status   │
└──────────────────────────┬─────────────────────────────┘
                           │ 3. Sync & Log
                           ▼
┌────────────────────────────────────────────────────────┐
│             Operations Visibility & State              │
│  - Writes "Reminder Sent" / "No Answer" to Sheet       │
│  - Real-time Dashboard & Activity Log                  │
└────────────────────────────────────────────────────────┘
```

### 🗣️ Voice Message Script (TwiML)
When the driver answers, Twilio's neural voice delivers:
> *"Hello **[Driver Name]**. This is an automated reminder from Mr. Cabie dispatch. You have a scheduled pickup at **[Pickup Location]** in 30 minutes. Please do two things now: First, call or message your customer to confirm the pickup. Second, start heading towards **[Pickup Location]** so you arrive on time. Thank you and drive safely!"*

---

## 👥 Non-Technical Operations Team Guide

### What does this tool do for you?
You no longer have to look at the clock and manually dial drivers 30 minutes before each pickup. The agent monitors the schedule 24/7 and calls the driver on your behalf.

### What should you do day-to-day?
1. **Add new rides** directly in the sheet or via the dashboard "Add Ride" button.
2. Watch the dashboard for status indicators:
   - 🟢 **Reminder Sent**: Driver was successfully called and reminded.
   - 🟡 **Pending**: Ride is scheduled for later; agent is waiting for the 30-min mark.
   - 🔴 **No Answer / Failed**: The driver did not pick up. Fleet manager should follow up manually.
3. If an urgent ride needs an immediate call, click **"Call Now"** next to the driver's name.

---

## 🔮 What We'd Improve in V2 (Roadmap)

While V1 intentionally keeps the scope narrow and reliable, here is what we recommend building next:

| Feature | Description | Business Impact |
| :--- | :--- | :--- |
| **Interactive IVR (Press 1 to Confirm)** | Prompt the driver: *"Press 1 to confirm you are on your way, or press 2 to request dispatch help."* | Guarantees driver acknowledgment rather than just leaving voicemail. |
| **SMS / WhatsApp Fallback** | If the voice call goes unanswered after 45 seconds, instantly send an automated WhatsApp/SMS with pickup details. | Catches drivers in poor network zones or noisy vehicles. |
| **Fleet Manager Escalation** | If a driver fails to answer after 2 attempts (e.g. at T-25 mins), send an urgent Slack/Telegram alert to the fleet supervisor. | Enables proactive re-assignment before the customer experiences a delay. |
| **Live Telematics / GPS Check** | Check the vehicle's real-time distance from pickup. If ETA > 30 minutes, trigger an early reminder at T-45 mins. | Adapts dynamically to heavy traffic conditions. |
| **Google Sheets 2-Way Webhook Sync** | Direct bidirectional sync using Google Apps Script or Google Sheets API so edits in Google Sheets reflect in real time. | Seamless integration with existing operations workflows. |

---

## 📁 Repository Structure

```
Mr. Cabie/
├── app.py              # FastAPI server + Operations Dashboard + Twilio Webhooks
├── reminder_agent.py   # Core scheduler & 30-min window evaluation engine
├── data_manager.py     # CSV & Google Sheet data parser and state manager
├── twilio_service.py   # Twilio outbound voice client & TwiML generator
├── test_agent.py       # Automated unit test suite
├── rides_data.csv      # Persistent ride dataset with sample rows
├── config.py           # Configuration & environment loader
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── README.md           # Documentation & operations guide
```
#
