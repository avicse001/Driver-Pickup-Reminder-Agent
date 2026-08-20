"""
Single-command test call script for Mr. Cabie Driver Pickup Reminder Agent.
Usage:
    python make_test_call.py --phone "+919876543210" --name "Ramesh Kumar" --location "DLF Cyber City"
"""

import argparse
import config
from twilio_service import TwilioService, generate_twiml

def main():
    parser = argparse.ArgumentParser(description="Place a test driver reminder call via Twilio")
    parser.add_argument("--phone", type=str, default=config.TEST_DRIVER_PHONE or "+919876543210", help="Destination phone number (E.164 format e.g. +91XXXXXXXXXX)")
    parser.add_argument("--name", type=str, default="Ramesh Kumar", help="Driver name")
    parser.add_argument("--location", type=str, default="DLF Cyber City, Gurugram", help="Pickup location")
    parser.add_argument("--mock", action="store_true", help="Force mock/simulation mode")

    args = parser.parse_args()

    print("==================================================")
    print("[CALL DISPATCHER] Mr. Cabie - Driver Test Call Dispatcher")
    print("==================================================")
    print(f"Driver Name:     {args.name}")
    print(f"Target Phone:    {args.phone}")
    print(f"Pickup Location: {args.location}")
    print("--------------------------------------------------")

    service = TwilioService()
    print(f"Twilio Mode:     {'[LIVE] Twilio' if (service.is_configured and not args.mock) else '[SIMULATION] Mock Twilio'}")

    if not service.is_configured and not args.mock:
        print("\n[NOTE] Twilio credentials not detected in .env. Running in simulation mode.")
        print("To place a real call to your phone:")
        print("1. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER in .env")
        print("2. Run: python make_test_call.py --phone \"<YOUR_VERIFIED_PHONE>\"\n")

    print(f"Dispatching call to {args.phone}...")
    res = service.trigger_reminder_call(
        driver_name=args.name,
        to_phone=args.phone,
        pickup_location=args.location,
        force_mock=args.mock
    )

    print("\n--- Call Result ---")
    if res.get("success"):
        print(f"[SUCCESS] {res.get('message')}")
        print(f"   Call SID: {res.get('call_sid')}")
        print(f"   Status:   {res.get('status')}")
    else:
        print(f"[FAILED]  {res.get('error')}")

    print("\n--- Spoken TwiML Message ---")
    print(generate_twiml(args.name, args.location))
    print("==================================================")

if __name__ == "__main__":
    main()
