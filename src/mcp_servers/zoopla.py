"""MCP server for searching Zoopla UK property listings via Apify."""

import json
import os
from typing import Any

from apify_client import ApifyClient
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("zoopla")

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")


def _get_client() -> ApifyClient:
    if not APIFY_TOKEN:
        raise ValueError("APIFY_TOKEN environment variable is required")
    return ApifyClient(APIFY_TOKEN)


def _build_search_url(
    area: str, max_price: int, min_bedrooms: int,
    property_type: str = "", page: int = 1,
) -> str:
    """Build a Zoopla search URL for the Apify actor."""
    # Zoopla URL format: /for-sale/details/{type}/{area}/
    ptype = property_type.lower() if property_type else "property"
    if ptype in ("houses", "house"):
        ptype = "houses"
    elif ptype in ("flats", "flat"):
        ptype = "flats"
    else:
        ptype = "property"

    area_slug = area.lower().replace(" ", "-")
    return (
        f"https://www.zoopla.co.uk/for-sale/details/{ptype}/{area_slug}/"
        f"?price_max={max_price}&beds_min={min_bedrooms}"
        f"&page_size=25&pn={page}&view_type=list"
    )


def _parse_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Zoopla Apify result to our standard format."""
    return {
        "id": item.get("id", item.get("listing_id", "")),
        "price": item.get("price", item.get("listing_price", 0)),
        "address": item.get("address", item.get("displayAddress", "")),
        "bedrooms": item.get("bedrooms", item.get("num_bedrooms", 0)),
        "bathrooms": item.get("bathrooms", item.get("num_bathrooms", 0)),
        "propertyType": item.get("propertyType", item.get("property_type", "")),
        "latitude": item.get("latitude", item.get("lat")),
        "longitude": item.get("longitude", item.get("lon")),
        "listingUrl": item.get("url", item.get("listing_url", "")),
        "summary": item.get("description", item.get("short_description", ""))[:300],
        "addedOn": item.get("addedOn", item.get("first_published_date", "")),
        "floorArea": item.get("floorArea", item.get("floor_area", "")),
        "source": "zoopla",
    }


@mcp.tool()
async def search_zoopla(
    area: str,
    max_price: int,
    min_bedrooms: int,
    property_type: str = "houses",
    page: int = 1,
) -> str:
    """Search Zoopla UK property listings for sale via Apify.

    Args:
        area: London area or postcode (e.g. "SE15", "peckham", "hackney").
        max_price: Maximum price in GBP.
        min_bedrooms: Minimum number of bedrooms.
        property_type: "houses", "flats", or "property" (all).
        page: Page number (1-indexed).

    Returns:
        JSON string with property listings.
    """
    search_url = _build_search_url(area, max_price, min_bedrooms, property_type, page)

    try:
        client = _get_client()
        run_input = {
            "startUrls": [{"url": search_url}],
            "maxItems": 25,
        }
        run = client.actor("dhrumil/zoopla-scraper").call(run_input=run_input)
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
async def get_zoopla_details(property_url: str) -> str:
    """Fetch detailed information about a specific Zoopla listing via Apify.

    Args:
        property_url: Full Zoopla property URL.

    Returns:
        JSON string with detailed property information.
    """
    try:
        client = _get_client()
        run_input = {
            "startUrls": [{"url": property_url}],
            "maxItems": 1,
        }
        run = client.actor("dhrumil/zoopla-scraper").call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Apify error: {str(e)}"})

    if not items:
        return json.dumps({"error": "No data returned for this property"})

    return json.dumps(items[0], indent=2, default=str)


if __name__ == "__main__":
    mcp.run()
