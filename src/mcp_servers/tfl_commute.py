import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("tfl_commute")

TFL_APP_KEY = os.environ.get("TFL_APP_KEY", "")

BASE_URL = "https://api.tfl.gov.uk/Journey/JourneyResults"
MODES = "tube,dlr,overground,elizabeth-line,national-rail,bus,walking"


def _build_route_summary(legs: list[dict]) -> str:
    """Build a human-readable summary from journey legs."""
    parts = []
    for leg in legs:
        mode_name = leg.get("mode", {}).get("name", "")
        if mode_name == "walking":
            duration = leg.get("duration", 0)
            parts.append(f"Walk {duration} min")
        else:
            route_name = ""
            route_options = leg.get("routeOptions", [])
            if route_options:
                route_name = route_options[0].get("name", "")
            destination = leg.get("arrivalPoint", {}).get("commonName", "")
            if route_name and destination:
                parts.append(f"{route_name} to {destination}")
            elif destination:
                parts.append(f"{mode_name} to {destination}")
            else:
                parts.append(mode_name)
    return ", then ".join(parts)


def _extract_walking_time(legs: list[dict]) -> int:
    """Extract total walking time in minutes from journey legs."""
    total = 0
    for leg in legs:
        if leg.get("mode", {}).get("name", "") == "walking":
            total += leg.get("duration", 0)
    return total


def _parse_journey(journey: dict) -> dict:
    """Parse a single journey into a structured dict."""
    legs = journey.get("legs", [])
    duration = journey.get("duration", 0)
    summary = _build_route_summary(legs)
    walking_time = _extract_walking_time(legs)

    non_walking_legs = [
        leg for leg in legs
        if leg.get("mode", {}).get("name", "") != "walking"
    ]
    changes = max(0, len(non_walking_legs) - 1)

    departure_time = journey.get("startDateTime", "")
    arrival_time = journey.get("arrivalDateTime", "")

    return {
        "duration_mins": duration,
        "summary": summary,
        "changes": changes,
        "walking_mins": walking_time,
        "departure_time": departure_time,
        "arrival_time": arrival_time,
    }


@mcp.tool()
async def get_commute_time(
    from_location: str,
    to_location: str,
    arrival_time: str = "0900",
    mode: str = "public_transport",
) -> str:
    """Calculate commute time between two London locations using TfL Journey Planner.

    Args:
        from_location: Origin as a postcode (e.g. "SW1A1AA") or lat,lng pair (e.g. "51.5074,-0.1278").
        to_location: Destination as a postcode or lat,lng pair.
        arrival_time: Desired arrival time in HHMM format (default "0900").
        mode: Travel mode (default "public_transport").

    Returns:
        JSON string with best_duration_mins and up to 3 route alternatives.
    """
    url = f"{BASE_URL}/{from_location}/to/{to_location}"
    params = {
        "timeIs": "Arriving",
        "journeyPreference": "LeastTime",
        "time": arrival_time,
        "mode": MODES,
    }

    if TFL_APP_KEY:
        params["app_key"] = TFL_APP_KEY

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url, params=params)

            # Handle 300 disambiguation — pick the first match and retry
            if response.status_code == 300:
                disambig = response.json()
                # Check both from and to disambiguation
                for key in ("toLocationDisambiguation", "fromLocationDisambiguation"):
                    options = disambig.get(key, {}).get("disambiguationOptions", [])
                    if options:
                        # Use the top match's parameterValue (coordinates or ID)
                        best = options[0].get("parameterValue", "")
                        place_name = options[0].get("place", {}).get("commonName", "")
                        if best:
                            if key == "toLocationDisambiguation":
                                url = f"{BASE_URL}/{from_location}/to/{best}"
                            else:
                                url = f"{BASE_URL}/{best}/to/{to_location}"

                # Retry with resolved location
                response = await client.get(url, params=params)

            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        return json.dumps({
            "error": f"TfL API returned status {e.response.status_code}",
            "message": "Could not retrieve journey results. Check that the locations are valid.",
        })
    except httpx.RequestError as e:
        return json.dumps({
            "error": "Request failed",
            "message": str(e),
        })

    journeys = data.get("journeys", [])
    if not journeys:
        return json.dumps({
            "error": "No routes found",
            "message": f"TfL could not find any routes from {from_location} to {to_location} arriving by {arrival_time}.",
        })

    routes = [_parse_journey(j) for j in journeys[:3]]
    best_duration = min(r["duration_mins"] for r in routes)

    result = {
        "best_duration_mins": best_duration,
        "routes": routes,
    }

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run()
