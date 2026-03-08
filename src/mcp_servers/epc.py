import base64
import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("epc")

EPC_API_URL = (
    "https://epc.opendatacommunities.org/api/v1/domestic/search"
    "?postcode={postcode}&size=100"
)


def _build_headers() -> dict[str, str]:
    """Build request headers, including auth if credentials are available."""
    headers = {"Accept": "application/json"}

    token = os.environ.get("EPC_API_TOKEN", "")
    email = os.environ.get("EPC_API_EMAIL", "")

    if token and email:
        credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
        headers["Authorization"] = f"Basic {credentials}"

    return headers


def _fuzzy_match(address: str, fragment: str) -> bool:
    """Check whether an address fragment loosely matches a full address."""
    if not fragment:
        return True
    address_lower = address.lower()
    fragment_lower = fragment.lower().strip()
    # All words in the fragment must appear in the address
    return all(word in address_lower for word in fragment_lower.split())


def _format_certificate(row: dict) -> dict:
    """Extract relevant fields from a raw EPC API result row."""
    return {
        "address": row.get("address", ""),
        "epc_rating": row.get("current-energy-rating", ""),
        "epc_score": row.get("current-energy-efficiency", ""),
        "current_energy_efficiency": row.get("current-energy-efficiency", ""),
        "potential_energy_efficiency": row.get("potential-energy-efficiency", ""),
        "property_type": row.get("property-type", ""),
        "floor_area_sqm": row.get("total-floor-area", ""),
        "heating_type": row.get(
            "mainheat-description",
            row.get("main-heating-controls", ""),
        ),
    }


@mcp.tool()
async def get_epc_rating(postcode: str, address_fragment: str = "") -> str:
    """Look up Energy Performance Certificate data for a UK postcode.

    Uses the Open EPC API at epc.opendatacommunities.org. If the environment
    variables EPC_API_EMAIL and EPC_API_TOKEN are set they will be used for
    authentication; otherwise the request is attempted without auth.

    Args:
        postcode: UK postcode to search (e.g. 'SW1A 1AA').
        address_fragment: Optional part of the address to filter results
            (e.g. 'Flat 3' or '12 High Street'). If empty, all EPCs
            for the postcode are returned.

    Returns:
        JSON string with matching EPC records or an error message.
    """
    encoded_postcode = postcode.replace(" ", "%20")
    url = EPC_API_URL.format(postcode=encoded_postcode)
    headers = _build_headers()

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)

            if resp.status_code == 401:
                return json.dumps({
                    "error": (
                        "EPC API requires authentication. Register for free at "
                        "https://epc.opendatacommunities.org/ and set the "
                        "EPC_API_EMAIL and EPC_API_TOKEN environment variables."
                    ),
                })

            resp.raise_for_status()

            data = resp.json()

    except httpx.TimeoutException:
        return json.dumps({"error": f"Request timed out looking up EPCs for {postcode}"})
    except httpx.HTTPError as exc:
        return json.dumps({"error": f"HTTP error fetching EPC data: {exc}"})

    rows = data.get("rows", data if isinstance(data, list) else [])

    if not rows:
        return json.dumps({
            "results": [],
            "message": f"No EPC records found for postcode {postcode}.",
        })

    # Filter by address fragment if provided
    matched = [
        _format_certificate(row)
        for row in rows
        if _fuzzy_match(row.get("address", ""), address_fragment)
    ]

    if not matched:
        return json.dumps({
            "results": [],
            "message": (
                f"No EPC records matching '{address_fragment}' found "
                f"for postcode {postcode}. "
                f"{len(rows)} records exist for this postcode."
            ),
        })

    return json.dumps({
        "results": matched,
        "num_results": len(matched),
        "postcode": postcode,
    }, indent=2)


if __name__ == "__main__":
    mcp.run()
