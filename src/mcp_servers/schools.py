import json
import re

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("schools")

OFSTED_LABELS = {
    "1": "Outstanding",
    "2": "Good",
    "3": "Requires Improvement",
    "4": "Inadequate",
}

SEARCH_URL = (
    "https://reports.ofsted.gov.uk/search"
    "?q={postcode}&distance={radius}&level_2_types%5B0%5D=1"
)

FALLBACK_URL = (
    "https://www.find-school-performance-data.service.gov.uk"
    "/search/results?searchtype=search-by-postcode"
    "&LocationSearchModel.Postcode={postcode}"
    "&LocationSearchModel.Distance={radius}"
)


def _parse_ofsted_page(html: str) -> list[dict]:
    """Parse the Ofsted reports search results page."""
    soup = BeautifulSoup(html, "html.parser")
    schools: list[dict] = []

    results = soup.select("ul.resultsList li, ul.results-list li, .search-result")
    if not results:
        results = soup.select("li.search-result, div.search-result, article")

    for item in results:
        name_el = item.select_one("h2 a, h3 a, .heading a, a.name")
        if not name_el:
            name_el = item.find("a")
        name = name_el.get_text(strip=True) if name_el else None
        if not name:
            continue

        text = item.get_text(" ", strip=True)

        rating = "Unknown"
        for label in ["Outstanding", "Good", "Requires Improvement", "Inadequate"]:
            if label.lower() in text.lower():
                rating = label
                break

        school_type = "Unknown"
        for t in [
            "Primary", "Secondary", "Academy", "Free School",
            "Independent", "Nursery", "Special", "Pupil Referral",
        ]:
            if t.lower() in text.lower():
                school_type = t
                break

        distance_match = re.search(r"([\d.]+)\s*(?:miles?|mi)", text, re.IGNORECASE)
        distance_mi = float(distance_match.group(1)) if distance_match else None

        schools.append({
            "name": name,
            "ofsted_rating": rating,
            "type": school_type,
            "distance_mi": distance_mi,
        })

    return schools


def _parse_performance_page(html: str) -> list[dict]:
    """Parse the Find School Performance Data results page."""
    soup = BeautifulSoup(html, "html.parser")
    schools: list[dict] = []

    rows = soup.select("div.school-result, tr.school, .result-item, li.result")
    if not rows:
        rows = soup.select("table tbody tr")

    for row in rows:
        name_el = row.select_one("a, .school-name, td:first-child")
        name = name_el.get_text(strip=True) if name_el else None
        if not name:
            continue

        text = row.get_text(" ", strip=True)

        rating = "Unknown"
        for label in ["Outstanding", "Good", "Requires Improvement", "Inadequate"]:
            if label.lower() in text.lower():
                rating = label
                break

        school_type = "Unknown"
        for t in ["Primary", "Secondary", "Academy", "Free School", "Independent"]:
            if t.lower() in text.lower():
                school_type = t
                break

        distance_match = re.search(r"([\d.]+)\s*(?:miles?|mi|km)", text, re.IGNORECASE)
        distance_mi = float(distance_match.group(1)) if distance_match else None

        schools.append({
            "name": name,
            "ofsted_rating": rating,
            "type": school_type,
            "distance_mi": distance_mi,
        })

    return schools


def _compute_average_ofsted(schools: list[dict]) -> float | None:
    """Compute numerical average Ofsted rating for schools with known ratings."""
    rating_to_num = {
        "Outstanding": 1,
        "Good": 2,
        "Requires Improvement": 3,
        "Inadequate": 4,
    }
    values = [
        rating_to_num[s["ofsted_rating"]]
        for s in schools
        if s["ofsted_rating"] in rating_to_num
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


@mcp.tool()
async def get_nearby_schools(postcode: str, radius_km: float = 1.0) -> str:
    """Find nearby schools with Ofsted ratings for a UK postcode.

    Args:
        postcode: UK postcode to search around (e.g. 'SW1A 1AA').
        radius_km: Search radius in kilometres (default 1.0).

    Returns:
        JSON string with schools list, average_ofsted_rating,
        num_schools_nearby, and best_school.
    """
    encoded_postcode = postcode.replace(" ", "+")
    radius_mi = round(radius_km * 0.621371, 1)

    schools: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            # Try Ofsted reports search first
            url = SEARCH_URL.format(postcode=encoded_postcode, radius=radius_mi)
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )
            if resp.status_code == 200:
                schools = _parse_ofsted_page(resp.text)

            # Fall back to performance data site if no results
            if not schools:
                url = FALLBACK_URL.format(
                    postcode=encoded_postcode, radius=radius_km,
                )
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                    },
                )
                if resp.status_code == 200:
                    schools = _parse_performance_page(resp.text)

    except httpx.TimeoutException:
        return json.dumps({"error": f"Request timed out searching schools near {postcode}"})
    except httpx.HTTPError as exc:
        return json.dumps({"error": f"HTTP error searching schools: {exc}"})

    if not schools:
        return json.dumps({
            "schools": [],
            "num_schools_nearby": 0,
            "average_ofsted_rating": None,
            "best_school": None,
            "message": (
                f"No schools found near {postcode} within {radius_km} km. "
                "The search pages may have changed structure."
            ),
        })

    avg_rating = _compute_average_ofsted(schools)

    rating_priority = {
        "Outstanding": 0,
        "Good": 1,
        "Requires Improvement": 2,
        "Inadequate": 3,
        "Unknown": 4,
    }
    best = min(schools, key=lambda s: rating_priority.get(s["ofsted_rating"], 5))

    return json.dumps({
        "schools": schools,
        "num_schools_nearby": len(schools),
        "average_ofsted_rating": avg_rating,
        "best_school": best,
    }, indent=2)


if __name__ == "__main__":
    mcp.run()
