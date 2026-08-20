import os
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import FastAPI, Form, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from data_manager import DataManager, parse_pickup_datetime
from twilio_service import TwilioService, generate_twiml, get_call_logs
from reminder_agent import ReminderAgent
import config

app = FastAPI(
    title="Mr. Cabie - Driver Pickup Reminder Agent",
    description="Automated voice dispatch & reminder agent to eliminate missed/late pickups.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_mgr = DataManager()
twilio_svc = TwilioService()
agent = ReminderAgent(data_manager=data_mgr, twilio_service=twilio_svc)

class AddRideRequest(BaseModel):
    driver_name: str
    driver_phone: str
    pickup_location: str
    scheduled_pickup_time: str

class SimulationScanRequest(BaseModel):
    simulated_time: Optional[str] = None
    force_mock: Optional[bool] = False

# ==========================================
# Twilio Voice & Webhook Endpoints
# ==========================================

@app.get("/api/twiml/reminder", response_class=Response)
@app.post("/api/twiml/reminder", response_class=Response)
async def twiml_reminder(driver_name: str = "Driver", pickup_location: str = "your pickup point"):
    """Returns TwiML XML voice instructions for Twilio outbound/inbound calls."""
    twiml_xml = generate_twiml(driver_name, pickup_location)
    return Response(content=twiml_xml, media_type="application/xml")

@app.post("/api/twilio/call-status")
async def twilio_call_status(request: Request):
    """
    Twilio status callback webhook.
    Receives events such as: initiated, ringing, answered, completed, busy, no-answer, failed.
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    call_status = form_data.get("CallStatus", "").lower()
    call_duration = form_data.get("CallDuration", "0")
    
    print(f"[Twilio Webhook] Received status '{call_status}' for Call SID {call_sid} (Duration: {call_duration}s)")

    # Map Twilio call statuses to operational sheet status
    status_mapping = {
        "completed": "Reminder Sent",
        "in-progress": "In Call",
        "answered": "In Call",
        "ringing": "Ringing",
        "busy": "Line Busy",
        "no-answer": "No Answer",
        "failed": "Call Failed",
        "canceled": "Call Canceled"
    }

    final_status = status_mapping.get(call_status, call_status.capitalize())
    notes = f"Twilio status: {call_status} (Duration: {call_duration}s)"

    # Update ride record in CSV
    data_mgr.update_ride_status(ride_id=-1, status=final_status, call_sid=call_sid, notes=notes)

    # Update in-memory call log if present
    for log in get_call_logs():
        if log.get("call_sid") == call_sid:
            log["status"] = call_status
            log["notes"] = notes
            break

    return {"status": "ok", "call_sid": call_sid, "updated_status": final_status}

# ==========================================
# REST API Endpoints
# ==========================================

@app.get("/api/config-status")
def get_config_status():
    return {
        "twilio_configured": twilio_svc.is_configured,
        "twilio_phone_number": config.TWILIO_PHONE_NUMBER if twilio_svc.is_configured else "Not Set (Simulation Mode)",
        "test_driver_phone": config.TEST_DRIVER_PHONE or "None (Calling number in row)",
        "reminder_window_minutes": config.REMINDER_WINDOW_MINUTES,
        "window_tolerance_minutes": config.WINDOW_TOLERANCE_MINUTES,
        "csv_path": config.CSV_FILE_PATH,
        "server_time": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    }

@app.get("/api/rides")
def list_rides():
    rides = data_mgr.load_rides()
    return [r.to_dict() for r in rides]

@app.post("/api/rides/add")
def add_ride(req: AddRideRequest):
    new_ride = data_mgr.add_ride(
        driver_name=req.driver_name,
        driver_phone=req.driver_phone,
        pickup_location=req.pickup_location,
        pickup_time_str=req.scheduled_pickup_time
    )
    return {"success": True, "ride": new_ride.to_dict()}

@app.post("/api/rides/trigger/{ride_id}")
def trigger_ride_call(ride_id: int, force_mock: bool = False):
    result = agent.trigger_single_ride(ride_id=ride_id, force_mock=force_mock)
    return result

@app.post("/api/rides/reset")
def reset_rides():
    data_mgr.reset_to_default_sample()
    return {"success": True, "message": "Dataset reset to default sample rows."}

@app.post("/api/agent/run-scan")
def run_agent_scan(req: SimulationScanRequest):
    sim_dt = None
    if req.simulated_time:
        sim_dt = parse_pickup_datetime(req.simulated_time)
        if not sim_dt:
            raise HTTPException(status_code=400, detail=f"Invalid simulated datetime format '{req.simulated_time}'")

    result = agent.check_and_trigger_reminders(current_time=sim_dt, force_mock=req.force_mock)
    return result

@app.get("/api/call-logs")
def call_logs():
    return get_call_logs()

# ==========================================
# Operations UI Dashboard
# ==========================================

@app.get("/", response_class=HTMLResponse)
def index_page():
    return """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mr. Cabie — Driver Pickup Reminder Agent</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: {
              50: '#eef9ff',
              500: '#0284c7',
              600: '#0369a1',
              700: '#075985',
              900: '#0c4a6e',
            }
          }
        }
      }
    }
  </script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
    .glass-card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .pulse-dot { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .4; transform: scale(1.1); } }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
  <!-- Top Navigation -->
  <header class="border-b border-slate-800/80 bg-slate-900/80 sticky top-0 z-50 backdrop-blur-md">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
          <i class="fa-solid fa-taxi text-white text-lg"></i>
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <h1 class="font-bold text-lg text-white">Mr. Cabie</h1>
            <span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20">Reminder Agent v1.0</span>
          </div>
          <p class="text-xs text-slate-400">Automated 30-min Driver Voice Reminders</p>
        </div>
      </div>

      <div class="flex items-center space-x-4">
        <div id="twilioBadge" class="hidden sm:flex items-center space-x-2 px-3 py-1 rounded-lg text-xs font-medium border bg-slate-800/80 border-slate-700">
          <span id="twilioDot" class="w-2 h-2 rounded-full bg-amber-400 pulse-dot"></span>
          <span id="twilioText" class="text-slate-300">Checking Twilio...</span>
        </div>

        <button onclick="refreshData()" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-slate-700 transition flex items-center space-x-1.5 shadow-sm">
          <i class="fa-solid fa-rotate text-sky-400"></i>
          <span>Sync</span>
        </button>

        <button onclick="resetData()" class="px-3 py-1.5 rounded-lg bg-red-950/40 hover:bg-red-900/60 text-xs font-semibold text-red-300 border border-red-800/40 transition">
          <i class="fa-solid fa-arrows-rotate mr-1"></i> Reset Data
        </button>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
    
    <!-- Top Stats Row -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="glass-card rounded-2xl p-5 shadow-sm">
        <div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
          <span>Scheduled Rides</span>
          <i class="fa-solid fa-calendar-check text-sky-400 text-base"></i>
        </div>
        <div id="statTotalRides" class="text-3xl font-extrabold text-white mt-2">0</div>
        <div class="text-xs text-slate-500 mt-1">From connected sheet/CSV</div>
      </div>

      <div class="glass-card rounded-2xl p-5 shadow-sm">
        <div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
          <span>Due for 30m Reminder</span>
          <i class="fa-solid fa-bell text-amber-400 text-base"></i>
        </div>
        <div id="statDueRides" class="text-3xl font-extrabold text-amber-400 mt-2">0</div>
        <div class="text-xs text-slate-500 mt-1">Pickup within next ~30 mins</div>
      </div>

      <div class="glass-card rounded-2xl p-5 shadow-sm">
        <div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
          <span>Reminders Sent</span>
          <i class="fa-solid fa-phone-volume text-emerald-400 text-base"></i>
        </div>
        <div id="statSentRides" class="text-3xl font-extrabold text-emerald-400 mt-2">0</div>
        <div class="text-xs text-slate-500 mt-1">Voice call dispatched</div>
      </div>

      <div class="glass-card rounded-2xl p-5 shadow-sm">
        <div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
          <span>Pending Reminders</span>
          <i class="fa-solid fa-hourglass-half text-indigo-400 text-base"></i>
        </div>
        <div id="statPendingRides" class="text-3xl font-extrabold text-indigo-400 mt-2">0</div>
        <div class="text-xs text-slate-500 mt-1">Waiting for 30m window</div>
      </div>
    </div>

    <!-- Simulator & Live Agent Runner Box -->
    <div class="glass-card rounded-2xl p-6 border border-sky-500/20 bg-gradient-to-r from-slate-900 via-slate-900 to-sky-950/30">
      <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
        <div class="space-y-1.5">
          <div class="flex items-center space-x-2">
            <span class="flex h-2.5 w-2.5 relative">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-sky-500"></span>
            </span>
            <h2 class="text-base font-bold text-white">Agent Time Machine & Simulator</h2>
          </div>
          <p class="text-xs text-slate-400 max-w-xl">
            Test the automated 30-minute reminder trigger on the sample rides. Select a simulated time (e.g. <strong>21-Aug-2026 08:30 am</strong> for Ramesh Kumar's 9:00 am ride) or run against the current time.
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <div class="relative">
            <input id="simTimeInput" type="text" placeholder="21-Aug-2026 08:30 am" value="21-Aug-2026 08:30 am" 
                   class="bg-slate-950/80 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500 w-52" />
          </div>

          <button onclick="runAgentScan(true)" class="px-4 py-2 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-xs font-bold text-white shadow-lg shadow-sky-500/25 transition flex items-center space-x-2">
            <i class="fa-solid fa-play"></i>
            <span>Simulate Time Scan</span>
          </button>

          <button onclick="runAgentScan(false)" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-bold text-slate-200 transition flex items-center space-x-2">
            <i class="fa-solid fa-clock"></i>
            <span>Run Current Time Scan</span>
          </button>
        </div>
      </div>

      <!-- Quick Preset Simulation Buttons -->
      <div class="mt-4 pt-4 border-t border-slate-800/80 flex flex-wrap items-center gap-2 text-xs">
        <span class="text-slate-400 text-xs font-semibold mr-1">Quick Presets:</span>
        <button onclick="setSimPreset('21-Aug-2026 08:30 am')" class="px-2.5 py-1 rounded-lg bg-slate-800/60 hover:bg-slate-700 text-slate-300 border border-slate-700/60">08:30 AM (Triggers Ramesh - 9:00 AM)</button>
        <button onclick="setSimPreset('21-Aug-2026 09:15 am')" class="px-2.5 py-1 rounded-lg bg-slate-800/60 hover:bg-slate-700 text-slate-300 border border-slate-700/60">09:15 AM (Triggers Suresh - 9:45 AM)</button>
        <button onclick="setSimPreset('21-Aug-2026 10:00 am')" class="px-2.5 py-1 rounded-lg bg-slate-800/60 hover:bg-slate-700 text-slate-300 border border-slate-700/60">10:00 AM (Triggers Amit - 10:30 AM)</button>
        <button onclick="setSimPreset('21-Aug-2026 10:45 am')" class="px-2.5 py-1 rounded-lg bg-slate-800/60 hover:bg-slate-700 text-slate-300 border border-slate-700/60">10:45 AM (Triggers Vikram - 11:15 AM)</button>
        <button onclick="setSimPreset('21-Aug-2026 11:30 am')" class="px-2.5 py-1 rounded-lg bg-slate-800/60 hover:bg-slate-700 text-slate-300 border border-slate-700/60">11:30 AM (Triggers Rajesh - 12:00 PM)</button>
      </div>
    </div>

    <!-- Main Content Area: Rides Table & Audio Sample -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      
      <!-- Rides Table (2 Cols) -->
      <div class="lg:col-span-2 space-y-4">
        <div class="glass-card rounded-2xl p-6 shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h2 class="text-base font-bold text-white flex items-center gap-2">
                <i class="fa-solid fa-list-check text-sky-400"></i>
                <span>Driver Scheduled Rides</span>
              </h2>
              <p class="text-xs text-slate-400">Real-time status synchronization with sheet/CSV</p>
            </div>
            <button onclick="openAddModal()" class="px-3 py-1.5 rounded-lg bg-sky-600/20 hover:bg-sky-600/30 text-sky-400 border border-sky-500/30 text-xs font-semibold transition flex items-center space-x-1.5">
              <i class="fa-solid fa-plus"></i>
              <span>Add Ride</span>
            </button>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
              <thead>
                <tr class="border-b border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  <th class="py-3 px-3">Driver</th>
                  <th class="py-3 px-3">Pickup Location</th>
                  <th class="py-3 px-3">Pickup Time</th>
                  <th class="py-3 px-3">Status</th>
                  <th class="py-3 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody id="ridesTableBody" class="divide-y divide-slate-800/60 text-xs">
                <tr><td colspan="5" class="py-8 text-center text-slate-500">Loading rides...</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Voice Message Script Preview & Audio Test -->
        <div class="glass-card rounded-2xl p-6 space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-bold text-white flex items-center gap-2">
              <i class="fa-solid fa-microphone-lines text-indigo-400"></i>
              <span>TwiML Voice Reminder Script Preview</span>
            </h3>
            <button onclick="playVoicePreview()" class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md transition flex items-center space-x-1.5">
              <i class="fa-solid fa-volume-high"></i>
              <span>Listen TTS Sample</span>
            </button>
          </div>
          <div class="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-300 font-mono leading-relaxed">
            <p class="text-indigo-300 mb-1 font-sans font-semibold">🔊 Exact message spoken to driver upon answering:</p>
            "Hello <span class="text-sky-400 font-bold">{Driver Name}</span>. This is an automated reminder from Mr. Cabie dispatch. You have a scheduled pickup at <span class="text-sky-400 font-bold">{Pickup Location}</span> in 30 minutes. Please do two things now: First, call or message your customer to confirm the pickup. Second, start heading towards {Pickup Location} so you arrive on time. Thank you and drive safely!"
          </div>
        </div>
      </div>

      <!-- Right Column: Live Call Logs & Activity Feed -->
      <div class="space-y-4">
        <div class="glass-card rounded-2xl p-6 shadow-sm h-full flex flex-col">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h2 class="text-base font-bold text-white flex items-center gap-2">
                <i class="fa-solid fa-clock-rotate-left text-emerald-400"></i>
                <span>Live Call Activity Log</span>
              </h2>
              <p class="text-xs text-slate-400">Outbound dispatch events</p>
            </div>
          </div>

          <div id="callLogsContainer" class="space-y-3 flex-1 overflow-y-auto max-h-[520px] pr-1">
            <div class="p-4 rounded-xl bg-slate-950/40 border border-slate-800 text-center text-xs text-slate-500">
              No calls dispatched yet in this session.
            </div>
          </div>
        </div>
      </div>

    </div>
  </main>

  <!-- Add Ride Modal -->
  <div id="addModal" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm hidden items-center justify-center p-4">
    <div class="glass-card max-w-md w-full rounded-2xl p-6 space-y-4 border border-slate-700 bg-slate-900 shadow-2xl">
      <div class="flex items-center justify-between">
        <h3 class="text-base font-bold text-white">Add Scheduled Ride</h3>
        <button onclick="closeAddModal()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
      </div>

      <div class="space-y-3 text-xs">
        <div>
          <label class="block text-slate-400 font-semibold mb-1">Driver Name</label>
          <input id="newDriverName" type="text" placeholder="e.g. Sunil Kumar" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-sky-500" />
        </div>
        <div>
          <label class="block text-slate-400 font-semibold mb-1">Driver Phone Number</label>
          <input id="newDriverPhone" type="text" placeholder="e.g. +91 98765 00000" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-sky-500" />
        </div>
        <div>
          <label class="block text-slate-400 font-semibold mb-1">Pickup Location</label>
          <input id="newPickupLoc" type="text" placeholder="e.g. Terminal 3, IGI Airport" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-sky-500" />
        </div>
        <div>
          <label class="block text-slate-400 font-semibold mb-1">Scheduled Pickup Time</label>
          <input id="newPickupTime" type="text" placeholder="e.g. 21-Aug-2026 02:30 pm" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-sky-500" />
        </div>
      </div>

      <div class="flex justify-end space-x-2 pt-2">
        <button onclick="closeAddModal()" class="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-semibold hover:bg-slate-700">Cancel</button>
        <button onclick="submitNewRide()" class="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-md">Add Ride</button>
      </div>
    </div>
  </div>

  <script>
    async function loadConfig() {
      try {
        const res = await fetch('/api/config-status');
        const data = await res.json();
        const badge = document.getElementById('twilioBadge');
        const dot = document.getElementById('twilioDot');
        const text = document.getElementById('twilioText');
        
        badge.classList.remove('hidden');
        if (data.twilio_configured) {
          dot.className = 'w-2 h-2 rounded-full bg-emerald-400 pulse-dot';
          text.innerHTML = `Twilio Live (${data.twilio_phone_number})`;
          text.className = 'text-emerald-300';
        } else {
          dot.className = 'w-2 h-2 rounded-full bg-amber-400';
          text.innerHTML = 'Twilio: Simulation Mode (Ready)';
          text.className = 'text-amber-300';
        }
      } catch (err) {
        console.error('Config load error', err);
      }
    }

    async function refreshData() {
      try {
        const res = await fetch('/api/rides');
        const rides = await res.json();
        renderRides(rides);
        updateStats(rides);
        await loadCallLogs();
      } catch (err) {
        console.error('Refresh error', err);
      }
    }

    function updateStats(rides) {
      document.getElementById('statTotalRides').innerText = rides.length;
      const sentCount = rides.filter(r => r.reminder_status.includes('Sent') || r.reminder_status.includes('Completed') || r.reminder_status.includes('Call Placed')).length;
      const pendingCount = rides.filter(r => r.reminder_status === 'Pending').length;
      document.getElementById('statSentRides').innerText = sentCount;
      document.getElementById('statPendingRides').innerText = pendingCount;
    }

    function renderRides(rides) {
      const tbody = document.getElementById('ridesTableBody');
      if (!rides || rides.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="py-8 text-center text-slate-500">No scheduled rides found.</td></tr>';
        return;
      }

      tbody.innerHTML = rides.map(r => {
        let statusBadge = '';
        const st = r.reminder_status || 'Pending';
        if (st.includes('Sent') || st.includes('Completed') || st.includes('Call Placed')) {
          statusBadge = `<span class="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><i class="fa-solid fa-check mr-1"></i>${st}</span>`;
        } else if (st.includes('Triggering') || st.includes('In Call')) {
          statusBadge = `<span class="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20"><i class="fa-solid fa-spinner fa-spin mr-1"></i>${st}</span>`;
        } else if (st.includes('Failed') || st.includes('Busy') || st.includes('No Answer')) {
          statusBadge = `<span class="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-red-500/10 text-red-400 border border-red-500/20"><i class="fa-solid fa-triangle-exclamation mr-1"></i>${st}</span>`;
        } else {
          statusBadge = `<span class="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-slate-700/50 text-slate-300 border border-slate-600/50"><i class="fa-solid fa-hourglass-start mr-1"></i>Pending</span>`;
        }

        return `
          <tr class="hover:bg-slate-800/40 transition">
            <td class="py-3.5 px-3">
              <div class="font-bold text-white">${r.driver_name}</div>
              <div class="text-[11px] text-slate-400 flex items-center gap-1"><i class="fa-solid fa-phone text-slate-500 text-[10px]"></i> ${r.driver_phone}</div>
            </td>
            <td class="py-3.5 px-3 text-slate-300 font-medium">
              <div class="flex items-center gap-1.5">
                <i class="fa-solid fa-location-dot text-rose-400 text-xs"></i>
                <span>${r.pickup_location}</span>
              </div>
            </td>
            <td class="py-3.5 px-3">
              <div class="font-mono text-slate-200 font-medium">${r.scheduled_pickup_time_raw}</div>
            </td>
            <td class="py-3.5 px-3">${statusBadge}</td>
            <td class="py-3.5 px-3 text-right">
              <button onclick="triggerManualCall(${r.id})" class="px-2.5 py-1 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-[11px] font-bold shadow-sm transition">
                <i class="fa-solid fa-phone mr-1"></i> Call Now
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }

    async function loadCallLogs() {
      try {
        const res = await fetch('/api/call-logs');
        const logs = await res.json();
        const container = document.getElementById('callLogsContainer');
        if (!logs || logs.length === 0) {
          container.innerHTML = '<div class="p-4 rounded-xl bg-slate-950/40 border border-slate-800 text-center text-xs text-slate-500">No calls dispatched yet.</div>';
          return;
        }

        container.innerHTML = logs.map(l => `
          <div class="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1.5">
            <div class="flex items-center justify-between text-xs">
              <span class="font-bold text-white flex items-center gap-1.5">
                <i class="fa-solid fa-phone-volume text-sky-400"></i> ${l.driver_name}
              </span>
              <span class="px-2 py-0.5 rounded text-[10px] font-semibold ${l.status === 'completed' || l.status === 'initiated' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}">
                ${l.status}
              </span>
            </div>
            <div class="text-[11px] text-slate-400">${l.notes}</div>
            <div class="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-900">
              <span>${l.timestamp}</span>
              <span class="font-mono text-slate-600">${l.call_sid ? l.call_sid.substring(0, 12) + '...' : ''}</span>
            </div>
          </div>
        `).join('');
      } catch (err) {
        console.error('Call logs error', err);
      }
    }

    function showToast(title, msg, type = 'info') {
      const toast = document.createElement('div');
      const bg = type === 'success' ? 'bg-emerald-900/90 border-emerald-500/50 text-emerald-200' : 'bg-slate-800/95 border-sky-500/50 text-slate-200';
      toast.className = `fixed bottom-6 right-6 z-50 p-4 rounded-xl shadow-2xl border backdrop-blur-md max-w-sm transition-all duration-300 transform translate-y-0 opacity-100 ${bg}`;
      toast.innerHTML = `
        <div class="font-bold text-xs flex items-center gap-2 mb-1">
          <i class="fa-solid fa-circle-info"></i>
          <span>${title}</span>
        </div>
        <div class="text-[11px] text-slate-300">${msg}</div>
      `;
      document.body.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 400);
      }, 3500);
    }

    async function triggerManualCall(rideId) {
      try {
        const res = await fetch(`/api/rides/trigger/${rideId}`, { method: 'POST' });
        const data = await res.json();
        showToast('Call Dispatched', `Reminder call initiated for Ride #${rideId}`, 'success');
        await refreshData();
      } catch (err) {
        showToast('Error', 'Failed to trigger call: ' + err, 'error');
      }
    }

    async function runAgentScan(useSimulatedTime) {
      try {
        const simTime = useSimulatedTime ? document.getElementById('simTimeInput').value : null;
        const res = await fetch('/api/agent/run-scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ simulated_time: simTime })
        });
        const result = await res.json();
        showToast('Scan Completed', `Checked ${result.total_rides_checked} rides. Dispatched ${result.reminders_triggered} reminder(s).`, 'success');
        await refreshData();
      } catch (err) {
        showToast('Scan Error', err.toString(), 'error');
      }
    }

    function setSimPreset(timeStr) {
      document.getElementById('simTimeInput').value = timeStr;
      runAgentScan(true);
    }

    async function resetData() {
      await fetch('/api/rides/reset', { method: 'POST' });
      showToast('Data Reset', 'Rides table restored to initial prompt sample rows.', 'info');
      await refreshData();
    }

    function playVoicePreview() {
      const text = "Hello Ramesh Kumar. This is an automated reminder from Mr. Cabie dispatch. You have a scheduled pickup at DLF Cyber City, Gurugram in 30 minutes. Please call or message your customer to confirm the pickup, and head to the pickup location on time. Thank you and drive safely!";
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.95;
        window.speechSynthesis.speak(utterance);
        showToast('Voice Preview', 'Playing synthesized voice message sample...', 'info');
      } else {
        showToast('Voice Preview', text, 'info');
      }
    }

    function openAddModal() { document.getElementById('addModal').classList.remove('hidden'); document.getElementById('addModal').classList.add('flex'); }
    function closeAddModal() { document.getElementById('addModal').classList.add('hidden'); document.getElementById('addModal').classList.remove('flex'); }

    async function submitNewRide() {
      const name = document.getElementById('newDriverName').value;
      const phone = document.getElementById('newDriverPhone').value;
      const loc = document.getElementById('newPickupLoc').value;
      const time = document.getElementById('newPickupTime').value;

      if (!name || !time) {
        alert('Please provide at least a driver name and pickup time.');
        return;
      }

      await fetch('/api/rides/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          driver_name: name,
          driver_phone: phone,
          pickup_location: loc,
          scheduled_pickup_time: time
        })
      });

      closeAddModal();
      await refreshData();
    }

    // Auto-refresh every 10s
    window.addEventListener('DOMContentLoaded', async () => {
      await loadConfig();
      await refreshData();
      setInterval(refreshData, 10000);
    });
  </script>
</body>
</html>
    """
