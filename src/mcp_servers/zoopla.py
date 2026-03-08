import json
import re

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("zoopla")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _extract_next_data(html: str) -> dict | None:
    """Extract __NEXT_DATA__ JSON from script tag."""
    pattern = r'<script\s+id="__NEXT_DATA__"\s+type="application/json">\s*(.*?)\s*</script>'
    match = re.search(pattern, html, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _extract_listings(next_data: dict) -> list[dict]:
    """Extract property listings from Zoopla __NEXT_DATA__ structure."""
    listings = []

    try:
        props = next_data.get("props", {})
        page_props = props.get("pageProps", {})

        regular_listings = (
            page_props.get("regularListings", [])
            or page_props.get("listings", [])
            or []
        )

        # Also check for initialProps / searchResults path
        if not regular_listings:
            initial_props = page_props.get("initialProps", {})
            search_results = initial_props.get("searchResults", {})
            regular_listings = search_results.get("listings", {}).get(
                "regular", []
            ) or search_results.get("regularListings", [])

        for item in regular_listings:
            listing = item if not item.get("listing") else item["listing"]

            address = listing.get("address", "") or listing.get(
                "displayAddress", ""
            )
            if isinstance(address, dict):
                address = address.get("displayAddress", str(address))

            price_obj = listing.get("price", "")
            if isinstance(price_obj, dict):
                price = price_obj.get("amount", price_obj.get("displayPrice", ""))
            else:
                price = price_obj

            branch = listing.get("branch", {})
            _ = branch  # available if needed

            location = listing.get("location", {}) or {}
            lat = location.get("latitude") or listing.get("latitude")
            lng = location.get("longitude") or listing.get("longitude")

            listing_id = listing.get("listingId", "") or listing.get("id", "")
            listing_uri = listing.get("listingUris", {})
            detail_url = listing_uri.get("detail", "") if isinstance(listing_uri, dict) else ""
            if detail_url and not detail_url.startswith("http"):
                detail_url = f"https://www.zoopla.co.uk{detail_url}"

            image = listing.get("image", {})
            image_url = ""
            if isinstance(image, dict):
                image_url = image.get("src", "") or image.get("url", "")
            elif isinstance(image, str):
                image_url = image
            # Also check images array
            if not image_url:
                images = listing.get("images", [])
                if images and isinstance(images, list):
                    first = images[0]
                    if isinstance(first, dict):
                        image_url = first.get("src", "") or first.get("url", "")
                    elif isinstance(first, str):
                        image_url = first

            listings.append(
                {
                    "id": str(listing_id),
                    "price": price,
                    "address": address,
                    "bedrooms": listing.get("beds", listing.get("bedrooms")),
                    "bathrooms": listing.get("baths", listing.get("bathrooms")),
                    "propertyType": listing.get("propertyType", ""),
                    "latitude": lat,
                    "longitude": lng,
                    "listingUrl": detail_url,
                    "imageUrl": image_url,
                    "summary": listing.get("summaryDescription", "")
                    or listing.get("summary", "")
                    or listing.get("description", ""),
                }
            )
    except (KeyError, TypeError, AttributeError):
        pass

    return listings


@mcp.tool()
async def search_zoopla(
    area: str,
    max_price: int,
    min_bedrooms: int,
    property_type: str = "houses",
    page: int = 1,
) -> str:
    """Search Zoopla for UK property listings.

    Args:
        area: Location area to search, e.g. 'london', 'oxford', 'SW1'.
        max_price: Maximum price in GBP.
        min_bedrooms: Minimum number of bedrooms.
        property_type: Type of property - 'houses' or 'flats'. Defaults to 'houses'.
        page: Page number for paginated results. Defaults to 1.

    Returns:
        JSON string with property listings or an error message.
    """
    url = (
        f"https://www.zoopla.co.uk/for-sale/details/{property_type}/{area}/"
        f"?price_max={max_price}&beds_min={min_bedrooms}"
        f"&page_size=25&pn={page}&view_type=list"
    )

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30, headers=HEADERS
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        return json.dumps(
            {"error": f"HTTP error {e.response.status_code} fetching {url}"}
        )
    except httpx.RequestError as e:
        return json.dumps({"error": f"Request error: {str(e)}"})

    html = response.text
    next_data = _extract_next_data(html)

    if next_data is None:
        return json.dumps(
            {
                "error": "Could not find __NEXT_DATA__ in page. "
                "Zoopla may have changed their page structure or blocked the request.",
                "url": url,
            }
        )

    listings = _extract_listings(next_data)

    return json.dumps(
        {
            "url": url,
            "total_results": len(listings),
            "page": page,
            "listings": listings,
        },
        indent=2,
    )


@mcp.tool()
async def get_zoopla_details(property_url: str) -> str:
    """Fetch detailed information for a specific Zoopla property listing.

    Args:
        property_url: Full URL to a Zoopla property listing page.

    Returns:
        JSON string with property details or an error message.
    """
    if not property_url.startswith("http"):
        property_url = f"https://www.zoopla.co.uk{property_url}"

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30, headers=HEADERS
        ) as client:
            response = await client.get(property_url)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        return json.dumps(
            {
                "error": f"HTTP error {e.response.status_code} fetching {property_url}"
            }
        )
    except httpx.RequestError as e:
        return json.dumps({"error": f"Request error: {str(e)}"})

    html = response.text
    next_data = _extract_next_data(html)

    if next_data is None:
        return json.dumps(
            {
                "error": "Could not find __NEXT_DATA__ in page. "
                "Zoopla may have changed their page structure or blocked the request.",
                "url": property_url,
            }
        )

    details = {}

    try:
        props = next_data.get("props", {})
        page_props = props.get("pageProps", {})

        listing_details = (
            page_props.get("listingDetails", {})
            or page_props.get("data", {}).get("listing", {})
            or page_props.get("listing", {})
            or {}
        )

        # Address
        address = listing_details.get("address", "")
        if isinstance(address, dict):
            address = address.get("displayAddress", str(address))
        details["address"] = address

        # Price
        price_obj = listing_details.get("price", "")
        if isinstance(price_obj, dict):
            details["price"] = price_obj.get(
                "amount", price_obj.get("displayPrice", "")
            )
        else:
            details["price"] = price_obj

        # Core details
        details["bedrooms"] = listing_details.get(
            "beds", listing_details.get("bedrooms")
        )
        details["bathrooms"] = listing_details.get(
            "baths", listing_details.get("bathrooms")
        )
        details["propertyType"] = listing_details.get("propertyType", "")

        # Full description
        details["description"] = (
            listing_details.get("detailedDescription", "")
            or listing_details.get("description", "")
            or listing_details.get("summaryDescription", "")
        )

        # Features / bullet points
        details["features"] = listing_details.get("features", []) or listing_details.get(
            "bulletPoints", []
        )
        if isinstance(details["features"], dict):
            details["features"] = details["features"].get("bullets", [])

        # Floorplan
        floorplans = listing_details.get("floorPlan", {}) or listing_details.get(
            "floorPlans", []
        )
        if isinstance(floorplans, dict):
            details["floorplanUrl"] = floorplans.get("image", {}).get("src", "") or floorplans.get("url", "")
        elif isinstance(floorplans, list) and floorplans:
            fp = floorplans[0]
            if isinstance(fp, dict):
                details["floorplanUrl"] = fp.get("image", {}).get("src", "") if isinstance(fp.get("image"), dict) else fp.get("url", "")
            else:
                details["floorplanUrl"] = str(fp)
        else:
            details["floorplanUrl"] = ""

        # EPC
        epc = listing_details.get("epc", {}) or {}
        if isinstance(epc, dict):
            details["epc"] = {
                "currentRating": epc.get("currentRating", ""),
                "potentialRating": epc.get("potentialRating", ""),
                "url": epc.get("image", {}).get("src", "") if isinstance(epc.get("image"), dict) else epc.get("url", ""),
            }
        else:
            details["epc"] = epc

        # Nearby stations
        stations_data = listing_details.get("nearbyStations", []) or listing_details.get(
            "transportLinks", []
        )
        stations = []
        if isinstance(stations_data, list):
            for station in stations_data:
                if isinstance(station, dict):
                    stations.append(
                        {
                            "name": station.get("name", ""),
                            "distance": station.get(
                                "distance", station.get("distanceMiles", "")
                            ),
                            "type": station.get("type", station.get("mode", "")),
                        }
                    )
        details["nearbyStations"] = stations

        # Size / square footage
        details["size"] = (
            listing_details.get("sizeSqFt", "")
            or listing_details.get("floorArea", "")
            or listing_details.get("size", "")
        )
        if isinstance(details["size"], dict):
            details["size"] = details["size"].get("value", "")

        # Location
        location = listing_details.get("location", {}) or {}
        if isinstance(location, dict):
            details["latitude"] = location.get("latitude")
            details["longitude"] = location.get("longitude")

    except (KeyError, TypeError, AttributeError) as e:
        details["parse_warning"] = f"Some fields may be missing: {str(e)}"

    return json.dumps(details, indent=2)


if __name__ == "__main__":
    mcp.run()
