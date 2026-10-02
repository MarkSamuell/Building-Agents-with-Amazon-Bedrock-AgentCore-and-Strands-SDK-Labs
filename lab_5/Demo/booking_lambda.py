"""
================================================================================
WanderBot — Lambda: Booking Tools
================================================================================
Function Name : WanderBotBookingTools
Runtime       : Python 3.14

AgentCore Gateway invokes this Lambda directly 
The event format is:
  {
    "booking_ref": "BK-1001"
  }
================================================================================
"""

import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Demo booking data
# ---------------------------------------------------------------------------
BOOKINGS = {
    "BK-1001": {
        "booking_ref": "BK-1001",
        "customer": "Alice Johnson",
        "email": "alice@example.com",
        "flight": "HZ-101",
        "route": "LHR → CDG",
        "date": "2026-03-15",
        "cabin": "Economy Flex",
        "fare_usd": 189.99,
        "status": "CONFIRMED",
    },
    "BK-1002": {
        "booking_ref": "BK-1002",
        "customer": "Alice Johnson",
        "email": "alice@example.com",
        "flight": "HZ-450",
        "route": "BCN → FCO",
        "date": "2026-03-20",
        "cabin": "Economy Lite",
        "fare_usd": 145.00,
        "status": "CONFIRMED",
    },
    "BK-1003": {
        "booking_ref": "BK-1003",
        "customer": "Bob Smith",
        "email": "bob@example.com",
        "flight": "HZ-311",
        "route": "JFK → LAX",
        "date": "2026-03-15",
        "cabin": "Business",
        "fare_usd": 349.00,
        "status": "CONFIRMED",
    },
}


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------

def get_booking(booking_ref: str) -> str:
    booking = BOOKINGS.get(booking_ref.upper())
    if not booking:
        return f"No booking found with reference {booking_ref}."
    return json.dumps(booking)


def list_bookings_by_email(email: str) -> str:
    matches = [b for b in BOOKINGS.values() if b["email"].lower() == email.lower()]
    if not matches:
        return f"No bookings found for {email}."
    return json.dumps({"email": email, "bookings": matches})


# ---------------------------------------------------------------------------
# Lambda handler — AgentCore Gateway direct invocation
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context) -> dict:

    # ── Resolve tool name ─────────────────────────────────────────────────────
    # When invoked via the Gateway, the tool name is in the client context.
    # For direct invocation (e.g. aws lambda invoke), infer from the event keys.
    tool = ""
    try:
        raw_tool = context.client_context.custom.get("bedrockAgentCoreToolName", "")
        tool = raw_tool.split("___", 1)[-1] if "___" in raw_tool else raw_tool
    except (AttributeError, TypeError):
        pass

    # Fallback: infer tool from event keys when no client context is present
    if not tool:
        if "booking_ref" in event:
            tool = "get_booking"
        elif "email" in event:
            tool = "list_bookings_by_email"

    print(f"Tool called: {tool} | Event: {json.dumps(event)}")

    if tool == "get_booking":
        result = get_booking(event.get("booking_ref", ""))
    elif tool == "list_bookings_by_email":
        result = list_bookings_by_email(event.get("email", ""))
    else:
        result = f"Unknown tool: {tool}"


    return {
        "statusCode": 200,
        "body": json.dumps({
            "result":    result
        }),
    }
    