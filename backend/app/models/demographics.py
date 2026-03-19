from __future__ import annotations
from pydantic import BaseModel, Field


class AgeDistribution(BaseModel):
    bracket: str
    percentage: float


class IncomeDistribution(BaseModel):
    bracket: str
    percentage: float


class OccupationDistribution(BaseModel):
    category: str
    percentage: float


class EthnicityDistribution(BaseModel):
    group: str
    percentage: float


class DemographicProfile(BaseModel):
    city_name: str
    state: str
    population: int
    age: list[AgeDistribution] = Field(default_factory=list)
    income: list[IncomeDistribution] = Field(default_factory=list)
    occupations: list[OccupationDistribution] = Field(default_factory=list)
    ethnicity: list[EthnicityDistribution] = Field(default_factory=list)
    median_household_income: int = 0
    poverty_rate: float = 0.0
    unemployment_rate: float = 0.0
    homeownership_rate: float = 0.0
    median_rent: int = 0
    rent_burden_rate: float = 0.0
    college_education_rate: float = 0.0
    median_age: float = 0.0
    city_character: str = ""
