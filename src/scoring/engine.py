"""Weighted scoring engine for property ranking."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PropertyScore:
    """Score breakdown for a single property."""

    address: str
    price: int
    value_score: float = 0.0       # 0-100: how good is price vs area avg
    commute_score: float = 0.0     # 0-100: shorter = better
    crime_score: float = 0.0       # 0-100: less crime = better
    schools_score: float = 0.0     # 0-100: higher ofsted = better
    epc_score: float = 0.0         # 0-100: better rating = better
    size_score: float = 0.0        # 0-100: more space = better
    total_score: float = 0.0
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "price": self.price,
            "scores": {
                "value": round(self.value_score, 1),
                "commute": round(self.commute_score, 1),
                "crime": round(self.crime_score, 1),
                "schools": round(self.schools_score, 1),
                "epc": round(self.epc_score, 1),
                "size": round(self.size_score, 1),
                "total": round(self.total_score, 1),
            },
            "raw": self.raw_data,
        }


# --- Individual dimension scorers ---

def score_value(asking_price: int, area_avg_price: int) -> float:
    """Score 0-100 based on how asking price compares to area average.
    At average = 50, 20% below = 100, 20% above = 0."""
    if area_avg_price <= 0:
        return 50.0
    ratio = asking_price / area_avg_price
    # Linear scale: ratio 0.8 -> 100, ratio 1.0 -> 50, ratio 1.2 -> 0
    score = max(0.0, min(100.0, (1.2 - ratio) / 0.4 * 100))
    return score


def score_commute(commute_mins: int, max_commute: int) -> float:
    """Score 0-100 based on commute time. 0 min = 100, max_commute = 20, over max = 0."""
    if commute_mins <= 0:
        return 100.0
    if commute_mins >= max_commute * 1.5:
        return 0.0
    if commute_mins >= max_commute:
        # Penalise but don't zero out immediately
        return max(0.0, 20.0 * (1 - (commute_mins - max_commute) / (max_commute * 0.5)))
    # Linear from 100 (0 min) to 20 (max_commute)
    return 100.0 - (commute_mins / max_commute) * 80.0


def score_crime(total_crimes: int) -> float:
    """Score 0-100 based on total monthly crimes in area.
    0 crimes = 100, 100+ crimes = 0."""
    return max(0.0, min(100.0, 100.0 - total_crimes))


EPC_SCORES = {"A": 100, "B": 85, "C": 70, "D": 55, "E": 40, "F": 25, "G": 10}


def score_epc(rating: str) -> float:
    """Score 0-100 based on EPC rating letter."""
    return float(EPC_SCORES.get(rating.upper().strip(), 50))


OFSTED_MAP = {"Outstanding": 100, "Good": 70, "Requires improvement": 35, "Inadequate": 10}


def score_schools(avg_ofsted: str | float) -> float:
    """Score 0-100 based on average nearby school Ofsted rating.
    Accepts string rating or numeric 1-4 scale."""
    if isinstance(avg_ofsted, str):
        return float(OFSTED_MAP.get(avg_ofsted, 50))
    # Numeric: 1=Outstanding(100), 2=Good(70), 3=RI(35), 4=Inadequate(10)
    if avg_ofsted <= 1:
        return 100.0
    if avg_ofsted >= 4:
        return 10.0
    # Interpolate
    return max(10.0, 100.0 - (avg_ofsted - 1) * 30.0)


def score_size(bedrooms: int, sqft: float = 0) -> float:
    """Score 0-100 based on size. More beds and space = better."""
    bed_score = min(100.0, bedrooms * 20.0)  # 5+ beds = 100
    if sqft > 0:
        sqft_score = min(100.0, sqft / 15.0)  # 1500 sqft = 100
        return (bed_score + sqft_score) / 2
    return bed_score


def compute_total(
    ps: PropertyScore,
    w_value: float = 0.25,
    w_commute: float = 0.25,
    w_crime: float = 0.15,
    w_schools: float = 0.15,
    w_epc: float = 0.10,
    w_size: float = 0.10,
) -> float:
    """Compute weighted total score."""
    ps.total_score = (
        ps.value_score * w_value
        + ps.commute_score * w_commute
        + ps.crime_score * w_crime
        + ps.schools_score * w_schools
        + ps.epc_score * w_epc
        + ps.size_score * w_size
    )
    return ps.total_score
