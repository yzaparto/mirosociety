"""Tests for CensusService FIPS resolution and DemographicProfile model."""
from __future__ import annotations

import pytest

from app.models.demographics import (
    AgeDistribution,
    DemographicProfile,
    EthnicityDistribution,
    IncomeDistribution,
    OccupationDistribution,
)
from app.services.census import CensusService


@pytest.fixture
def service():
    return CensusService(llm=None)


# ── FIPS resolution ──────────────────────────────────────────────────────────

class TestResolveFips:
    def test_known_city_san_francisco(self, service):
        result = service._resolve_fips("san francisco", "ca")
        assert result == ("06", "67000")

    def test_known_city_new_york(self, service):
        result = service._resolve_fips("new york", "ny")
        assert result == ("36", "51000")

    def test_known_city_chicago(self, service):
        result = service._resolve_fips("chicago", "il")
        assert result == ("17", "14000")

    def test_unknown_city_returns_none(self, service):
        result = service._resolve_fips("nonexistent city", "zz")
        assert result is None

    def test_unknown_city_no_state_returns_none(self, service):
        result = service._resolve_fips("timbuktu")
        assert result is None

    def test_case_insensitive_upper(self, service):
        result = service._resolve_fips("San Francisco", "CA")
        assert result == ("06", "67000")

    def test_case_insensitive_mixed(self, service):
        result = service._resolve_fips("NEW YORK", "NY")
        assert result == ("36", "51000")

    def test_case_insensitive_no_state(self, service):
        result = service._resolve_fips("Seattle")
        assert result == ("53", "63000")

    def test_portland_disambiguated_oregon(self, service):
        result = service._resolve_fips("portland", "or")
        assert result == ("41", "59000")

    def test_portland_disambiguated_maine(self, service):
        result = service._resolve_fips("portland", "me")
        assert result == ("23", "60545")

    def test_whitespace_stripped(self, service):
        result = service._resolve_fips("  boston  ", "  ma  ")
        assert result == ("25", "07000")


# ── DemographicProfile model ────────────────────────────────────────────────

class TestDemographicProfile:
    def test_full_construction(self):
        profile = DemographicProfile(
            city_name="Test City",
            state="TX",
            population=500000,
            age=[AgeDistribution(bracket="18_24", percentage=12.5)],
            income=[IncomeDistribution(bracket="50k_75k", percentage=22.0)],
            occupations=[OccupationDistribution(category="service", percentage=18.3)],
            ethnicity=[EthnicityDistribution(group="white", percentage=55.0)],
            median_household_income=65000,
            poverty_rate=14.2,
            unemployment_rate=5.1,
            homeownership_rate=58.0,
            median_rent=1200,
            rent_burden_rate=42.0,
            college_education_rate=33.5,
            median_age=34.7,
            city_character="A vibrant test city",
        )
        assert profile.city_name == "Test City"
        assert profile.population == 500000
        assert len(profile.age) == 1
        assert profile.age[0].bracket == "18_24"
        assert profile.median_household_income == 65000
        assert profile.city_character == "A vibrant test city"

    def test_defaults(self):
        profile = DemographicProfile(
            city_name="Minimal",
            state="CA",
            population=1000,
        )
        assert profile.age == []
        assert profile.income == []
        assert profile.occupations == []
        assert profile.ethnicity == []
        assert profile.median_household_income == 0
        assert profile.poverty_rate == 0.0
        assert profile.unemployment_rate == 0.0
        assert profile.homeownership_rate == 0.0
        assert profile.median_rent == 0
        assert profile.rent_burden_rate == 0.0
        assert profile.college_education_rate == 0.0
        assert profile.median_age == 0.0
        assert profile.city_character == ""
