---
name: score-and-rank
description: Score and rank enriched properties using a weighted multi-dimensional model. Use this after enriching properties to produce a final ranked recommendation list.
---

# Score and Rank Properties

Apply a weighted scoring model to rank enriched properties.

## Scoring Dimensions (each 0-100)

1. **Value** (default weight 0.25): Compare asking price to area average sold price.
   - At area average = 50. 20% below = 100. 20% above = 0.

2. **Commute** (default weight 0.25): Based on journey time to buyer's target.
   - 0 min = 100. At max acceptable = 20. Over 1.5x max = 0.

3. **Crime** (default weight 0.15): Based on total monthly crimes nearby.
   - 0 crimes = 100. 100+ crimes = 0. Linear scale.

4. **Schools** (default weight 0.15): Based on average nearby Ofsted rating.
   - Outstanding = 100. Good = 70. Requires Improvement = 35. Inadequate = 10.

5. **EPC** (default weight 0.10): Based on energy rating letter.
   - A=100, B=85, C=70, D=55, E=40, F=25, G=10.

6. **Size** (default weight 0.10): Based on bedrooms and floor area.
   - 5+ beds = 100 (bed component). 1500+ sqft = 100 (area component).

## Output

Return the **top 10** properties ranked by total weighted score. For each:
- Rank, address, price, bedrooms, property type
- Total score and per-dimension score breakdown
- 1-2 sentence summary of key pros/cons
- Listing URL
- Key data: commute time, crime level, best school, EPC rating, area avg price

If the buyer specified custom weights, use those instead of defaults.
