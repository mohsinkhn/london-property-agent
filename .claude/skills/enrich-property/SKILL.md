---
name: enrich-property
description: Enrich a property listing with commute time, crime stats, school ratings, sold prices, and EPC data. Use this after searching for properties to add location intelligence to each listing.
---

# Enrich Property

Given a property (with address, postcode, lat/lng), gather all location intelligence data.

## Steps

For each property, call these tools (can be done in parallel where possible):

1. **Commute** — `get_commute_time(from_postcode, to_target, arrival_time)` via the tfl MCP server. Extract the best journey duration and route summary.

2. **Crime** — `get_crime_stats(lat, lng)` via the crime MCP server. Note total crimes, top categories, and risk level.

3. **Schools** — `get_nearby_schools(postcode)` via the schools MCP server. Note the average Ofsted rating and the best nearby school.

4. **Sold Prices** — `get_sold_prices(postcode, years_back=3)` via the land_registry MCP server. Note average and median sold prices for the area.

5. **EPC** — `get_epc_rating(postcode, address_fragment)` via the epc MCP server. Note the energy rating (A-G) and floor area.

## Output Format

For each property, produce an enrichment record:
- commute_mins, commute_route
- crime_total, crime_risk_level, crime_top_categories
- schools_avg_ofsted, best_school_name, best_school_rating
- area_avg_sold_price, area_median_sold_price
- epc_rating, floor_area_sqm

## Error Handling
- If any enrichment tool fails, record "unavailable" for that dimension and continue.
- Do not skip a property just because one enrichment fails.
