"""MCP server for searching Rightmove UK property listings via Apify."""

import json
import os
from typing import Any

from apify_client import ApifyClient
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("rightmove")

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")


def _get_client() -> ApifyClient:
    if not APIFY_TOKEN:
        raise ValueError("APIFY_TOKEN environment variable is required")
    return ApifyClient(APIFY_TOKEN)


def _build_search_url(
    location_id: str, max_price: int, min_bedrooms: int,
    property_type: str = "", radius: float = 0.5, index: int = 0,
) -> str:
    """Build a Rightmove search URL for the Apify actor."""
    base = "https://www.rightmove.co.uk/property-for-sale/find.html"
    params = (
        f"?searchLocation={location_id}"
        f"&maxPrice={max_price}"
        f"&minBedrooms={min_bedrooms}"
        f"&radius={radius}"
        f"&sortType=2"
        f"&index={index}"
    )
    if property_type and property_type.lower() != "all":
        TYPE_MAP = {
            "houses": "detached%2Csemi-detached%2Cterraced",
            "flats": "flat",
            "bungalows": "bungalow",
        }
        rm_type = TYPE_MAP.get(property_type.lower(), property_type)
        params += f"&propertyTypes={rm_type}"
    return base + params


def _parse_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize an Apify result item to our standard format."""
    return {
        "id": item.get("id", item.get("propertyId", "")),
        "price": item.get("price", item.get("amount", 0)),
        "address": item.get("address", item.get("displayAddress", "")),
        "bedrooms": item.get("bedrooms", 0),
        "bathrooms": item.get("bathrooms", 0),
        "propertyType": item.get("propertyType", item.get("propertySubType", "")),
        "latitude": item.get("latitude", item.get("location", {}).get("latitude")),
        "longitude": item.get("longitude", item.get("location", {}).get("longitude")),
        "listingUrl": item.get("url", item.get("propertyUrl", "")),
        "summary": item.get("summary", item.get("description", ""))[:300],
        "addedOn": item.get("addedOn", item.get("firstVisibleDate", "")),
        "floorArea": item.get("floorArea", item.get("sizeSqFt", "")),
        "tenure": item.get("tenure", ""),
        "source": "rightmove",
    }


@mcp.tool()
async def search_rightmove(
    location: str,
    max_price: int,
    min_bedrooms: int,
    property_type: str = "houses",
    radius: float = 1.0,
    page: int = 0,
) -> str:
    """Search Rightmove UK property listings for sale via Apify.

    Args:
        location: London area or postcode (e.g. "SE15", "Peckham", "E8").
        max_price: Maximum price in GBP.
        min_bedrooms: Minimum number of bedrooms.
        property_type: "houses", "flats", "bungalows", or "all".
        radius: Search radius in miles.
        page: Page number (0-indexed).

    Returns:
        JSON string with property listings.
    """
    search_url = _build_search_url(
        location, max_price, min_bedrooms, property_type, radius, page * 24,
    )

    try:
        client = _get_client()
        run_input = {
            "listUrls": [{"url": search_url}],
            "maxItems": 30,
        }
        run = client.actor("dhrumil/rightmove-scraper").call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Apify error: {str(e)}"})

    properties = [_parse_item(item) for item in items]

    return json.dumps({
        "resultCount": len(properties),
        "page": page,
        "properties": properties,
    }, indent=2)


@mcp.tool()
async def get_rightmove_details(property_url: str) -> str:
    """Fetch detailed information about a specific Rightmove listing via Apify.

    Args:
        property_url: Full Rightmove property URL.

    Returns:
        JSON string with detailed property information.
    """
    if not property_url.startswith("http"):
        property_url = f"https://www.rightmove.co.uk/properties/{property_url}"

    try:
        client = _get_client()
        run_input = {
            "listUrls": [{"url": property_url}],
            "maxItems": 1,
        }
        run = client.actor("dhrumil/rightmove-scraper").call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Apify error: {str(e)}"})

    if not items:
        return json.dumps({"error": "No data returned for this property"})

    item = items[0]
    return json.dumps(item, indent=2, default=str)


if __name__ == "__main__":
    mcp.run()
