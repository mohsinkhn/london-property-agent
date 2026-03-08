"""MCP server for retrieving sold house prices from HM Land Registry's Linked Data API."""

import json
import statistics
from datetime import datetime, timedelta
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("land_registry")


def _format_postcode(postcode: str) -> str:
    """Format a postcode to uppercase with a single space before the last 3 characters."""
    clean = postcode.strip().upper().replace(" ", "")
    if len(clean) < 5:
        return clean
    return f"{clean[:-3]} {clean[-3:]}"


@mcp.tool()
async def get_sold_prices(
    postcode: str, years_back: int = 3, property_type: str = ""
) -> str:
    """Get sold house prices from HM Land Registry for a given postcode.

    Args:
        postcode: UK postcode to search (e.g. "SE15 5AA").
        years_back: Number of years to look back (default 3).
        property_type: Optional property type filter.

    Returns:
        JSON string with transaction data and price statistics.
    """
    formatted_postcode = _format_postcode(postcode)
    start_date = (datetime.now() - timedelta(days=years_back * 365)).strftime("%Y-%m-%d")

    sparql_query = f"""PREFIX lrppi: <http://landregistry.data.gov.uk/def/ppi/>
PREFIX lrcommon: <http://landregistry.data.gov.uk/def/common/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?address ?price ?date ?type
WHERE {{
  ?transaktion lrppi:pricePaid ?price ;
               lrppi:transactionDate ?date ;
               lrppi:propertyAddress ?addr ;
               lrppi:propertyType ?type .
  ?addr lrcommon:postcode "{formatted_postcode}" ;
        lrcommon:paon ?paon ;
        lrcommon:street ?street .
  BIND(CONCAT(?paon, " ", ?street) AS ?address)
  FILTER(?date >= "{start_date}"^^xsd:date)
}}
ORDER BY DESC(?date)
LIMIT 50"""

    endpoint = "https://landregistry.data.gov.uk/landregistry/query"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                endpoint,
                data={"query": sparql_query},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/sparql-results+json",
                },
            )
            response.raise_for_status()
    except httpx.TimeoutException:
        return json.dumps({"error": f"Request timed out querying Land Registry for {formatted_postcode}"})
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"HTTP error {e.response.status_code} from Land Registry API"})
    except httpx.RequestError as e:
        return json.dumps({"error": f"Request error querying Land Registry: {str(e)}"})

    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError):
        return json.dumps({"error": "Failed to parse response from Land Registry API"})

    bindings = data.get("results", {}).get("bindings", [])

    transactions = []
    prices = []
    for binding in bindings:
        price = int(float(binding["price"]["value"]))
        prices.append(price)
        transactions.append(
            {
                "address": binding["address"]["value"],
                "price": price,
                "date": binding["date"]["value"],
                "property_type": binding["type"]["value"].split("/")[-1] if "type" in binding else "",
            }
        )

    if prices:
        average_price = round(statistics.mean(prices))
        median_price = round(statistics.median(prices))
    else:
        average_price = 0
        median_price = 0

    result = {
        "postcode": formatted_postcode,
        "num_transactions": len(transactions),
        "average_price": average_price,
        "median_price": median_price,
        "transactions": transactions,
    }

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run()
