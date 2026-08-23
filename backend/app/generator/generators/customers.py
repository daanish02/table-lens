"""Generators for customers & parties domain."""

import numpy as np
import pandas as pd

from config import ROW_COUNTS, WIDE_EXTRA_COLUMNS
from generators.base import (
    city_series, clipped_normal, fake, foreign_keys, imbalanced_categories,
    inject_nulls, lognormal, random_dates, rng, seasonal_dates,
    sequential_ids, state_series, weighted_choice, generate_wide_columns,
    save_parquet,
)
from config import OUTPUT_DIR


def generate_customers() -> pd.DataFrame:
    """Synthetic customer records, one row per customer."""
    n = ROW_COUNTS["customers"]
    segments     = ["STANDARD", "PREFERRED", "VIP", "MASS_MARKET", "CORPORATE"]
    channels     = ["ONLINE", "AGENT", "BROKER", "DIRECT", "REFERRAL", "BANK"]
    risk_tiers   = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
    credit_bands = ["EXCELLENT", "GOOD", "FAIR", "POOR", "NO_HISTORY"]
    genders      = ["M", "F", "NB", "UNKNOWN"]
    marital      = ["SINGLE", "MARRIED", "DIVORCED", "WIDOWED", "SEPARATED"]

    dob = random_dates(n, 1940, 2000)
    acq_date = seasonal_dates(n, peak_months=[1, 3, 9, 10])

    df = pd.DataFrame({
        "customer_id":       sequential_ids(n),
        "customer_ref":      [f"CUST{i:08d}" for i in range(1, n + 1)],
        "first_name":        [fake.first_name() for _ in range(n)],
        "last_name":         [fake.last_name() for _ in range(n)],
        "date_of_birth":     dob,
        "gender":            weighted_choice(genders, [0.45, 0.45, 0.05, 0.05], n),
        "marital_status":    weighted_choice(marital, [0.30, 0.45, 0.12, 0.08, 0.05], n),
        "ssn_hash":          [fake.sha256()[:64] for _ in range(n)],
        "email":             [fake.email() for _ in range(n)],
        "phone_primary":     [fake.phone_number() for _ in range(n)],
        "phone_secondary":   inject_nulls(pd.Series([fake.phone_number() for _ in range(n)]), 0.60),
        "occupation":        [fake.job() for _ in range(n)],
        "employer_name":     inject_nulls(pd.Series([fake.company() for _ in range(n)]), 0.25),
        "annual_income":     lognormal(n, mean=65_000, sigma=0.8),
        "income_band":       weighted_choice(["<30K","30-60K","60-100K","100-200K",">200K"], [0.15,0.30,0.30,0.18,0.07], n),
        "address_line1":     [fake.street_address() for _ in range(n)],
        "address_line2":     inject_nulls(pd.Series([fake.secondary_address() for _ in range(n)]), 0.70),
        "city":              city_series(n),
        "state":             state_series(n),
        "zip_code":          [fake.zipcode() for _ in range(n)],
        "country":           "US",
        # Legacy mailing address — intentionally duplicated/denormalized
        "mail_address1":     inject_nulls(pd.Series([fake.street_address() for _ in range(n)]), 0.40),
        "mail_city":         inject_nulls(city_series(n), 0.40),
        "mail_state":        inject_nulls(state_series(n), 0.40),
        "mail_zip":          inject_nulls(pd.Series([fake.zipcode() for _ in range(n)]), 0.40),
        "customer_segment":  imbalanced_categories(segments, n, top_share=0.75),
        "acquisition_channel": weighted_choice(channels, [0.30, 0.25, 0.20, 0.10, 0.10, 0.05], n),
        "acquisition_date":  acq_date,
        "risk_tier":         weighted_choice(risk_tiers, [0.40, 0.35, 0.18, 0.07], n),
        "credit_score_band": weighted_choice(credit_bands, [0.25, 0.35, 0.25, 0.10, 0.05], n),
        "lifetime_value":    lognormal(n, mean=12_000, sigma=1.1),
        "churn_score":       np.round(rng.beta(2, 5, n), 4),
        "is_active":         weighted_choice([True, False], [0.88, 0.12], n),
        "is_vip":            weighted_choice([True, False], [0.05, 0.95], n),
        "created_at":        acq_date,
        "updated_at":        acq_date,
    })

    # Wide extra columns
    extra_df = pd.DataFrame(generate_wide_columns(n, WIDE_EXTRA_COLUMNS["customers"], "cust"))
    df = pd.concat([df, extra_df], axis=1)

    df.drop(columns=["ext_col_start"], errors="ignore")
    return df


def generate_customer_addresses() -> pd.DataFrame:
    """Synthetic customer address records (a customer can have several)."""
    n = ROW_COUNTS["customer_addresses"]
    n_customers = ROW_COUNTS["customers"]
    addr_types = ["MAILING", "BILLING", "PROPERTY", "PREVIOUS"]

    return pd.DataFrame({
        "address_id":    sequential_ids(n),
        "customer_id":   foreign_keys(n, n_customers),
        "address_type":  weighted_choice(addr_types, [0.35, 0.30, 0.25, 0.10], n),
        "address_line1": [fake.street_address() for _ in range(n)],
        "address_line2": inject_nulls(pd.Series([fake.secondary_address() for _ in range(n)]), 0.70),
        "city":          city_series(n),
        "state":         state_series(n),
        "zip_code":      [fake.zipcode() for _ in range(n)],
        "country":       "US",
        "is_current":    weighted_choice([True, False], [0.70, 0.30], n),
        "valid_from":    random_dates(n),
        "valid_to":      inject_nulls(pd.Series(random_dates(n)), 0.60),
        "created_at":    random_dates(n),
    })


def generate_customer_contacts() -> pd.DataFrame:
    """Synthetic customer contact-method records."""
    n = ROW_COUNTS["customer_contacts"]
    n_customers = ROW_COUNTS["customers"]
    contact_types = ["EMAIL", "MOBILE", "HOME", "WORK"]

    return pd.DataFrame({
        "contact_id":       sequential_ids(n),
        "customer_id":      foreign_keys(n, n_customers),
        "contact_type":     weighted_choice(contact_types, [0.35, 0.35, 0.15, 0.15], n),
        "contact_value":    [fake.email() if i % 3 == 0 else fake.phone_number() for i in range(n)],
        "is_primary":       weighted_choice([True, False], [0.40, 0.60], n),
        "is_verified":      weighted_choice([True, False], [0.70, 0.30], n),
        "opt_in_marketing": weighted_choice([True, False], [0.65, 0.35], n),
        "created_at":       random_dates(n),
    })


def generate_beneficiaries() -> pd.DataFrame:
    """Synthetic policy beneficiary records."""
    n = ROW_COUNTS["beneficiaries"]
    n_policies  = ROW_COUNTS["policies"]
    n_customers = ROW_COUNTS["customers"]
    rels = ["SPOUSE", "CHILD", "PARENT", "SIBLING", "ESTATE", "TRUST", "OTHER"]

    return pd.DataFrame({
        "beneficiary_id":  sequential_ids(n),
        "policy_id":       foreign_keys(n, n_policies),
        "customer_id":     inject_nulls(foreign_keys(n, n_customers), 0.30),
        "first_name":      [fake.first_name() for _ in range(n)],
        "last_name":       [fake.last_name() for _ in range(n)],
        "relationship":    weighted_choice(rels, [0.35, 0.30, 0.15, 0.10, 0.05, 0.03, 0.02], n),
        "date_of_birth":   inject_nulls(pd.Series(random_dates(n, 1940, 2005)), 0.20),
        "share_percentage": np.round(rng.uniform(10, 100, n), 2),
        "is_primary":      weighted_choice([True, False], [0.70, 0.30], n),
        "created_at":      random_dates(n),
    })


def generate_agents() -> pd.DataFrame:
    """Synthetic insurance agent records."""
    n = ROW_COUNTS["agents"]
    tiers  = ["BRONZE", "SILVER", "GOLD", "PLATINUM"]
    regions = ["NORTHEAST", "SOUTHEAST", "MIDWEST", "SOUTHWEST", "WEST"]

    hire_dates = random_dates(n, 2005, 2022)
    return pd.DataFrame({
        "agent_id":         sequential_ids(n),
        "agent_code":       [f"AGT{i:06d}" for i in range(1, n + 1)],
        "first_name":       [fake.first_name() for _ in range(n)],
        "last_name":        [fake.last_name() for _ in range(n)],
        "email":            [fake.company_email() for _ in range(n)],
        "phone":            [fake.phone_number() for _ in range(n)],
        "license_number":   [f"LIC{fake.bothify('??####??').upper()}" for _ in range(n)],
        "license_state":    state_series(n),
        "license_expiry":   random_dates(n, 2024, 2027),
        "agency_name":      [fake.company() for _ in range(n)],
        "region":           imbalanced_categories(regions, n),
        "manager_agent_id": inject_nulls(foreign_keys(n, n), 0.15),
        "commission_tier":  weighted_choice(tiers, [0.40, 0.35, 0.18, 0.07], n),
        "hire_date":        hire_dates,
        "is_active":        weighted_choice([True, False], [0.85, 0.15], n),
        "created_at":       hire_dates,
    })


def generate_agent_performance() -> pd.DataFrame:
    """Synthetic monthly agent-performance snapshot records."""
    n = ROW_COUNTS["agent_performance"]
    n_agents = ROW_COUNTS["agents"]

    years  = rng.integers(2015, 2025, n)
    months = rng.integers(1, 13, n)
    policies_sold = rng.integers(0, 30, n)
    # Seasonal: more policies sold in Q4
    q4_mask = months >= 10
    policies_sold[q4_mask] = (policies_sold[q4_mask] * 1.5).astype(int)

    return pd.DataFrame({
        "perf_id":            sequential_ids(n),
        "agent_id":           foreign_keys(n, n_agents),
        "period_year":        years,
        "period_month":       months,
        "policies_sold":      policies_sold,
        "policies_renewed":   rng.integers(0, 20, n),
        "policies_cancelled": rng.integers(0, 8, n),
        "total_premium":      lognormal(n, mean=45_000, sigma=0.9),
        "total_commission":   lognormal(n, mean=4_500, sigma=0.9),
        "claims_generated":   rng.integers(0, 10, n),
        "customer_satisfaction_score": np.round(clipped_normal(n, 3.8, 0.7, 1.0, 5.0), 2),
        "conversion_rate":    np.round(rng.beta(3, 5, n), 4),
        "created_at":         random_dates(n),
    })


def generate_third_parties() -> pd.DataFrame:
    """Synthetic third-party (claimants, witnesses, etc.) records."""
    n = ROW_COUNTS["third_parties"]
    types = ["CLAIMANT", "WITNESS", "LEGAL_REP", "EXPERT", "MEDICAL_PROVIDER"]

    return pd.DataFrame({
        "third_party_id": sequential_ids(n),
        "party_type":     weighted_choice(types, [0.40, 0.25, 0.15, 0.12, 0.08], n),
        "first_name":     inject_nulls(pd.Series([fake.first_name() for _ in range(n)]), 0.20),
        "last_name":      inject_nulls(pd.Series([fake.last_name() for _ in range(n)]), 0.20),
        "company_name":   inject_nulls(pd.Series([fake.company() for _ in range(n)]), 0.50),
        "phone":          inject_nulls(pd.Series([fake.phone_number() for _ in range(n)]), 0.35),
        "email":          inject_nulls(pd.Series([fake.email() for _ in range(n)]), 0.45),
        "address_line1":  inject_nulls(pd.Series([fake.street_address() for _ in range(n)]), 0.30),
        "city":           inject_nulls(city_series(n), 0.30),
        "state":          inject_nulls(state_series(n), 0.30),
        "zip_code":       inject_nulls(pd.Series([fake.zipcode() for _ in range(n)]), 0.30),
        "created_at":     random_dates(n),
    })


def generate_employers() -> pd.DataFrame:
    """Synthetic employer records."""
    n = ROW_COUNTS["employers"]
    industries = ["HEALTHCARE", "TECHNOLOGY", "FINANCE", "RETAIL", "MANUFACTURING",
                  "EDUCATION", "GOVERNMENT", "CONSTRUCTION", "HOSPITALITY", "TRANSPORT"]
    bands = ["1-10", "11-50", "51-200", "201-1000", "1000+"]

    return pd.DataFrame({
        "employer_id":          sequential_ids(n),
        "employer_name":        [fake.company() for _ in range(n)],
        "industry":             imbalanced_categories(industries, n),
        "sic_code":             [fake.numerify("####") for _ in range(n)],
        "address_line1":        [fake.street_address() for _ in range(n)],
        "city":                 city_series(n),
        "state":                state_series(n),
        "zip_code":             [fake.zipcode() for _ in range(n)],
        "employee_count_band":  weighted_choice(bands, [0.30, 0.35, 0.20, 0.10, 0.05], n),
        "group_policy_eligible": weighted_choice([True, False], [0.30, 0.70], n),
        "created_at":           random_dates(n),
    })


CUSTOMER_GENERATORS = {
    "customers":          generate_customers,
    "customer_addresses": generate_customer_addresses,
    "customer_contacts":  generate_customer_contacts,
    "beneficiaries":      generate_beneficiaries,
    "agents":             generate_agents,
    "agent_performance":  generate_agent_performance,
    "third_parties":      generate_third_parties,
    "employers":          generate_employers,
}
