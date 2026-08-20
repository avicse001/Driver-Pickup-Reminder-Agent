import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import config

# In-memory log of calls for real-time visibility and debugging
CALL_LOGS: List[Dict[str, Any]] = []

def generate_twiml(driver_name: str, pickup_location: str) -> str:
    """
    Generate TwiML XML string with a clear, professional text-to-speech message.
    """
    response = VoiceResponse()
    
    # Friendly greeting and instructions
    message = (
        f"Hello {driver_name}. This is an automated reminder from Mr. Cabie dispatch. "
        f"You have a scheduled pickup at {pickup_location} in 30 minutes. "
        f"Please do two things now: First, call or message your customer to confirm the pickup. "
        f"Second, start heading towards {pickup_location} so you arrive on time. "
        f"Thank you and drive safely!"
    )
    
    # Use high-quality neural/poly voice with gentle pause
    response.say(message, voice="Polly.Aditi", language="en-IN")
    response.pause(length=1)
    response.say(f"Repeating: Please confirm with the customer and proceed to {pickup_location}. Goodbye.", voice="Polly.Aditi", language="en-IN")
    
    return str(response)

class TwilioService:
    def __init__(self):
        self.is_configured = config.is_twilio_configured()
        self.client = None
        if self.is_configured:
            try:
                self.client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
            except Exception as e:
                print(f"[TwilioService] Initialization error: {e}")
                self.is_configured = False

    def trigger_reminder_call(
        self,
        driver_name: str,
        to_phone: str,
        pickup_location: str,
        ride_id: Optional[int] = None,
        force_mock: bool = False
    ) -> Dict[str, Any]:
        """
        Triggers an outbound call to the driver's phone number.
        If Twilio credentials are not set or force_mock is True, simulates the call with realistic logs.
        """
        # If test phone is configured (e.g. verified Twilio trial number), prioritize it for testing
        target_phone = config.TEST_DRIVER_PHONE if config.TEST_DRIVER_PHONE else to_phone
        # Clean phone number (remove spaces, hyphens)
        clean_phone = target_phone.replace(" ", "").replace("-", "")
        if not clean_phone.startswith("+"):
            clean_phone = "+" + clean_phone

        twiml_content = generate_twiml(driver_name, pickup_location)
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")

        if self.is_configured and not force_mock:
            try:
                # Prepare call parameters
                call_kwargs = {
                    "to": clean_phone,
                    "from_": config.TWILIO_PHONE_NUMBER,
                    "twiml": twiml_content,
                }
                
                # If webhook base URL is available, configure status callback
                if config.BASE_WEBHOOK_URL:
                    call_kwargs["status_callback"] = f"{config.BASE_WEBHOOK_URL}/api/twilio/call-status"
                    call_kwargs["status_callback_event"] = ["initiated", "ringing", "answered", "completed"]
                    call_kwargs["status_callback_method"] = "POST"

                print(f"[TwilioService] Dispatching live call to {clean_phone} for driver '{driver_name}'...")
                call = self.client.calls.create(**call_kwargs)

                log_entry = {
                    "call_sid": call.sid,
                    "ride_id": ride_id,
                    "driver_name": driver_name,
                    "driver_phone": clean_phone,
                    "pickup_location": pickup_location,
                    "status": call.status or "initiated",
                    "timestamp": timestamp,
                    "mode": "Live Twilio Call",
                    "notes": f"Outbound call placed (SID: {call.sid})"
                }
                CALL_LOGS.insert(0, log_entry)

                return {
                    "success": True,
                    "call_sid": call.sid,
                    "status": call.status or "initiated",
                    "mode": "live",
                    "message": f"Live call initiated to {clean_phone} (SID: {call.sid})"
                }
            except Exception as e:
                error_msg = str(e)
                print(f"[TwilioService] Error calling {clean_phone}: {error_msg}")
                log_entry = {
                    "call_sid": f"ERR-{uuid.uuid4().hex[:8].upper()}",
                    "ride_id": ride_id,
                    "driver_name": driver_name,
                    "driver_phone": clean_phone,
                    "pickup_location": pickup_location,
                    "status": "failed",
                    "timestamp": timestamp,
                    "mode": "Live Twilio Error",
                    "notes": f"Call failed: {error_msg}"
                }
                CALL_LOGS.insert(0, log_entry)
                return {
                    "success": False,
                    "call_sid": log_entry["call_sid"],
                    "status": "failed",
                    "mode": "live",
                    "error": error_msg
                }
        else:
            # Simulated Call for local testing / offline verification
            mock_sid = f"CA{uuid.uuid4().hex.upper()}"
            print(f"[TwilioService: SIMULATION] Outbound call simulated to {clean_phone} for '{driver_name}'.")
            print(f"   [Message Spoken]: \"Hello {driver_name}, pickup at {pickup_location} in 30 mins...\"")

            log_entry = {
                "call_sid": mock_sid,
                "ride_id": ride_id,
                "driver_name": driver_name,
                "driver_phone": clean_phone,
                "pickup_location": pickup_location,
                "status": "completed",
                "timestamp": timestamp,
                "mode": "Simulation (Mock Twilio)",
                "notes": "Voice reminder played successfully (Simulated)"
            }
            CALL_LOGS.insert(0, log_entry)

            return {
                "success": True,
                "call_sid": mock_sid,
                "status": "completed",
                "mode": "simulation",
                "message": f"Simulated call to {clean_phone} completed (Mock SID: {mock_sid})"
            }

def get_call_logs() -> List[Dict[str, Any]]:
    """Return all recorded call logs."""
    return CALL_LOGS
