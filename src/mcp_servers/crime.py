import json
from collections import Counter

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("crime")


@mcp.tool()
async def get_crime_stats(lat: float, lng: float, date: str = "") -> str:
    """Retrieve street-level crime statistics for a location from the police.uk API.

    Args:
        lat: Latitude of the location.
        lng: Longitude of the location.
        date: Optional month in YYYY-MM format. If omitted, returns the latest available month.

    Returns:
        JSON string with total_crimes, by_category, month, top_3_categories, and risk_level.
    """
    url = f"https://data.police.uk/api/crimes-street/all-crime?lat={lat}&lng={lng}"
    if date:
        url += f"&date={date}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url)
            response.raise_for_status()

        crimes = response.json()

        if not crimes:
            return json.dumps({
                "total_crimes": 0,
                "by_category": {},
                "month": date or "unknown",
                "top_3_categories": [],
                "risk_level": "low",
            })

        category_counts = Counter(crime["category"] for crime in crimes)
        total = sum(category_counts.values())
        month = crimes[0].get("month", date or "unknown")
        top_3 = category_counts.most_common(3)

        if total < 20:
            risk_level = "low"
        elif total <= 50:
            risk_level = "medium"
        else:
            risk_level = "high"

        return json.dumps({
            "total_crimes": total,
            "by_category": dict(category_counts),
            "month": month,
            "top_3_categories": top_3,
            "risk_level": risk_level,
        })

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"HTTP error {e.response.status_code}: {e.response.text}"})
    except httpx.RequestError as e:
        return json.dumps({"error": f"Request failed: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {str(e)}"})


if __name__ == "__main__":
    mcp.run()
