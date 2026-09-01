"""
================================================================================
WanderBot — DEMO: Structured Outputs with Pydantic
================================================================================
"""

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("WanderBot.StructuredOutputs")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "datasets"
FLIGHTS_FILE = DATA_DIR / "flights_broken.json"

app = BedrockAgentCoreApp()

MODEL_ID = "us.amazon.nova-2-lite-v1:0"
model = BedrockModel(model_id=MODEL_ID)

SYSTEM_PROMPT = """You are WanderBot, the AI travel assistant for Horizon Travel.

AVAILABLE TOOLS
1. search_flights — Search Horizon Travel flights by route and date

GUIDELINES
- Always use tools to fetch real data instead of guessing
- When a customer asks about flights, use search_flights with the correct IATA codes
- Be concise, structured, and helpful

IATA CODE QUICK REFERENCE
LHR = London Heathrow | CDG = Paris Charles de Gaulle | JFK = New York JFK
MIA = Miami | LAX = Los Angeles | BCN = Barcelona | FCO = Rome Fiumicino"""


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================

class FlightSearchInput(BaseModel):
    """Validated input for a flight search query."""
    origin: str = Field(description="IATA departure airport code, e.g. LHR")
    destination: str = Field(description="IATA arrival airport code, e.g. CDG")
    date: str = Field(description="Travel date in YYYY-MM-DD format, e.g. 2026-03-15")


class FlightOption(BaseModel):
    """A single validated flight result."""
    flight_number: str = Field(description="Flight code, e.g. HZ-101")
    origin: str = Field(description="IATA departure airport code")
    destination: str = Field(description="IATA arrival airport code")
    date: str = Field(description="Flight date in YYYY-MM-DD format")
    departure_time: str = Field(description="Departure time, e.g. 08:30")
    arrival_time: str = Field(description="Arrival time, e.g. 10:45")
    price_usd: float = Field(description="Ticket price in US dollars")
    available_seats: int = Field(ge=0, description="Number of seats remaining")
    status: str = Field(description="Flight status: SCHEDULED, DELAYED, or CANCELLED")
    cabin_class: Optional[str] = Field(default=None, description="Cabin class, e.g. Economy")
    aircraft: Optional[str] = Field(default=None, description="Aircraft type, e.g. A320neo")
    gate: Optional[str] = Field(default=None, description="Departure gate, e.g. B14")


class FlightSearchResult(BaseModel):
    """Validated response containing all matching flights."""
    flights: list[FlightOption] = Field(description="List of matching flights")
    total: int = Field(description="Total number of flights found")


# ===========================================================================
# TOOL — with Pydantic validation
# ===========================================================================

@tool
def search_flights(origin: str, destination: str, date: str) -> str:
    """
    Search for available Horizon Travel flights between two airports on a specific date.

    Use this tool when a customer asks about flight availability, times, or prices.

    Args:
        origin      : IATA departure airport code (e.g. 'LHR', 'JFK')
        destination : IATA arrival airport code (e.g. 'CDG', 'MIA')
        date        : Travel date in YYYY-MM-DD format (e.g. '2026-03-15')

    Returns:
        JSON string with validated flight results.
    """
    # --- Validate input ---
    try:
        validated_input = FlightSearchInput(
            origin=origin,
            destination=destination,
            date=date,
        )
    except ValidationError as e:
        logger.error("Input validation failed: %s", e)
        return json.dumps({"error": "Invalid search parameters", "details": str(e)})

    logger.info(
        "search_flights called: %s → %s on %s",
        validated_input.origin, validated_input.destination, validated_input.date,
    )

    # --- Load data ---
    try:
        with open(FLIGHTS_FILE, encoding="utf-8") as f:
            flights = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Failed to load flights data: %s", e)
        return json.dumps({"error": "Flight database unavailable"})

    # --- Filter ---
    matches = [
        fl for fl in flights
        if fl.get("origin", "").upper() == validated_input.origin.upper()
        and fl.get("destination", "").upper() == validated_input.destination.upper()
        and fl.get("date", "") == validated_input.date
    ]

    # --- Validate each flight record ---
    validated_flights = []
    for fl in matches:
        try:
            validated_flights.append(FlightOption.model_validate(fl))
        except ValidationError as e:
            logger.warning("Skipping invalid flight record %s: %s", fl.get("flight_number", "?"), e)

    result = FlightSearchResult(flights=validated_flights, total=len(validated_flights))
    return result.model_dump_json(indent=2)


# ===========================================================================
# ENTRY POINT
# ===========================================================================

@app.entrypoint
async def invoke(payload, context=None):
    """WanderBot — Structured Outputs entry point."""
    user_message = payload.get("message", "Hello!")
    logger.info("User: %s", user_message[:100])

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[search_flights],
    )

    response = agent(user_message)
    return response


if __name__ == "__main__":
    app.run()