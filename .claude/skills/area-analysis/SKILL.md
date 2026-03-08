---
name: area-analysis
description: Analyse a London area or postcode district to provide an overview of property market, safety, schools, and transport. Use this when the buyer wants to understand a neighbourhood before committing to a search.
---

# Area Analysis

Provide a comprehensive overview of a London area/postcode district.

## Steps

1. **Market Data** — Use `get_sold_prices(postcode_prefix)` to get recent transaction history. Calculate average prices by property type, price trends (comparing recent 12mo vs prior 12mo).

2. **Safety** — Use `get_crime_stats` for a central point in the area. Summarize crime levels and dominant categories.

3. **Schools** — Use `get_nearby_schools` for the area's central postcode. List top-rated schools.

4. **Transport** — Use `get_commute_time` from the area to 2-3 common London hubs (King's Cross, Liverpool Street, Waterloo) to give a commute profile.

5. **Summary** — Synthesize into a concise area profile: who it's good for, price range, vibe, pros/cons.

## Output Format

Structured area report with sections for each dimension, plus an overall recommendation.
