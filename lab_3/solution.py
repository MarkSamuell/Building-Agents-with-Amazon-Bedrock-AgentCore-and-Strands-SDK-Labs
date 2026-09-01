"""
================================================================================
WanderBot — EXERCISE SOLUTION: Structured Outputs with Pydantic
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

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("WanderBot.StructuredOutputs")

# ---------------------------------------------------------------------------
# Dataset paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "datasets"
HOTELS_FILE = DATA_DIR / "hotels_broken.json"

# ---------------------------------------------------------------------------
# AgentCore app
# ---------------------------------------------------------------------------
app = BedrockAgentCoreApp()

MODEL_ID = "us.amazon.nova-2-lite-v1:0"
model = BedrockModel(model_id=MODEL_ID)

SYSTEM_PROMPT = """You are WanderBot, the AI travel assistant for Horizon Travel.

AVAILABLE TOOLS
1. search_hotels — Find available hotels in a city by price

GUIDELINES
- Always use tools to fetch real data instead of guessing
- When a customer asks about hotels, use search_hotels with the city name
- Be concise, structured, and helpful"""


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================

class HotelSearchInput(BaseModel):
    """Validated input for a hotel search query."""
    city: str = Field(description="Name of the destination city, e.g. 'Barcelona'")
    max_price_usd: float = Field(description="Maximum price per night in USD, e.g. 200.0")


class HotelOption(BaseModel):
    """A single validated hotel result."""
    hotel_id: str = Field(description="Hotel identifier, e.g. 'HT-BCN-001'")
    name: str = Field(description="Hotel name, e.g. 'Hotel Casa Marina'")
    city: str = Field(description="City where the hotel is located, e.g. 'Barcelona'")
    star_rating: int = Field(ge=1, le=5, description="Star rating from 1 to 5")
    price_per_night_usd: float = Field(ge=0, description="Price per night in US dollars")
    available: bool = Field(description="Whether the hotel has availability")
    room_types: list[str] = Field(description="Available room types, e.g. ['Standard', 'Deluxe']")
    amenities: list[str] = Field(description="Hotel amenities, e.g. ['Pool', 'Spa']")
    check_in_time: Optional[str] = Field(default=None, description="Check-in time, e.g. '15:00'")
    check_out_time: Optional[str] = Field(default=None, description="Check-out time, e.g. '11:00'")
    cancellation_policy: Optional[str] = Field(default=None, description="Cancellation policy description")


class HotelSearchResult(BaseModel):
    """Validated response containing all matching hotels."""
    hotels: list[HotelOption] = Field(description="List of matching hotels")
    total: int = Field(description="Total number of hotels found")


# ===========================================================================
# TOOL — search_hotels with Pydantic validation
# ===========================================================================

@tool
def search_hotels(city: str, max_price_usd: float = 9999.0) -> str:
    """
    Search for available hotels in a destination city, with optional price filtering.

    Use this tool when a customer asks about hotel availability, prices, or amenities.

    Args:
        city          : Name of the destination city (e.g. 'Barcelona', 'Tokyo')
        max_price_usd : Maximum price per night in USD (default: 9999.0 for no limit)

    Returns:
        JSON string with validated hotel results.
    """
    # --- Validate input ---
    try:
        validated_input = HotelSearchInput(
            city=city,
            max_price_usd=max_price_usd,
        )
    except ValidationError as e:
        logger.error("Input validation failed: %s", e)
        return json.dumps({"error": "Invalid search parameters", "details": str(e)})

    logger.info(
        "search_hotels called: city=%s, max=$%.0f",
        validated_input.city, validated_input.max_price_usd,
    )

    # --- Load data ---
    try:
        with open(HOTELS_FILE, encoding="utf-8") as f:
            hotels = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Failed to load hotels data: %s", e)
        return json.dumps({"error": "Hotel database unavailable"})

    # --- Filter by city and availability only ---
    city_normalised = validated_input.city.strip().title()
    matches = [
        h for h in hotels
        if h.get("city", "").lower() == city_normalised.lower()
        and h.get("available", False)
    ]

    # --- Validate each hotel record, then apply price filter ---
    validated_hotels = []
    for h in matches:
        try:
            hotel = HotelOption.model_validate(h)
            if hotel.price_per_night_usd <= validated_input.max_price_usd:
                validated_hotels.append(hotel)
        except ValidationError as e:
            logger.warning("Skipping invalid hotel record %s: %s", h.get("hotel_id", "?"), e)

    result = HotelSearchResult(hotels=validated_hotels, total=len(validated_hotels))
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
        tools=[search_hotels],
    )

    response = agent(user_message)
    return response


if __name__ == "__main__":
    app.run()