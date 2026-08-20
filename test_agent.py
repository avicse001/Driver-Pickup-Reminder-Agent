import unittest
import os
from datetime import datetime, timedelta
from data_manager import DataManager, parse_pickup_datetime, Ride
from twilio_service import TwilioService, generate_twiml
from reminder_agent import ReminderAgent

TEST_CSV = "test_rides.csv"

class TestReminderAgent(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_CSV):
            os.remove(TEST_CSV)
        self.data_mgr = DataManager(csv_path=TEST_CSV)
        self.twilio = TwilioService()
        self.agent = ReminderAgent(data_manager=self.data_mgr, twilio_service=self.twilio)

    def tearDown(self):
        if os.path.exists(TEST_CSV):
            os.remove(TEST_CSV)

    def test_datetime_parsing(self):
        # Format in prompt: "21-Aug-2026 09:00 am"
        dt1 = parse_pickup_datetime("21-Aug-2026 09:00 am")
        self.assertIsNotNone(dt1)
        self.assertEqual(dt1.year, 2026)
        self.assertEqual(dt1.month, 8)
        self.assertEqual(dt1.day, 21)
        self.assertEqual(dt1.hour, 9)
        self.assertEqual(dt1.minute, 0)

        # Standard formats
        dt2 = parse_pickup_datetime("2026-08-21 14:30")
        self.assertIsNotNone(dt2)
        self.assertEqual(dt2.hour, 14)
        self.assertEqual(dt2.minute, 30)

    def test_30_min_reminder_window_matching(self):
        # Scenario: Simulated current time is 21-Aug-2026 08:30 am
        # Ramesh Kumar's ride is at 21-Aug-2026 09:00 am (exactly 30 minutes away)
        sim_time = datetime(2026, 8, 21, 8, 30)
        due_rides = self.data_mgr.get_due_rides(current_time=sim_time, window_minutes=30, tolerance_minutes=5)
        
        self.assertEqual(len(due_rides), 1)
        self.assertEqual(due_rides[0].driver_name, "Ramesh Kumar")

    def test_duplicate_prevention(self):
        sim_time = datetime(2026, 8, 21, 8, 30)
        # First scan triggers reminder for Ramesh
        res1 = self.agent.check_and_trigger_reminders(current_time=sim_time, force_mock=True)
        self.assertEqual(res1["reminders_triggered"], 1)

        # Verify status in sheet was updated to Reminder Sent
        rides = self.data_mgr.load_rides()
        ramesh = next(r for r in rides if r.driver_name == "Ramesh Kumar")
        self.assertEqual(ramesh.reminder_status, "Reminder Sent")
        self.assertTrue(len(ramesh.call_sid) > 0)

        # Second scan at same or slightly later time (e.g. 8:31 AM) should NOT trigger again
        sim_time2 = datetime(2026, 8, 21, 8, 31)
        res2 = self.agent.check_and_trigger_reminders(current_time=sim_time2, force_mock=True)
        self.assertEqual(res2["reminders_triggered"], 0)

    def test_twiml_generation(self):
        twiml = generate_twiml("Amit Sharma", "DLF Cyber City")
        self.assertIn("<Say", twiml)
        self.assertIn("Amit Sharma", twiml)
        self.assertIn("DLF Cyber City", twiml)
        self.assertIn("30 minutes", twiml)

if __name__ == "__main__":
    unittest.main()
