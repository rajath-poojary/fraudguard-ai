from typing import Literal

from pydantic import BaseModel, Field


class FeatureAttribution(BaseModel):
    feature: str
    direction: Literal["increases_risk", "decreases_risk", "above_baseline", "below_baseline"]
    contribution: float
    relative_contribution: float = Field(ge=0, le=1)
    source: str