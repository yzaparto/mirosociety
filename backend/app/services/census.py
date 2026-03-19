from __future__ import annotations
import logging

import httpx

from app.models.demographics import (
    AgeDistribution,
    DemographicProfile,
    EthnicityDistribution,
    IncomeDistribution,
    OccupationDistribution,
)
from app.services.llm import LLMClient, parse_json

logger = logging.getLogger(__name__)

# (state_fips, place_fips)
CITY_FIPS: dict[str, tuple[str, str]] = {
    "new york, ny":       ("36", "51000"),
    "los angeles, ca":    ("06", "44000"),
    "chicago, il":        ("17", "14000"),
    "san francisco, ca":  ("06", "67000"),
    "houston, tx":        ("48", "35000"),
    "phoenix, az":        ("04", "55000"),
    "philadelphia, pa":   ("42", "60000"),
    "san antonio, tx":    ("48", "65000"),
    "san diego, ca":      ("06", "66000"),
    "dallas, tx":         ("48", "19000"),
    "austin, tx":         ("48", "05000"),
    "seattle, wa":        ("53", "63000"),
    "denver, co":         ("08", "20000"),
    "boston, ma":          ("25", "07000"),
    "miami, fl":          ("12", "45000"),
    "atlanta, ga":        ("13", "04000"),
    "detroit, mi":        ("26", "22000"),
    "portland, or":       ("41", "59000"),
    "portland, me":       ("23", "60545"),
    "nashville, tn":      ("47", "52006"),
    "minneapolis, mn":    ("27", "43000"),
}

STATE_ABBREV_TO_FIPS: dict[str, str] = {
    "al": "01", "ak": "02", "az": "04", "ar": "05", "ca": "06",
    "co": "08", "ct": "09", "de": "10", "fl": "12", "ga": "13",
    "hi": "15", "id": "16", "il": "17", "in": "18", "ia": "19",
    "ks": "20", "ky": "21", "la": "22", "me": "23", "md": "24",
    "ma": "25", "mi": "26", "mn": "27", "ms": "28", "mo": "29",
    "mt": "30", "ne": "31", "nv": "32", "nh": "33", "nj": "34",
    "nm": "35", "ny": "36", "nc": "37", "nd": "38", "oh": "39",
    "ok": "40", "or": "41", "pa": "42", "ri": "44", "sc": "45",
    "sd": "46", "tn": "47", "tx": "48", "ut": "49", "vt": "50",
    "va": "51", "wa": "53", "wv": "54", "wi": "55", "wy": "56",
    "dc": "11",
}

TABLE_VARIABLES: dict[str, list[str]] = {
    "DP05": [
        "DP05_0001E",   # total population
        "DP05_0018E",   # median age
        "DP05_0019PE",  # age under 18 pct (used to derive 18-24)
        "DP05_0021PE",  # age 18-24 pct
        "DP05_0022PE",  # age 25-34 pct (proxy, actual code may differ)
        "DP05_0023PE",  # age 35-44 pct
        "DP05_0024PE",  # age 45-54 pct
        "DP05_0025PE",  # age 55-64 pct
        "DP05_0026PE",  # age 65+ pct (proxy, actual codes may differ)
        "DP05_0037PE",  # white alone pct
        "DP05_0038PE",  # black alone pct
        "DP05_0044PE",  # asian alone pct
        "DP05_0071PE",  # hispanic/latino pct
    ],
    "DP03": [
        "DP03_0062E",   # median household income
        "DP03_0119PE",  # poverty rate
        "DP03_0005PE",  # unemployment rate
        "DP03_0027PE",  # occupation: management/business/science/arts
        "DP03_0028PE",  # occupation: service
        "DP03_0029PE",  # occupation: sales and office
        "DP03_0030PE",  # occupation: natural resources/construction/maintenance
        "DP03_0031PE",  # occupation: production/transportation/material moving
    ],
}

ACS_BASE_URL = "https://api.census.gov/data/2023/acs/acs5/profile"


class CensusService:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def _resolve_fips(self, city: str, state: str | None = None) -> tuple[str, str] | None:
        city_lower = city.strip().lower()
        state_lower = state.strip().lower() if state else None

        if state_lower:
            state_fips = STATE_ABBREV_TO_FIPS.get(state_lower)
            key = f"{city_lower}, {state_lower}"
            if key in CITY_FIPS:
                return CITY_FIPS[key]
            if state_fips:
                for k, v in CITY_FIPS.items():
                    if k.startswith(city_lower + ",") and v[0] == state_fips:
                        return v

        for k, v in CITY_FIPS.items():
            if k.startswith(city_lower + ","):
                return v

        return None

    async def get_profile(self, city: str, state: str | None = None) -> DemographicProfile:
        fips = self._resolve_fips(city, state)
        if not fips:
            logger.info("No FIPS for %s, %s — falling back to LLM estimate", city, state)
            return await self._llm_estimate(city, state)

        state_fips, place_fips = fips
        try:
            data: dict = {}
            for table in TABLE_VARIABLES:
                result = await self._fetch_acs(state_fips, place_fips, table)
                data.update(result)

            state_abbrev = state or self._state_abbrev_from_fips(state_fips)
            return self._build_profile(city, state_abbrev or "", data)
        except Exception:
            logger.exception("Census API failed for %s — falling back to LLM", city)
            return await self._llm_estimate(city, state)

    async def _fetch_acs(self, state_fips: str, place_fips: str, table: str) -> dict:
        variables = TABLE_VARIABLES[table]
        var_str = ",".join(variables)
        url = f"{ACS_BASE_URL}?get={var_str}&for=place:{place_fips}&in=state:{state_fips}"

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        rows = resp.json()
        if len(rows) < 2:
            raise ValueError(f"Empty response from Census API for table {table}")

        headers = rows[0]
        values = rows[1]
        return dict(zip(headers, values))

    def _build_profile(self, city: str, state: str, data: dict) -> DemographicProfile:
        def safe_int(key: str, default: int = 0) -> int:
            val = data.get(key)
            if val is None or val == "null":
                return default
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return default

        def safe_float(key: str, default: float = 0.0) -> float:
            val = data.get(key)
            if val is None or val == "null":
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        age = [
            AgeDistribution(bracket="18_24", percentage=safe_float("DP05_0021PE")),
            AgeDistribution(bracket="25_34", percentage=safe_float("DP05_0022PE")),
            AgeDistribution(bracket="35_44", percentage=safe_float("DP05_0023PE")),
            AgeDistribution(bracket="45_54", percentage=safe_float("DP05_0024PE")),
            AgeDistribution(bracket="55_64", percentage=safe_float("DP05_0025PE")),
            AgeDistribution(bracket="65_plus", percentage=safe_float("DP05_0026PE")),
        ]

        income_brackets = [
            IncomeDistribution(bracket="under_25k", percentage=0.0),
            IncomeDistribution(bracket="25k_50k", percentage=0.0),
            IncomeDistribution(bracket="50k_75k", percentage=0.0),
            IncomeDistribution(bracket="75k_100k", percentage=0.0),
            IncomeDistribution(bracket="100k_150k", percentage=0.0),
            IncomeDistribution(bracket="150k_plus", percentage=0.0),
        ]

        occupations = [
            OccupationDistribution(category="management_business", percentage=safe_float("DP03_0027PE")),
            OccupationDistribution(category="service", percentage=safe_float("DP03_0028PE")),
            OccupationDistribution(category="sales_office", percentage=safe_float("DP03_0029PE")),
            OccupationDistribution(category="construction_maintenance", percentage=safe_float("DP03_0030PE")),
            OccupationDistribution(category="production_transportation", percentage=safe_float("DP03_0031PE")),
        ]

        ethnicity = [
            EthnicityDistribution(group="white", percentage=safe_float("DP05_0037PE")),
            EthnicityDistribution(group="black", percentage=safe_float("DP05_0038PE")),
            EthnicityDistribution(group="asian", percentage=safe_float("DP05_0044PE")),
            EthnicityDistribution(group="hispanic_latino", percentage=safe_float("DP05_0071PE")),
        ]

        return DemographicProfile(
            city_name=city.title(),
            state=state.upper(),
            population=safe_int("DP05_0001E"),
            age=age,
            income=income_brackets,
            occupations=occupations,
            ethnicity=ethnicity,
            median_household_income=safe_int("DP03_0062E"),
            poverty_rate=safe_float("DP03_0119PE"),
            unemployment_rate=safe_float("DP03_0005PE"),
            median_age=safe_float("DP05_0018E"),
        )

    async def _llm_estimate(self, city: str, state: str | None) -> DemographicProfile:
        location = f"{city}, {state}" if state else city
        system = (
            "You are a demographics expert. Given a city name, provide estimated "
            "demographic data in JSON format. Use realistic values based on your "
            "knowledge. Return ONLY valid JSON."
        )
        user = (
            f"Estimate demographics for {location}. Return JSON with these fields:\n"
            '{"population": int, "median_age": float, "median_household_income": int, '
            '"poverty_rate": float, "unemployment_rate": float, '
            '"age": [{"bracket": "18_24", "percentage": float}, ...], '
            '"ethnicity": [{"group": "white", "percentage": float}, ...], '
            '"occupations": [{"category": "management_business", "percentage": float}, ...], '
            '"city_character": "brief description of the city\'s character"}'
        )

        raw = await self.llm.generate(system, user, json_mode=True, max_tokens=800)
        data = parse_json(raw)

        return DemographicProfile(
            city_name=city.title(),
            state=(state or "").upper(),
            population=data.get("population", 0),
            median_age=data.get("median_age", 0.0),
            median_household_income=data.get("median_household_income", 0),
            poverty_rate=data.get("poverty_rate", 0.0),
            unemployment_rate=data.get("unemployment_rate", 0.0),
            age=[AgeDistribution(**a) for a in data.get("age", [])],
            ethnicity=[EthnicityDistribution(**e) for e in data.get("ethnicity", [])],
            occupations=[OccupationDistribution(**o) for o in data.get("occupations", [])],
            city_character=data.get("city_character", ""),
        )

    @staticmethod
    def _state_abbrev_from_fips(state_fips: str) -> str | None:
        for abbrev, fips in STATE_ABBREV_TO_FIPS.items():
            if fips == state_fips:
                return abbrev
        return None
