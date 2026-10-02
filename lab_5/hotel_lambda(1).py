"""
================================================================================
WanderBot — Lambda: Hotel Search Tools API
================================================================================
Function Name : WanderBotHotelTools
Runtime       : Python 3.14

Sits behind an API Gateway REST API.

ENDPOINT
--------
  GET /hotels
  — Returns hotels in a given city, optionally under a maximum price (e.g. city=Rome)
  
  GET /hotels/{hotel_id}
  — Returns hotel details (e.g. hotel_id=HTL-001)
  

EVENT FORMAT (API Gateway Lambda proxy)
---------------------------------------
  {
    "httpMethod": "GET",
    "path": "/hotels/{hotel_id}",
    "pathParameters": {"hotel_id": "HTL-009"}
  }

  {
    "httpMethod": "GET",
    "path": "/hotels",
    "queryStringParameters": {"city": "Rome", "max_price": 200.00}
  }

RESPONSE FORMAT
---------------
  {"statusCode": 200, "body": "{...}"}
================================================================================
"""


import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Demo hotel data
# ---------------------------------------------------------------------------
HOTELS = [
    {"hotel_id": "HTL-001", "name": "Hotel Arts Barcelona",     "city": "Barcelona", "stars": 5, "price": 320.00, "available": True},
    {"hotel_id": "HTL-002", "name": "Catalonia Plaza",          "city": "Barcelona", "stars": 4, "price": 145.00, "available": True},
    {"hotel_id": "HTL-003", "name": "Hostal Grau",              "city": "Barcelona", "stars": 3, "price":  85.00, "available": True},
    {"hotel_id": "HTL-004", "name": "The Peninsula Tokyo",      "city": "Tokyo",     "stars": 5, "price": 580.00, "available": True},
    {"hotel_id": "HTL-005", "name": "Shinjuku Granbell Hotel",  "city": "Tokyo",     "stars": 4, "price": 180.00, "available": True},
    {"hotel_id": "HTL-006", "name": "Hotel de Russie",          "city": "Rome",      "stars": 5, "price": 490.00, "available": True},
    {"hotel_id": "HTL-007", "name": "Hotel Campo de' Fiori",    "city": "Rome",      "stars": 4, "price": 165.00, "available": True},
    {"hotel_id": "HTL-008", "name": "InterContinental Dubai",   "city": "Dubai",     "stars": 5, "price": 390.00, "available": True},
    {"hotel_id": "HTL-009", "name": "Rove Downtown Dubai",      "city": "Dubai",     "stars": 3, "price": 110.00, "available": True},
]


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------

def search_hotels(city: str, max_price: float = 9999.0) -> str:
    matches = [
        h for h in HOTELS
        if h["city"].lower() == city.lower()
        and h["available"]
        and h["price"] <= max_price
    ]
    if not matches:
        return f"No hotels found in {city} under ${max_price:.0f}/night."
    return json.dumps({"city": city, "hotels": sorted(matches, key=lambda h: h["price"])})


def get_hotel_detail(hotel_id: str) -> str:
    hotel = next((h for h in HOTELS if h["hotel_id"].upper() == hotel_id.upper()), None)
    if not hotel:
        return f"No hotel found with ID {hotel_id}."
    return json.dumps(hotel)


# ---------------------------------------------------------------------------
# Lambda handler — API Gateway proxy integration
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context) -> dict:

    
    if event.get("queryStringParameters") != None and "city" in event.get("queryStringParameters", {}):
        city = event.get("queryStringParameters", {}).get("city")
        max_price = float(event.get("queryStringParameters", {}).get("max_price", 9999))
        result = search_hotels(city, max_price)

    elif "hotel_id" in event.get("pathParameters"):
        result = get_hotel_detail(event.get("pathParameters")["hotel_id"])

    else:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing path parameter: city or hotel_id"}),
        }
    

    return {
            "statusCode": 200,
            "body": json.dumps({
                "result":    result
            }),
        }