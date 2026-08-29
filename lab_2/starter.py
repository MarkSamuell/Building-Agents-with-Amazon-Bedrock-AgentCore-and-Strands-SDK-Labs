"""
================================================================================
WanderBot — EXERCISE: Function Calling
================================================================================
Topic     : Custom @tool functions + built-in current_time tool
Exercise  : Add four tools to WanderBot: current_time (built-in),
            search_flights, search_hotels, and get_exchange_rate (custom)

EXERCISE INSTRUCTIONS
---------------------
  Step 1: Import `tool` from strands, and `current_time` from strands_tools
  Step 2: Write docstring for `search_flights` tool
  Step 3: Write docstring for `search_hotels` @tool
  Step 4: Write docstring for `get_exchange_rate` @tool
  Step 5: Pass all four tools to the Agent in the @app.entrypoint function
"""

import json
import logging
from pathlib import Path

from bedrock_agentcore.runtime import BedrockAgentCoreApp
# TODO (Step 1): Import `tool` from strands (alongside Agent)
from strands import Agent, tool
from strands import Agent
from strands.models import BedrockModel
# TODO (Step 1): Import `current_time` from strands_tools
from strands_tools import current_time 

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("WanderBot3.StrandsTools")

# ---------------------------------------------------------------------------
# Dataset paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # exercise folder root
DATA_DIR = BASE_DIR / "datasets"

FLIGHTS_FILE = DATA_DIR / "flights.json"
HOTELS_FILE = DATA_DIR / "hotels.json"
EXCHANGE_FILE = DATA_DIR / "exchange_rates.json"

# ---------------------------------------------------------------------------
# AgentCore app
# ---------------------------------------------------------------------------
app = BedrockAgentCoreApp()

MODEL_ID = "us.amazon.nova-2-lite-v1:0"
model = BedrockModel(model_id=MODEL_ID)

SYSTEM_PROMPT = """You are WanderBot, the AI travel assistant for Horizon Travel.

AVAILABLE TOOLS
You have the following tools at your disposal:
1. current_time      — Get the current date and time (UTC)
2. search_flights    — Search Horizon Travel flights by route and date
3. search_hotels     — Find available hotels in a city by price
4. get_exchange_rate — Convert between currencies at current rates

GUIDELINES
- Always use tools to fetch real data instead of guessing
- When a customer asks about flights, use search_flights with the correct IATA codes
- When a customer asks about hotels, use search_hotels with the city name
- For currency questions, use get_exchange_rate with ISO 4217 currency codes
- Chain tools together when needed (e.g., find flights AND hotels in the same city)
- Always indicate the data source in your response (e.g., "According to current availability...")
- Be concise, structured, and helpful

IATA CODE QUICK REFERENCE
LHR = London Heathrow | CDG = Paris Charles de Gaulle | JFK = New York JFK
MIA = Miami | LAX = Los Angeles | BCN = Barcelona | FCO = Rome Fiumicino
SYD = Sydney | NRT = Tokyo Narita | DXB = Dubai | CUN = Cancun"""


# ===========================================================================
# TOOL 1: Built-in — current_time (imported from strands_tools, no code needed)
# ===========================================================================
# current_time is imported above. Just pass it to the Agent's tools list.


# ===========================================================================
# TOOL 2: Custom — search_flights
# ===========================================================================

# TODO (Step 2): Add the @tool decorator
@tool
def search_flights(origin: str, destination: str, date: str) -> str:

    # TODO (Step 2): Add a docstring describing when to use this tool, the expected parameters, and the return format

    """
    Search for available Horizon Travel flights between two airports on a specific date.

    Use this tool when a customer asks about:
    - Flight availability between two cities or airports
    - Departure or arrival times for a specific route and date
    - Flight prices, seat availability, or aircraft type
    - Whether a flight is delayed, cancelled, or on schedule

    Args:
        origin      : IATA airport code for the departure airport.
                      Examples: 'LHR' (London), 'JFK' (New York), 'BCN' (Barcelona),
                      'SYD' (Sydney), 'DXB' (Dubai), 'MIA' (Miami), 'LAX' (Los Angeles)
        destination : IATA airport code for the arrival airport.
                      Examples: 'CDG' (Paris), 'FCO' (Rome), 'NRT' (Tokyo Narita),
                      'LHR' (London), 'MIA' (Miami), 'LAX' (Los Angeles), 'CUN' (Cancun)
        date        : Travel date in YYYY-MM-DD format. Example: '2026-03-15'

    Returns:
        Formatted string listing all matching flights with status, times, price,
        and available seats. Returns a not-found message if no flights match.
    """
    
    logger.info("search_flights called: %s → %s on %s", origin, destination, date)

    # Load flight data
    try:
        with open(FLIGHTS_FILE, encoding="utf-8") as f:
            flights = json.load(f)
    except FileNotFoundError:
        logger.error("flights.json not found at %s", FLIGHTS_FILE)
        return "⚠️  Flight database is temporarily unavailable. Please contact support."
    except json.JSONDecodeError as e:
        logger.error("Failed to parse flights.json: %s", e)
        return "⚠️  Error reading flight data. Please try again."

    # Normalise inputs
    origin_code = origin.strip().upper()
    dest_code = destination.strip().upper()
    search_date = date.strip()

    # Filter matching flights
    results = [
        fl for fl in flights
        if fl.get("origin", "").upper() == origin_code
        and fl.get("destination", "").upper() == dest_code
        and fl.get("date", "") == search_date
    ]

    if not results:
        return (
            f"No Horizon Travel flights found from {origin_code} to {dest_code} "
            f"on {search_date}.\n"
            f"💡 Tip: Try the day before or after, or check alternative routes."
        )

    # Format results
    status_icons = {"SCHEDULED": "🟢", "DELAYED": "🟡", "CANCELLED": "🔴"}
    header = f"✈️  Horizon Travel — {origin_code} → {dest_code} | {search_date}\n{'─' * 55}"
    rows = []
    for fl in results:
        icon = status_icons.get(fl.get("status", ""), "⚪")
        gate = f"Gate {fl['gate']}" if fl.get("gate") else "Gate TBA"
        seats_left = fl.get("available_seats", 0)
        seat_label = f"{seats_left} seats" if seats_left > 0 else "SOLD OUT"

        row = (
            f"{icon} {fl['flight_number']:8}  "
            f"{fl['departure_time']} → {fl['arrival_time']}  "
            f"{fl.get('cabin_class', ''):10}  "
            f"${fl.get('price_usd', 0):.2f}  "
            f"{seat_label:12}  "
            f"{gate}  |  {fl.get('aircraft', '')}"
        )
        rows.append(row)

    return f"{header}\n" + "\n".join(rows)


# ===========================================================================
# TOOL 3: Custom — search_hotels
# ===========================================================================

# TODO (Step 3): Add the @tool decorator
@tool
def search_hotels(city: str, max_price_usd: float = 9999.0) -> str:

    # TODO (Step 3): Add a docstring describing when to use this tool, the expected parameters, and the return format

    """
    Search for available hotels in a destination city, with optional price filtering.

    Use this tool when a customer asks about:
    - Hotel availability in a specific city
    - Hotel prices, star ratings, or room types
    - Hotel amenities (pools, spas, restaurants, gyms)
    - Check-in/check-out times or cancellation policies

    Args:
        city          : Name of the destination city. Examples: 'Barcelona', 'Tokyo',
                        'Rome', 'Dubai'. Must be an exact city name.
        max_price_usd : Maximum acceptable price per night in US dollars.
                        Defaults to 9999 (no price limit). Use values like 100, 200,
                        300 based on customer's budget.

    Returns:
        Formatted string listing matching available hotels with star ratings,
        prices, room types, amenities, and cancellation policies.

    """
    
    logger.info("search_hotels called: city=%s, max=$%.0f", city, max_price_usd)

    try:
        with open(HOTELS_FILE, encoding="utf-8") as f:
            hotels = json.load(f)
    except FileNotFoundError:
        return "⚠️  Hotel database is temporarily unavailable. Please contact support."
    except json.JSONDecodeError as e:
        logger.error("Failed to parse hotels.json: %s", e)
        return "⚠️  Error reading hotel data. Please try again."

    city_normalised = city.strip().title()

    # Filter: city match, available, within budget
    matching = [
        h for h in hotels
        if h.get("city", "").lower() == city_normalised.lower()
        and h.get("available", False)
        and h.get("price_per_night_usd", 9999) <= max_price_usd
    ]

    if not matching:
        budget_msg = f" under ${max_price_usd:.0f}/night" if max_price_usd < 9999 else ""
        return (
            f"No available hotels found in {city_normalised}{budget_msg}.\n"
            f"💡 Tip: Try a higher budget or check nearby cities."
        )

    star_icons = {5: "⭐⭐⭐⭐⭐", 4: "⭐⭐⭐⭐", 3: "⭐⭐⭐", 2: "⭐⭐", 1: "⭐"}
    budget_label = f" (budget: under ${max_price_usd:.0f})" if max_price_usd < 9999 else ""
    lines = [f"🏨  Hotels in {city_normalised}{budget_label}\n{'─' * 55}"]

    for h in sorted(matching, key=lambda x: x["price_per_night_usd"]):
        stars = star_icons.get(h.get("star_rating", 3), "")
        amenities_preview = ", ".join(h.get("amenities", [])[:4])
        rooms = ", ".join(h.get("room_types", []))

        lines.append(
            f"\n{stars} {h['name']} ({h['hotel_id']})\n"
            f"   💰 ${h['price_per_night_usd']:.0f}/night\n"
            f"   🛏️  Rooms : {rooms}\n"
            f"   🏖️  Amenities: {amenities_preview}\n"
            f"   🕐 Check-in: {h.get('check_in_time', 'N/A')}  |  "
            f"Check-out: {h.get('check_out_time', 'N/A')}\n"
            f"   📋 Policy: {h.get('cancellation_policy', 'See website')}"
        )

    return "\n".join(lines)


# ===========================================================================
# TOOL 4: Custom — get_exchange_rate
# ===========================================================================

# TODO (Step 4): Add the @tool decorator
@tool
def get_exchange_rate(from_currency: str, to_currency: str, amount: float = 1.0) -> str:

    # TODO (Step 4): Add a docstring describing when to use this tool, the expected parameters, and the return format
  
    """
    Get the current exchange rate between two currencies and optionally convert an amount.

    Use this tool when a customer asks about:
    - Currency exchange rates (e.g., USD to EUR, GBP to JPY)
    - How much a foreign currency will cost in their home currency
    - Budget planning in a destination country's local currency
    - Converting prices from one currency to another

    Supported currencies: USD, EUR, GBP, JPY, AUD, CAD, CHF, SGD, HKD, NZD,
                          SEK, NOK, DKK, AED, THB, MXN

    Args:
        from_currency : ISO 4217 source currency code (e.g. 'USD', 'EUR', 'GBP')
        to_currency   : ISO 4217 target currency code (e.g. 'JPY', 'AED', 'AUD')
        amount        : Amount to convert (default: 1.0 for a rate-only query)

    Returns:
        Exchange rate and converted amount as a formatted string.
    """

    logger.info(
        "get_exchange_rate called: %.2f %s → %s",
        amount, from_currency, to_currency
    )

    try:
        with open(EXCHANGE_FILE, encoding="utf-8") as f:
            rate_data = json.load(f)
    except FileNotFoundError:
        return "⚠️  Exchange rate data is temporarily unavailable."
    except json.JSONDecodeError as e:
        logger.error("Failed to parse exchange_rates.json: %s", e)
        return "⚠️  Error reading exchange rate data."

    # Build a dict: {currency_code: usd_rate}
    rates: dict[str, float] = rate_data.get("rates", {})
    rates["USD"] = 1.0  # USD is the pivot

    from_code = from_currency.strip().upper()
    to_code = to_currency.strip().upper()

    if from_code not in rates:
        return f"⚠️  Currency '{from_code}' is not supported. Supported: {', '.join(sorted(rates.keys()))}"
    if to_code not in rates:
        return f"⚠️  Currency '{to_code}' is not supported. Supported: {', '.join(sorted(rates.keys()))}"

    # Convert via USD as pivot:
    # amount_from_currency → USD → to_currency
    # 1 from_currency = (1 / rate_to_usd[from]) USD
    # 1 USD = rate_to_usd[to] to_currency
    from_rate = rates[from_code]   # to_currency units per 1 USD (if from==USD this is 1)
    to_rate = rates[to_code]       # to_currency units per 1 USD

    # Compute cross-rate: 1 from_currency = ? to_currency
    # 1 from_currency = (1 / from_rate) USD = (to_rate / from_rate) to_currency
    if from_code == "USD":
        cross_rate = to_rate
    elif to_code == "USD":
        cross_rate = 1.0 / from_rate
    else:
        cross_rate = to_rate / from_rate

    converted = amount * cross_rate
    last_updated = rate_data.get("last_updated", "recent")

    return (
        f"💱  Exchange Rate ({last_updated})\n"
        f"   1 {from_code} = {cross_rate:.4f} {to_code}\n"
        f"   {amount:,.2f} {from_code} = {converted:,.2f} {to_code}"
    )


# ===========================================================================
# ENTRY POINT
# ===========================================================================

@app.entrypoint
async def invoke(payload, context=None):
    """
    WanderBot — Function Calling entry point.

    Supports four tools:
        1. current_time      (built-in)
        2. search_flights    (custom — reads flights.json)
        3. search_hotels     (custom — reads hotels.json)
        4. get_exchange_rate (custom — reads exchange_rates.json)
    """
    user_message = payload.get("message", "Hello!")

    logger.info("User: %s", user_message[:100])

    # TODO (Step 5): Create an Agent with all four tools:

    # TODO (Step 5): Invoke the agent and return the response dict
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            current_time,       # Built-in
            search_flights,     # Custom
            search_hotels,      # Custom
            get_exchange_rate,  # Custom
        ],
    )

    response = agent(user_message)

    return response


if __name__ == "__main__":
    app.run()