import time
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional
import schedule
from data_manager import DataManager, Ride, parse_pickup_datetime
from twilio_service import TwilioService
import config

class ReminderAgent:
    def __init__(self, data_manager: Optional[DataManager] = None, twilio_service: Optional[TwilioService] = None):
        self.data_mgr = data_manager or DataManager()
        self.twilio = twilio_service or TwilioService()

    def check_and_trigger_reminders(
        self,
        current_time: Optional[datetime] = None,
        dry_run: bool = False,
        force_mock: bool = False
    ) -> Dict[str, Any]:
        """
        Scans all scheduled rides, identifies rides 30 minutes away,
        and triggers outbound voice reminders for un-reminded rides.
        """
        if current_time is None:
            current_time = datetime.now()

        due_rides = self.data_mgr.get_due_rides(
            current_time=current_time,
            window_minutes=config.REMINDER_WINDOW_MINUTES,
            tolerance_minutes=config.WINDOW_TOLERANCE_MINUTES
        )

        all_rides = self.data_mgr.load_rides()
        results = []

        print(f"\n[{current_time.strftime('%Y-%m-%d %I:%M:%S %p')}] Scanning scheduled rides...")
        print(f"Total rides found: {len(all_rides)} | Due for 30-min reminder: {len(due_rides)}")

        for ride in due_rides:
            lead_mins = ride.get_minutes_until(current_time)
            print(f" -> Found match: Driver '{ride.driver_name}' (Phone: {ride.driver_phone}) | Location: {ride.pickup_location} | Pickup in {lead_mins} mins")

            if dry_run:
                results.append({
                    "ride_id": ride.id,
                    "driver_name": ride.driver_name,
                    "action": "dry_run_skipped",
                    "minutes_until": lead_mins
                })
                continue

            # Mark as Initiated/Triggered before making the call to prevent race condition duplicates
            self.data_mgr.update_ride_status(ride.id, "Triggering Call...", notes="Dispatching reminder call")

            call_res = self.twilio.trigger_reminder_call(
                driver_name=ride.driver_name,
                to_phone=ride.driver_phone,
                pickup_location=ride.pickup_location,
                ride_id=ride.id,
                force_mock=force_mock
            )

            if call_res.get("success"):
                new_status = "Reminder Sent" if call_res.get("mode") == "simulation" else "Call Placed"
                notes = f"Call triggered successfully ({call_res.get('mode')})"
                self.data_mgr.update_ride_status(
                    ride_id=ride.id,
                    status=new_status,
                    call_sid=call_res.get("call_sid", ""),
                    notes=notes
                )
            else:
                self.data_mgr.update_ride_status(
                    ride_id=ride.id,
                    status="Failed",
                    call_sid=call_res.get("call_sid", ""),
                    notes=f"Error: {call_res.get('error')}"
                )

            results.append({
                "ride_id": ride.id,
                "driver_name": ride.driver_name,
                "phone": ride.driver_phone,
                "call_result": call_res,
                "lead_minutes": lead_mins
            })

        return {
            "timestamp": current_time.strftime("%Y-%m-%d %I:%M:%S %p"),
            "total_rides_checked": len(all_rides),
            "due_rides_count": len(due_rides),
            "reminders_triggered": len(results),
            "details": results
        }

    def trigger_single_ride(self, ride_id: int, force_mock: bool = False) -> Dict[str, Any]:
        """Manually trigger a reminder for a specific ride ID."""
        rides = self.data_mgr.load_rides()
        target = next((r for r in rides if r.id == ride_id), None)
        if not target:
            return {"success": False, "error": f"Ride #{ride_id} not found."}

        self.data_mgr.update_ride_status(target.id, "Triggering Call...", notes="Manual dispatch triggered")

        call_res = self.twilio.trigger_reminder_call(
            driver_name=target.driver_name,
            to_phone=target.driver_phone,
            pickup_location=target.pickup_location,
            ride_id=target.id,
            force_mock=force_mock
        )

        status = "Reminder Sent" if call_res.get("success") else "Failed"
        notes = f"Manual trigger ({call_res.get('mode')})"
        self.data_mgr.update_ride_status(
            ride_id=target.id,
            status=status,
            call_sid=call_res.get("call_sid", ""),
            notes=notes
        )

        return {
            "success": call_res.get("success", False),
            "ride": target.to_dict(),
            "call_result": call_res
        }

    def run_daemon(self):
        """Continuously run reminder check in the background on interval."""
        print(f"\n==========================================")
        print(f"[AGENT] Mr. Cabie Driver Pickup Reminder Agent")
        print(f"[POLL]  Polling every {config.POLL_INTERVAL_SECONDS} seconds")
        print(f"[LEAD]  Target reminder lead time: {config.REMINDER_WINDOW_MINUTES} minutes before pickup")
        print(f"[TWILIO] Status: {'Configured (Live Calls)' if self.twilio.is_configured else 'Mock Simulation Mode'}")
        print(f"==========================================\n")

        # Run immediately on start
        self.check_and_trigger_reminders()

        # Schedule recurring job
        schedule.every(config.POLL_INTERVAL_SECONDS).seconds.do(self.check_and_trigger_reminders)

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Agent] Polling daemon stopped by user.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mr. Cabie - Driver Pickup Reminder Agent")
    parser.add_argument("--run-now", action="store_true", help="Perform a single scan with current time")
    parser.add_argument("--daemon", action="store_true", help="Start continuous background polling daemon")
    parser.add_argument("--simulate-time", type=str, help="Simulate a specific time (e.g. '21-Aug-2026 08:30 am')")
    parser.add_argument("--trigger-ride", type=int, help="Manually trigger a reminder for a ride ID")
    parser.add_argument("--reset-data", action="store_true", help="Reset rides data to initial sample")
    parser.add_argument("--force-mock", action="store_true", help="Force simulated calls even if Twilio is configured")

    args = parser.parse_args()
    agent = ReminderAgent()

    if args.reset_data:
        agent.data_mgr.reset_to_default_sample()
        print("Rides data reset to initial sample successfully.")
    elif args.trigger_ride:
        res = agent.trigger_single_ride(args.trigger_ride, force_mock=args.force_mock)
        print(f"Manual Trigger Result: {res}")
    elif args.simulate_time:
        sim_dt = parse_pickup_datetime(args.simulate_time)
        if not sim_dt:
            print(f"Could not parse simulated datetime '{args.simulate_time}'")
        else:
            print(f"Simulating time as: {sim_dt.strftime('%d-%b-%Y %I:%M %p')}")
            res = agent.check_and_trigger_reminders(current_time=sim_dt, force_mock=args.force_mock)
            print(f"Simulation Result: {res}")
    elif args.daemon:
        agent.run_daemon()
    else:
        # Default: run one scan
        res = agent.check_and_trigger_reminders(force_mock=args.force_mock)
        print(f"\nScan completed: {res['reminders_triggered']} reminder(s) triggered out of {res['total_rides_checked']} total rides.")
