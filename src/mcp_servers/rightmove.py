"""MCP server for searching Rightmove UK property listings."""

import json
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("rightmove")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}


def _extract_json_model(html: str) -> dict[str, Any] | None:
    """Extract the window.jsonModel data embedded in Rightmove pages."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        text = script.string
        if text and "window.jsonModel" in text:
            match = re.search(r"window\.jsonModel\s*=\s*(\{.*?\})\s*;?\s*$", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            # Try a more lenient pattern
            match = re.search(r"window\.jsonModel\s*=\s*(\{.*\})", text, re.DOTALL)
            if match:
                raw = match.group(1).strip().rstrip(";").strip()
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    pass
    return None


def _parse_property(prop: dict[str, Any]) -> dict[str, Any]:
    """Extract relevant fields from a Rightmove property dict."""
    location = prop.get("location", {})
    listing_update = prop.get("listingUpdate", {})
    price_info = prop.get("price", {})

    property_id = prop.get("id", "")
    price = price_info.get("amount") if isinstance(price_info, dict) else prop.get("price")

    return {
        "id": property_id,
        "price": price,
        "address": prop.get("displayAddress", prop.get("address", "")),
        "bedrooms": prop.get("bedrooms"),
        "bathrooms": prop.get("bathrooms"),
        "propertyType": prop.get("propertySubType", prop.get("propertyType", "")),
        "latitude": location.get("latitude") if isinstance(location, dict) else None,
        "longitude": location.get("longitude") if isinstance(location, dict) else None,
        "listingUrl": (
            f"https://www.rightmove.co.uk/properties/{property_id}"
            if property_id
            else prop.get("propertyUrl", "")
        ),
        "firstVisibleDate": (
            listing_update.get("listingUpdateDate")
            if isinstance(listing_update, dict)
            else prop.get("firstVisibleDate", "")
        ),
        "floorplanUrl": (
            prop.get("floorplans", [{}])[0].get("url", "")
            if prop.get("floorplans")
            else ""
        ),
        "summary": prop.get("summary", prop.get("propertyTypeFullDescription", "")),
    }


@mcp.tool()
async def search_rightmove(
    location_identifier: str,
    max_price: int,
    min_bedrooms: int,
    property_type: str = "houses",
    radius: float = 0.5,
    page: int = 0,
) -> str:
    """Search Rightmove UK property listings for sale.

    Args:
        location_identifier: Location search term (e.g. "London", "SW1A", "REGION^87490")
        max_price: Maximum price in GBP
        min_bedrooms: Minimum number of bedrooms
        property_type: Property type filter (e.g. "houses", "flats", "bungalows")
        radius: Search radius in miles (0.0, 0.25, 0.5, 1.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0)
        page: Page number (0-indexed), each page shows 24 results

    Returns:
        JSON string with search results containing property listings.
    """
    index = page * 24
    params = {
        "searchLocation": location_identifier,
        "maxPrice": str(max_price),
        "minBedrooms": str(min_bedrooms),
        "radius": str(radius),
        "sortType": "2",
        "includeSSTC": "false",
        "_includeLetAgreed": "false",
        "index": str(index),
    }
    if property_type and property_type.lower() != "all":
        params["propertyTypes"] = property_type

    url = "https://www.rightmove.co.uk/property-for-sale/find.html"

    try:
        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True, timeout=30
        ) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"HTTP error {e.response.status_code}: {e.response.reason_phrase}"})
    except httpx.RequestError as e:
        return json.dumps({"error": f"Request failed: {str(e)}"})

    json_model = _extract_json_model(response.text)
    if not json_model:
        return json.dumps({"error": "Could not extract property data from Rightmove page. The page structure may have changed."})

    properties_raw = json_model.get("properties", [])
    if not properties_raw:
        # Try alternate keys
        search_data = json_model.get("searchResult", {})
        if isinstance(search_data, dict):
            properties_raw = search_data.get("properties", [])

    properties = [_parse_property(p) for p in properties_raw]

    result_count = json_model.get("resultCount", json_model.get("totalResultCount", len(properties)))
    pagination = json_model.get("pagination", {})

    return json.dumps(
        {
            "resultCount": result_count,
            "page": page,
            "propertiesOnPage": len(properties),
            "pagination": {
                "total": pagination.get("total", ""),
                "current": pagination.get("page", page),
            },
            "properties": properties,
        },
        indent=2,
    )


@mcp.tool()
async def get_rightmove_details(property_url: str) -> str:
    """Fetch detailed information about a specific Rightmove property listing.

    Args:
        property_url: Full Rightmove property URL (e.g. "https://www.rightmove.co.uk/properties/123456789")

    Returns:
        JSON string with detailed property information.
    """
    if not property_url.startswith("http"):
        property_url = f"https://www.rightmove.co.uk/properties/{property_url}"

    try:
        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True, timeout=30
        ) as client:
            response = await client.get(property_url)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"HTTP error {e.response.status_code}: {e.response.reason_phrase}"})
    except httpx.RequestError as e:
        return json.dumps({"error": f"Request failed: {str(e)}"})

    html = response.text
    json_model = _extract_json_model(html)

    soup = BeautifulSoup(html, "html.parser")

    result: dict[str, Any] = {"url": property_url}

    if json_model:
        property_data = json_model.get("propertyData", json_model)

        result["address"] = property_data.get("address", {})
        result["bedrooms"] = property_data.get("bedrooms")
        result["bathrooms"] = property_data.get("bathrooms")

        prices = property_data.get("prices", {})
        if isinstance(prices, dict):
            result["price"] = prices.get("primaryPrice", "")
            result["priceQualifier"] = prices.get("priceQualifier", "")
        else:
            result["price"] = property_data.get("price", "")

        result["propertyType"] = property_data.get("propertySubType", property_data.get("propertyType", ""))
        result["tenure"] = property_data.get("tenure", {}).get("tenureType", "") if isinstance(property_data.get("tenure"), dict) else property_data.get("tenure", "")

        # Description
        text_data = property_data.get("text", {})
        if isinstance(text_data, dict):
            result["description"] = text_data.get("description", "")
        else:
            result["description"] = property_data.get("description", "")

        # Key features
        result["keyFeatures"] = property_data.get("keyFeatures", [])

        # Size
        sizing = property_data.get("sizings", [])
        if sizing and isinstance(sizing, list):
            for s in sizing:
                if isinstance(s, dict):
                    result["size"] = {
                        "minimumSize": s.get("minimumSize", ""),
                        "maximumSize": s.get("maximumSize", ""),
                        "unit": s.get("unit", ""),
                    }
                    break
        else:
            result["size"] = None

        # Floorplan
        floorplans = property_data.get("floorplans", [])
        if floorplans and isinstance(floorplans, list):
            result["floorplanUrls"] = [fp.get("url", "") for fp in floorplans if isinstance(fp, dict)]
        else:
            result["floorplanUrls"] = []

        # EPC
        epc = property_data.get("epc", {})
        if isinstance(epc, dict):
            epc_images = epc.get("images", [])
            result["epcChartUrl"] = epc_images[0].get("url", "") if epc_images else ""
        else:
            result["epcChartUrl"] = ""

        # Nearby stations
        stations = property_data.get("nearestStations", [])
        if stations and isinstance(stations, list):
            result["nearbyStations"] = [
                {
                    "name": st.get("name", ""),
                    "distance": st.get("distance", ""),
                    "unit": st.get("unit", "miles"),
                    "types": st.get("types", []),
                }
                for st in stations
                if isinstance(st, dict)
            ]
        else:
            result["nearbyStations"] = []

        # Location
        location = property_data.get("location", {})
        if isinstance(location, dict):
            result["latitude"] = location.get("latitude")
            result["longitude"] = location.get("longitude")

        # Features / bullet points
        features = property_data.get("features", property_data.get("bulletPoints", []))
        if features and isinstance(features, list):
            result["features"] = features

        # Listing history
        listing_history = property_data.get("listingHistory", {})
        if isinstance(listing_history, dict):
            result["listingHistory"] = listing_history

    else:
        # Fallback: scrape what we can from HTML directly
        result["warning"] = "Could not extract structured JSON data; falling back to HTML parsing."

        # Title / address
        title_tag = soup.find("h1")
        if title_tag:
            result["address"] = title_tag.get_text(strip=True)

        # Price
        price_tag = soup.find("span", {"data-testid": "price"}) or soup.find(class_=re.compile(r"price", re.I))
        if price_tag:
            result["price"] = price_tag.get_text(strip=True)

        # Description
        desc_div = soup.find("div", {"data-testid": "description"}) or soup.find(class_=re.compile(r"description", re.I))
        if desc_div:
            result["description"] = desc_div.get_text(separator="\n", strip=True)

        # Key features
        kf_list = soup.find("ul", class_=re.compile(r"keyFeatures", re.I))
        if kf_list:
            result["keyFeatures"] = [li.get_text(strip=True) for li in kf_list.find_all("li")]

        # Floorplan images
        floorplan_imgs = soup.find_all("img", src=re.compile(r"floorplan", re.I))
        if floorplan_imgs:
            result["floorplanUrls"] = [img["src"] for img in floorplan_imgs if img.get("src")]

        # EPC
        epc_imgs = soup.find_all("img", src=re.compile(r"epc", re.I))
        if epc_imgs:
            result["epcChartUrl"] = epc_imgs[0].get("src", "")

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run()
