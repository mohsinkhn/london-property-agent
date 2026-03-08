---
name: property-search
description: Search for properties on Rightmove and Zoopla matching buyer criteria. Use this when you need to find property listings in London areas with specific budget, bedroom, and property type requirements.
---

# Property Search

Search for properties across Rightmove and Zoopla, deduplicate results by address.

## Steps

1. For each area in the buyer's search criteria, call `search_rightmove` with the area code, max price, min bedrooms, and property type.
2. For each area, also call `search_zoopla` with equivalent parameters.
3. Merge results from both sources. Deduplicate by normalizing addresses (lowercase, strip whitespace) — if same address appears on both portals, keep the Rightmove version but note it's listed on both.
4. Filter out any SSTC (Sold Subject to Contract) properties.
5. Sort by price ascending.
6. Return the merged list with: address, price, bedrooms, bathrooms, property type, latitude, longitude, listing URL, source (rightmove/zoopla/both).

## Notes
- Rightmove location identifiers are typically area codes like "SE15" or "REGION^1234".
- If a search returns 0 results, try broadening the radius.
- Cap at 30 properties per area to keep enrichment manageable.
