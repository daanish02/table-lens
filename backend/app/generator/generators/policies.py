"""Generators for policies domain."""

import numpy as np
import pandas as pd

from config import ROW_COUNTS, WIDE_EXTRA_COLUMNS, CANCELLATION_RATE, RENEWAL_RATE
from generators.base import (
    city_series, fake, foreign_keys, future_dates, generate_wide_columns,
    inject_nulls, lognormal, random_dates, rng, seasonal_dates,
    sequential_ids, state_series, weighted_choice,
)


def generate_products() -> pd.DataFrame:
    n = ROW_COUNTS["products"]
    categories = ["AUTO", "HOME", "LIFE", "HEALTH", "COMMERCIAL", "TRAVEL", "LIABILITY"]
    rows = []
    prod_id = 1
    for cat in categories:
        count = max(1, n // len(categories))
        for j in range(count):
            rows.append({
                "product_id":       prod_id,
                "product_code":     f"{cat[:3]}{prod_id:04d}",
                "product_name":     f"{cat.title()} {fake.bs().title()[:30]}",
                "product_category": cat,
                "product_line":     weighted_choice(["PERSONAL", "COMMERCIAL", "GROUP"], [0.60, 0.30, 0.10], 1)[0],
                "is_active":        True if j < count - 1 else False,
                "min_sum_insured":  round(float(rng.uniform(5_000, 50_000)), 2),
                "max_sum_insured":  round(float(rng.uniform(500_000, 5_000_000)), 2),
                "base_rate":        round(float(rng.uniform(0.001, 0.05)), 4),
                "created_at":       random_dates(1).iloc[0],
            })
            prod_id += 1
    return pd.DataFrame(rows[:n])


def generate_policies() -> pd.DataFrame:
    n = ROW_COUNTS["policies"]
    n_customers = ROW_COUNTS["customers"]
    n_products  = ROW_COUNTS["products"]
    n_agents    = ROW_COUNTS["agents"]

    statuses   = ["ACTIVE", "LAPSED", "CANCELLED", "EXPIRED", "PENDING"]
    pay_freqs  = ["MONTHLY", "QUARTERLY", "ANNUAL", "SEMI_ANNUAL"]
    pay_methods = ["DIRECT_DEBIT", "CREDIT_CARD", "BANK_TRANSFER", "CHEQUE"]
    channels   = ["ONLINE", "AGENT", "BROKER", "DIRECT", "BANK"]

    inception = seasonal_dates(n, peak_months=[1, 3, 6, 9, 10])
    expiry    = future_dates(inception, min_days=180, max_days=730)
    cancel_mask = rng.random(n) < CANCELLATION_RATE
    cancel_dates = pd.Series([
        inception.iloc[i] + pd.Timedelta(days=int(rng.integers(30, 300)))
        if cancel_mask[i] else None
        for i in range(n)
    ])

    annual_premium = lognormal(n, mean=1_800, sigma=0.85)
    tax_rate       = rng.uniform(0.02, 0.08, n)
    discount       = rng.uniform(0, 0.15, n)

    gross  = annual_premium * (1 - discount)
    tax    = gross * tax_rate
    net    = gross - tax

    df = pd.DataFrame({
        "policy_id":        sequential_ids(n),
        "policy_number":    [f"POL{i:010d}" for i in range(1, n + 1)],
        "customer_id":      foreign_keys(n, n_customers),
        "product_id":       foreign_keys(n, n_products),
        "agent_id":         inject_nulls(foreign_keys(n, n_agents), 0.10),
        "quote_date":       pd.Series([
            inception.iloc[i] - pd.Timedelta(days=int(rng.integers(1, 30)))
            for i in range(n)
        ]),
        "inception_date":   inception,
        "expiry_date":      expiry,
        "cancellation_date": cancel_dates,
        "policy_status":    pd.Series([
            "CANCELLED" if cancel_mask[i]
            else weighted_choice(statuses, [0.65, 0.10, 0.05, 0.15, 0.05], 1)[0]
            for i in range(n)
        ]),
        "payment_frequency": weighted_choice(pay_freqs, [0.45, 0.20, 0.25, 0.10], n),
        "payment_method":   weighted_choice(pay_methods, [0.40, 0.30, 0.20, 0.10], n),
        "annual_premium":   np.round(annual_premium, 2),
        "gross_premium":    np.round(gross, 2),
        "net_premium":      np.round(net, 2),
        "tax_amount":       np.round(tax, 2),
        "discount_amount":  np.round(annual_premium * discount, 2),
        "sum_insured":      lognormal(n, mean=250_000, sigma=1.2),
        "deductible_amount": lognormal(n, mean=500, sigma=0.7),
        "covers_property":  weighted_choice([True, False], [0.40, 0.60], n),
        "covers_vehicle":   weighted_choice([True, False], [0.45, 0.55], n),
        "covers_life":      weighted_choice([True, False], [0.25, 0.75], n),
        "covers_health":    weighted_choice([True, False], [0.30, 0.70], n),
        "covers_liability": weighted_choice([True, False], [0.35, 0.65], n),
        "insured_address1": [fake.street_address() for _ in range(n)],
        "insured_city":     city_series(n),
        "insured_state":    state_series(n),
        "insured_zip":      [fake.zipcode() for _ in range(n)],
        "underwriter_id":   inject_nulls(foreign_keys(n, 500), 0.05),
        "channel":          weighted_choice(channels, [0.30, 0.25, 0.20, 0.15, 0.10], n),
        "created_at":       inception,
        "updated_at":       inception,
    })

    extra_df = pd.DataFrame(generate_wide_columns(n, WIDE_EXTRA_COLUMNS["policies"], "pol"))
    df = pd.concat([df, extra_df], axis=1)

    return df


def generate_policy_versions() -> pd.DataFrame:
    n = ROW_COUNTS["policy_versions"]
    n_policies = ROW_COUNTS["policies"]
    change_types = ["ENDORSEMENT", "RENEWAL", "CORRECTION", "CANCELLATION", "REINSTATEMENT"]

    old_prem = lognormal(n, mean=1_800, sigma=0.85)
    change   = rng.normal(0, 150, n)
    new_prem = np.round(np.maximum(old_prem + change, 100), 2)

    return pd.DataFrame({
        "version_id":      sequential_ids(n),
        "policy_id":       foreign_keys(n, n_policies),
        "version_number":  rng.integers(1, 15, n),
        "change_type":     weighted_choice(change_types, [0.35, 0.30, 0.20, 0.10, 0.05], n),
        "changed_by":      [fake.name() for _ in range(n)],
        "change_reason":   inject_nulls(pd.Series([fake.sentence(nb_words=8) for _ in range(n)]), 0.25),
        "previous_premium": np.round(old_prem, 2),
        "new_premium":      new_prem,
        "effective_date":   random_dates(n),
        "created_at":       random_dates(n),
    })


def generate_policy_endorsements() -> pd.DataFrame:
    n = ROW_COUNTS["policy_endorsements"]
    n_policies = ROW_COUNTS["policies"]
    types = ["ADD_DRIVER", "ADD_PROPERTY", "INCREASE_LIMIT", "REDUCE_DEDUCTIBLE",
             "ADD_RIDER", "REMOVE_EXCLUSION", "ADD_COVERAGE"]

    eff_date = random_dates(n)
    return pd.DataFrame({
        "endorsement_id":    sequential_ids(n),
        "policy_id":         foreign_keys(n, n_policies),
        "endorsement_type":  weighted_choice(types, [0.20, 0.15, 0.20, 0.15, 0.15, 0.10, 0.05], n),
        "description":       inject_nulls(pd.Series([fake.sentence() for _ in range(n)]), 0.30),
        "premium_adjustment": np.round(rng.normal(0, 200, n), 2),
        "effective_date":    eff_date,
        "expiry_date":       future_dates(eff_date, 30, 365),
        "is_active":         weighted_choice([True, False], [0.80, 0.20], n),
        "created_at":        eff_date,
    })


def generate_policy_documents() -> pd.DataFrame:
    n = ROW_COUNTS["policy_documents"]
    n_policies = ROW_COUNTS["policies"]
    doc_types = ["POLICY_SCHEDULE", "CERTIFICATE", "ENDORSEMENT", "RENEWAL_NOTICE",
                 "CANCELLATION_NOTICE", "CLAIMS_FORM", "ID_PROOF", "OTHER"]

    return pd.DataFrame({
        "document_id":   sequential_ids(n),
        "policy_id":     foreign_keys(n, n_policies),
        "document_type": weighted_choice(doc_types, [0.25, 0.20, 0.15, 0.15, 0.10, 0.08, 0.05, 0.02], n),
        "document_name": [fake.file_name(extension="pdf") for _ in range(n)],
        "storage_ref":   [f"s3://ins-docs/{fake.uuid4()}.pdf" for _ in range(n)],
        "file_size_kb":  rng.integers(10, 5000, n),
        "uploaded_by":   [fake.name() for _ in range(n)],
        "upload_date":   random_dates(n),
        "is_current":    weighted_choice([True, False], [0.75, 0.25], n),
        "created_at":    random_dates(n),
    })


def generate_policy_payments() -> pd.DataFrame:
    n = ROW_COUNTS["policy_payments"]
    n_policies  = ROW_COUNTS["policies"]
    n_customers = ROW_COUNTS["customers"]
    statuses    = ["PAID", "PENDING", "FAILED", "REVERSED"]
    methods     = ["DIRECT_DEBIT", "CREDIT_CARD", "BANK_TRANSFER", "CHEQUE"]

    # Seasonal: more payments in Jan (annual renewals), dip in Aug
    pay_dates = seasonal_dates(n, peak_months=[1, 4, 7, 10])
    due_dates = pd.Series([
        pay_dates.iloc[i] - pd.Timedelta(days=int(rng.integers(-5, 15)))
        for i in range(n)
    ])
    base_amount = lognormal(n, mean=150, sigma=0.7)
    days_overdue = np.where(
        rng.random(n) < 0.12,
        rng.integers(1, 90, n),
        0
    ).astype(int)

    return pd.DataFrame({
        "payment_id":     sequential_ids(n),
        "policy_id":      foreign_keys(n, n_policies),
        "customer_id":    foreign_keys(n, n_customers),
        "payment_date":   pay_dates,
        "due_date":       due_dates,
        "amount":         np.round(base_amount, 2),
        "payment_status": weighted_choice(statuses, [0.82, 0.10, 0.05, 0.03], n),
        "payment_method": weighted_choice(methods, [0.40, 0.30, 0.20, 0.10], n),
        "transaction_ref": [f"TXN{fake.bothify('??########').upper()}" for _ in range(n)],
        "days_overdue":   days_overdue,
        "late_fee":       np.where(days_overdue > 0, np.round(rng.uniform(10, 50, n), 2), 0.0),
        "created_at":     pay_dates,
    })


def generate_policy_cancellations() -> pd.DataFrame:
    n = ROW_COUNTS["policy_cancellations"]
    n_policies  = ROW_COUNTS["policies"]
    n_customers = ROW_COUNTS["customers"]
    reasons  = ["NON_PAYMENT", "CUSTOMER_REQUEST", "FRAUD", "UNDERWRITING", "DUPLICATE", "MOVED_ABROAD"]
    initiators = ["CUSTOMER", "INSURER", "SYSTEM"]

    cancel_dates = random_dates(n)
    return pd.DataFrame({
        "cancellation_id":     sequential_ids(n),
        "policy_id":           foreign_keys(n, n_policies),
        "customer_id":         foreign_keys(n, n_customers),
        "cancellation_date":   cancel_dates,
        "cancellation_reason": weighted_choice(reasons, [0.35, 0.30, 0.10, 0.12, 0.08, 0.05], n),
        "initiated_by":        weighted_choice(initiators, [0.50, 0.35, 0.15], n),
        "refund_amount":       inject_nulls(pd.Series(lognormal(n, mean=300, sigma=0.8)), 0.25),
        "refund_status":       inject_nulls(pd.Series(weighted_choice(["PROCESSED","PENDING","NA"], [0.60,0.25,0.15], n)), 0.25),
        "created_at":          cancel_dates,
    })


def generate_policy_renewals() -> pd.DataFrame:
    n = ROW_COUNTS["policy_renewals"]
    n_policies  = ROW_COUNTS["policies"]
    n_customers = ROW_COUNTS["customers"]
    statuses = ["RENEWED", "LAPSED", "PENDING", "DECLINED"]

    renewal_dates = seasonal_dates(n, peak_months=[1, 3, 9, 12])
    old_prem = lognormal(n, mean=1_800, sigma=0.8)
    prem_change = rng.normal(3.5, 5.0, n)
    new_prem = np.round(old_prem * (1 + prem_change / 100), 2)

    return pd.DataFrame({
        "renewal_id":         sequential_ids(n),
        "policy_id":          foreign_keys(n, n_policies),
        "customer_id":        foreign_keys(n, n_customers),
        "renewal_date":       renewal_dates,
        "previous_premium":   np.round(old_prem, 2),
        "new_premium":        new_prem,
        "premium_change_pct": np.round(prem_change, 2),
        "auto_renewed":       weighted_choice([True, False], [RENEWAL_RATE, 1 - RENEWAL_RATE], n),
        "renewal_status":     weighted_choice(statuses, [0.72, 0.15, 0.08, 0.05], n),
        "offer_sent_date":    pd.Series([
            renewal_dates.iloc[i] - pd.Timedelta(days=int(rng.integers(14, 45)))
            for i in range(n)
        ]),
        "created_at":         renewal_dates,
    })


def generate_coverage_details() -> pd.DataFrame:
    n = ROW_COUNTS["coverage_details"]
    n_policies = ROW_COUNTS["policies"]

    df = pd.DataFrame({
        "coverage_id":           sequential_ids(n),
        "policy_id":             pd.Series(range(1, n + 1)),  # 1-to-1 with policies
        "property_limit":        inject_nulls(pd.Series(lognormal(n, 300_000, 0.8)), 0.50),
        "vehicle_limit":         inject_nulls(pd.Series(lognormal(n, 40_000, 0.7)), 0.45),
        "liability_limit":       inject_nulls(pd.Series(lognormal(n, 500_000, 0.6)), 0.40),
        "medical_limit":         inject_nulls(pd.Series(lognormal(n, 100_000, 0.8)), 0.55),
        "personal_prop_limit":   inject_nulls(pd.Series(lognormal(n, 50_000, 0.7)), 0.60),
        "property_deductible":   inject_nulls(pd.Series(lognormal(n, 1_000, 0.6)), 0.50),
        "vehicle_deductible":    inject_nulls(pd.Series(lognormal(n, 500, 0.5)), 0.45),
        "medical_deductible":    inject_nulls(pd.Series(lognormal(n, 500, 0.6)), 0.55),
        "fire_covered":          weighted_choice([True, False], [0.70, 0.30], n),
        "flood_covered":         weighted_choice([True, False], [0.30, 0.70], n),
        "earthquake_covered":    weighted_choice([True, False], [0.15, 0.85], n),
        "theft_covered":         weighted_choice([True, False], [0.65, 0.35], n),
        "vandalism_covered":     weighted_choice([True, False], [0.55, 0.45], n),
        "windstorm_covered":     weighted_choice([True, False], [0.50, 0.50], n),
        "hail_covered":          weighted_choice([True, False], [0.45, 0.55], n),
        "collision_covered":     weighted_choice([True, False], [0.60, 0.40], n),
        "comprehensive_covered": weighted_choice([True, False], [0.55, 0.45], n),
        "uninsured_motorist":    weighted_choice([True, False], [0.50, 0.50], n),
        "roadside_assist":       weighted_choice([True, False], [0.40, 0.60], n),
        "rental_coverage":       weighted_choice([True, False], [0.35, 0.65], n),
        "accidental_death":      weighted_choice([True, False], [0.25, 0.75], n),
        "disability_covered":    weighted_choice([True, False], [0.20, 0.80], n),
        "critical_illness":      weighted_choice([True, False], [0.18, 0.82], n),
        "created_at":            random_dates(n),
    })

    extra_df = pd.DataFrame(generate_wide_columns(n, WIDE_EXTRA_COLUMNS["coverage_details"], "cov"))
    df = pd.concat([df, extra_df], axis=1)

    return df


def generate_product_pricing_rules() -> pd.DataFrame:
    n = ROW_COUNTS["product_pricing_rules"]
    n_products = ROW_COUNTS["products"]
    rule_types   = ["LOADING", "DISCOUNT", "BASE"]
    factor_names = ["AGE_FACTOR", "LOCATION_FACTOR", "CLAIMS_HISTORY", "CREDIT_SCORE",
                    "OCCUPATION_FACTOR", "VEHICLE_AGE", "NO_CLAIMS_BONUS", "LOYALTY_DISCOUNT"]

    eff = random_dates(n, 2015, 2022)
    return pd.DataFrame({
        "rule_id":       sequential_ids(n),
        "product_id":    foreign_keys(n, n_products),
        "rule_name":     [fake.bs() for _ in range(n)],
        "rule_type":     weighted_choice(rule_types, [0.40, 0.35, 0.25], n),
        "factor_name":   weighted_choice(factor_names, [0.15]*8, n),
        "factor_value":  np.round(rng.uniform(0.5, 2.0, n), 4),
        "effective_date": eff,
        "expiry_date":   inject_nulls(pd.Series(future_dates(eff, 180, 1800)), 0.20),
        "is_active":     weighted_choice([True, False], [0.75, 0.25], n),
        "created_at":    eff,
    })


POLICY_GENERATORS = {
    "products":              generate_products,
    "policies":              generate_policies,
    "policy_versions":       generate_policy_versions,
    "policy_endorsements":   generate_policy_endorsements,
    "policy_documents":      generate_policy_documents,
    "policy_payments":       generate_policy_payments,
    "policy_cancellations":  generate_policy_cancellations,
    "policy_renewals":       generate_policy_renewals,
    "coverage_details":      generate_coverage_details,
    "product_pricing_rules": generate_product_pricing_rules,
}
