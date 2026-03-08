# London Property Hunter — Agent Memory

This file serves as persistent memory for the property hunting agent.
It is loaded automatically via `setting_sources=["project"]`.
The agent should UPDATE this file as it learns from user interactions.

## User Preferences (learned from interactions)

<!-- The agent should add/update entries here as it discovers user preferences -->
<!-- Format: - **preference_name**: value (learned from: context) -->

## Location Disambiguation

<!-- When a location query is ambiguous (e.g. "Kings Cross" could be station or area),
     record the user's preferred interpretation here so future searches use it directly. -->
<!-- Format: - "ambiguous_term" → resolved_value (e.g. lat,lng or station ID) -->

- "Kings Cross" → 51.5308,-0.1238 (King's Cross station coordinates)

## Search History

<!-- Recent searches and their outcomes, so the agent can learn what works -->
<!-- Format: - YYYY-MM-DD: areas, budget, outcome summary -->

- 2026-03-08: SE15 (Peckham), budget £600k, 2+ beds, house/flat, commute Kings Cross ≤45min.
  9 properties found via web-search fallback (Rightmove search API returned 0 results).
  Top result: Peckham Rye top-floor flat £375k (Rightmove #163122380, score 61.1).
  SE15 area avg sold ~£462k; crime consistently HIGH across all SE15 sub-areas.

## Scoring Adjustments

<!-- If the user overrides default scoring weights or says things like
     "I care more about schools than commute", record it here -->

- 2026-03-08 search: value=0.25, commute=0.25, crime=0.15, schools=0.15, epc=0.10, size=0.10

## Blacklisted Properties / Areas

<!-- Properties or areas the user has rejected, so we don't show them again -->

## Agent Notes

<!-- Any other learned patterns: preferred property types, deal-breakers,
     things the user has explicitly said to remember -->

- **Rightmove Search API**: Returns 0 results consistently (Mar 2026). Use web search fallback to find listing IDs, then enrich manually.
- **Zoopla API**: Subscription expired (Mar 2026). Cross-check listings via web search instead.
- **TfL API**: Rate-limits (429) when called in parallel. Try sequential calls with delays. As fallback, use transport knowledge (SE15→KGX ~33–43 min depending on proximity to Peckham Rye / Queens Road Peckham stations).
- **EPC API**: Requires EPC_API_EMAIL + EPC_API_TOKEN env vars — not configured. Apply neutral 50/100 until credentials added.
- **Schools API**: Returns non-local schools for most SE15 postcodes. SE15 3JN was the exception (Angel Oak Academy Outstanding, Bellenden Primary Good, Bird in Bush Good). Use SE15 3JN result as proxy for SE15 3/5 area. Known SE15 outstanding primaries: Angel Oak Academy, Ivydale Primary, John Donne Primary.
- **Land Registry**: Good data for SE15 2ND (avg £416k, flats), SE15 2NB (Kings Grove, avg £637k incl. houses; flat comparables £333–377k), SE15 3JN (avg £399k, flats). Sparse/anomalous for SE15 3PT, SE15 5BD, SE15 6JH — use SE15 broad avg £462k as fallback.
- **SE15 crime**: All sub-areas score "high" risk. Relative range Jan-2026: 734 (Rye Hill Park, lowest) to 1152 (Peckham Grove/South City Court, highest). Use relative scoring within dataset (1500 crime cap) for meaningful differentiation.
- **SE15 commute reference**: Peckham Rye station (Zone 2) → KGX: ~33–36 min (Ovgd → Canada Water → Jubilee). Queens Road Peckham → KGX: ~38–40 min (train → London Bridge → Northern). Nunhead station → KGX: ~42–45 min.
