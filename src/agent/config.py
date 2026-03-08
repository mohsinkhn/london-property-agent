"""Search configuration for the property hunting agent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PropertySearchConfig(BaseModel):
    """User's property search criteria."""

    areas: list[str] = Field(
        description="London areas/postcodes to search (e.g. ['SE15', 'SE22', 'E8'])"
    )
    max_price: int = Field(description="Maximum budget in GBP")
    min_beds: int = Field(default=2, description="Minimum number of bedrooms")
    max_beds: int | None = Field(default=None, description="Maximum bedrooms (None=no limit)")
    property_types: list[str] = Field(
        default=["house", "flat"],
        description="Property types to include",
    )
    commute_target: str = Field(
        description="Destination postcode/station for commute calculation"
    )
    max_commute_mins: int = Field(
        default=45, description="Maximum acceptable commute in minutes"
    )
    arrival_time: str = Field(
        default="0900", description="Desired arrival time (HHMM) for commute calc"
    )

    # Scoring weights (must sum to 1.0)
    weight_value: float = Field(default=0.25, description="Weight: value vs area average")
    weight_commute: float = Field(default=0.25, description="Weight: commute time")
    weight_crime: float = Field(default=0.15, description="Weight: crime stats")
    weight_schools: float = Field(default=0.15, description="Weight: school ratings")
    weight_epc: float = Field(default=0.10, description="Weight: energy performance")
    weight_size: float = Field(default=0.10, description="Weight: property size/rooms")

    def to_prompt(self) -> str:
        areas_str = ", ".join(self.areas)
        types_str = ", ".join(self.property_types)
        beds_str = f"{self.min_beds}+" if self.max_beds is None else f"{self.min_beds}-{self.max_beds}"
        return (
            f"Search for {types_str} in London areas: {areas_str}. "
            f"Budget: up to £{self.max_price:,}. "
            f"Bedrooms: {beds_str}. "
            f"Commute target: {self.commute_target} (arrive by {self.arrival_time}, max {self.max_commute_mins} min). "
            f"Scoring weights: value={self.weight_value}, commute={self.weight_commute}, "
            f"crime={self.weight_crime}, schools={self.weight_schools}, "
            f"epc={self.weight_epc}, size={self.weight_size}."
        )
