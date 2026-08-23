"""Generators for underwriting & risk domain."""

import numpy as np
import pandas as pd

from config import ROW_COUNTS, WIDE_EXTRA_COLUMNS, QUOTE_CONVERSION
from generators.base import (
    fake, foreign_keys, future_dates, generate_wide_columns,
    inject_nulls, lognormal, random_dates, rng, seasonal_dates,
    sequential_ids, weighted_choice,
)


def generate_underwriting_assessments() -> pd.DataFrame:
    """Synthetic underwriting-assessment records."""
    n = ROW_COUNTS["underwriting_assessments"]
    n_policies  = ROW_COUNTS["policies"]
    n_customers = ROW_COUNTS["customers"]

    risk_cats = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
    decisions = ["APPROVED", "DECLINED", "REFERRED", "MODIFIED"]

    # Risk score drives premium loading — correlated
    risk_score = np.round(rng.lognormal(mean=3.5, sigma=0.6, size=n), 2)
    risk_score = np.clip(risk_score, 10, 999)
    loading = np.where(risk_score > 200, rng.uniform(10, 50, n), rng.uniform(0, 15, n))
    discount = np.where(risk_score < 80, rng.uniform(5, 20, n), rng.uniform(0, 5, n))
    base_prem = lognormal(n, 1_800, 0.7)
    final_prem = np.round(base_prem * (1 + loading / 100) * (1 - discount / 100), 2)

    df = pd.DataFrame({
        "assessment_id":    sequential_ids(n),
        "policy_id":        foreign_keys(n, n_policies),
        "customer_id":      foreign_keys(n, n_customers),
        "assessed_date":    random_dates(n),
        "underwriter_id":   inject_nulls(foreign_keys(n, 500), 0.08),
        "overall_risk_score": risk_score,
        "risk_category":    pd.Series(np.where(
            risk_score < 80, "LOW",
            np.where(risk_score < 200, "MEDIUM",
            np.where(risk_score < 400, "HIGH", "VERY_HIGH"))
        )),
        "decision":         weighted_choice(decisions, [0.72, 0.08, 0.12, 0.08], n),
        "decision_notes":   inject_nulls(pd.Series([fake.sentence(nb_words=12) for _ in range(n)]), 0.40),
        "base_premium":     np.round(base_prem, 2),
        "loading_pct":      np.round(loading, 2),
        "discount_pct":     np.round(discount, 2),
        "final_premium":    final_prem,
        "created_at":       random_dates(n),
    })

    extra_df = pd.DataFrame(generate_wide_columns(n, WIDE_EXTRA_COLUMNS["underwriting_assessments"], "uw"))
    df = pd.concat([df, extra_df], axis=1)

    return df


def generate_risk_scores() -> pd.DataFrame:
    """Synthetic risk-score records."""
    n = ROW_COUNTS["risk_scores"]
    n_customers = ROW_COUNTS["customers"]
    score_types = ["CREDIT", "FRAUD", "CHURN", "CLAIMS", "OVERALL"]
    score_bands = ["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
    model_versions = ["v1.0", "v1.2", "v2.0", "v2.1", "v3.0"]

    # Scores follow different distributions by type
    score_type = weighted_choice(score_types, [0.25, 0.20, 0.20, 0.20, 0.15], n)
    score_values = np.where(
        score_type == "CREDIT",   np.clip(rng.normal(650, 100, n), 300, 850),
        np.where(score_type == "FRAUD",  np.round(rng.beta(1.5, 8, n) * 100, 2),
        np.where(score_type == "CHURN",  np.round(rng.beta(2, 5, n) * 100, 2),
                 np.round(rng.lognormal(3.5, 0.6, n), 2)))
    )

    return pd.DataFrame({
        "score_id":           sequential_ids(n),
        "customer_id":        foreign_keys(n, n_customers),
        "score_date":         random_dates(n),
        "score_type":         pd.Series(score_type),
        "score_value":        np.round(score_values, 2),
        "score_band":         weighted_choice(score_bands, [0.15, 0.30, 0.30, 0.18, 0.07], n),
        "model_version":      weighted_choice(model_versions, [0.05, 0.10, 0.20, 0.30, 0.35], n),
        "contributing_factors": inject_nulls(pd.Series([None] * n), 0.30),  # JSONB left null for simplicity
        "created_at":         random_dates(n),
    })


def generate_quote_attempts() -> pd.DataFrame:
    """Synthetic insurance-quote-attempt records."""
    n = ROW_COUNTS["quote_attempts"]
    n_customers = ROW_COUNTS["customers"]
    n_products  = ROW_COUNTS["products"]
    n_agents    = ROW_COUNTS["agents"]
    n_policies  = ROW_COUNTS["policies"]

    channels = ["ONLINE", "AGENT", "BROKER", "PHONE", "MOBILE_APP"]
    abandon_reasons = ["PRICE_TOO_HIGH", "FOUND_BETTER_DEAL", "NOT_READY", "TECHNICAL_ERROR",
                       "MISSING_DOCUMENTS", "CHANGED_MIND", None]

    converted = rng.random(n) < QUOTE_CONVERSION
    quote_dates = seasonal_dates(n, peak_months=[1, 3, 9, 10, 11])

    return pd.DataFrame({
        "quote_id":            sequential_ids(n),
        "quote_ref":           [f"QT{i:010d}" for i in range(1, n + 1)],
        "customer_id":         inject_nulls(foreign_keys(n, n_customers), 0.20),  # guest quotes
        "product_id":          foreign_keys(n, n_products),
        "agent_id":            inject_nulls(foreign_keys(n, n_agents), 0.55),
        "quote_date":          quote_dates,
        "channel":             weighted_choice(channels, [0.35, 0.25, 0.15, 0.15, 0.10], n),
        "quoted_premium":      lognormal(n, mean=1_600, sigma=0.85),
        "sum_insured":         lognormal(n, mean=200_000, sigma=1.1),
        "converted":           pd.Series(converted),
        "policy_id":           pd.Series([
            int(rng.integers(1, n_policies + 1)) if converted[i] else None
            for i in range(n)
        ]),
        "abandon_reason":      pd.Series([
            None if converted[i]
            else weighted_choice(abandon_reasons, [0.30, 0.20, 0.15, 0.10, 0.10, 0.10, 0.05], 1)[0]
            for i in range(n)
        ]),
        "session_duration_sec": np.where(
            converted,
            rng.integers(300, 1800, n),
            rng.integers(30, 600, n)
        ),
        "created_at": quote_dates,
    })


def generate_credit_checks() -> pd.DataFrame:
    """Synthetic credit-check records."""
    n = ROW_COUNTS["credit_checks"]
    n_customers = ROW_COUNTS["customers"]
    bureaus = ["EQUIFAX", "EXPERIAN", "TRANSUNION"]
    bands   = ["EXCELLENT", "GOOD", "FAIR", "POOR", "NO_HISTORY"]

    scores = np.clip(rng.normal(660, 110, n), 300, 850).astype(int)
    return pd.DataFrame({
        "check_id":       sequential_ids(n),
        "customer_id":    foreign_keys(n, n_customers),
        "check_date":     random_dates(n),
        "bureau":         weighted_choice(bureaus, [0.35, 0.35, 0.30], n),
        "credit_score":   scores,
        "credit_band":    pd.Series(np.where(
            scores >= 750, "EXCELLENT",
            np.where(scores >= 670, "GOOD",
            np.where(scores >= 580, "FAIR",
            np.where(scores >= 300, "POOR", "NO_HISTORY")))
        )),
        "derogatory_marks": rng.integers(0, 8, n),
        "bankruptcy":     weighted_choice([True, False], [0.03, 0.97], n),
        "response_code":  weighted_choice(["00", "01", "02", "99"], [0.90, 0.05, 0.03, 0.02], n),
        "created_at":     random_dates(n),
    })


def generate_inspection_reports() -> pd.DataFrame:
    """Synthetic property/risk inspection report records."""
    n = ROW_COUNTS["inspection_reports"]
    n_policies = ROW_COUNTS["policies"]
    conditions = ["EXCELLENT", "GOOD", "FAIR", "POOR", "CONDEMNED"]
    types = ["PROPERTY", "VEHICLE", "COMMERCIAL", "MARINE"]

    return pd.DataFrame({
        "inspection_id":    sequential_ids(n),
        "policy_id":        foreign_keys(n, n_policies),
        "inspection_date":  random_dates(n),
        "inspector_name":   [fake.name() for _ in range(n)],
        "inspection_type":  weighted_choice(types, [0.45, 0.35, 0.15, 0.05], n),
        "property_condition": weighted_choice(conditions, [0.20, 0.45, 0.25, 0.08, 0.02], n),
        "risk_notes":       inject_nulls(pd.Series([fake.paragraph(nb_sentences=2) for _ in range(n)]), 0.40),
        "passed":           weighted_choice([True, False], [0.80, 0.20], n),
        "created_at":       random_dates(n),
    })


def generate_exclusions() -> pd.DataFrame:
    """Synthetic policy exclusion-clause records."""
    n = ROW_COUNTS["exclusions"]
    n_policies = ROW_COUNTS["policies"]
    excl_types = ["PRE_EXISTING_CONDITION", "WEAR_AND_TEAR", "INTENTIONAL_DAMAGE",
                  "WAR_TERRORISM", "NUCLEAR", "FLOOD_ZONE", "HIGH_RISK_ACTIVITY"]

    return pd.DataFrame({
        "exclusion_id":   sequential_ids(n),
        "policy_id":      foreign_keys(n, n_policies),
        "exclusion_type": weighted_choice(excl_types, [0.25, 0.20, 0.15, 0.10, 0.05, 0.15, 0.10], n),
        "description":    inject_nulls(pd.Series([fake.sentence(nb_words=15) for _ in range(n)]), 0.30),
        "effective_date": random_dates(n),
        "is_active":      weighted_choice([True, False], [0.85, 0.15], n),
        "created_at":     random_dates(n),
    })


def generate_reinsurance_treaties() -> pd.DataFrame:
    """Synthetic reinsurance-treaty records."""
    n = ROW_COUNTS["reinsurance_treaties"]
    treaty_types = ["QUOTA_SHARE", "EXCESS_LOSS", "FACULTATIVE", "STOP_LOSS"]
    reinsurers   = ["Munich Re", "Swiss Re", "Hannover Re", "SCOR", "Gen Re",
                    "Lloyd's of London", "Berkshire Hathaway Re"]

    eff = random_dates(n, 2015, 2022)
    return pd.DataFrame({
        "treaty_id":       sequential_ids(n),
        "treaty_name":     [f"Treaty-{fake.bothify('???-####').upper()}" for _ in range(n)],
        "reinsurer_name":  weighted_choice(reinsurers, [0.20,0.18,0.15,0.12,0.12,0.13,0.10], n),
        "treaty_type":     weighted_choice(treaty_types, [0.35, 0.30, 0.20, 0.15], n),
        "share_percentage": np.round(rng.uniform(10, 60, n), 2),
        "retention_limit": lognormal(n, mean=1_000_000, sigma=0.8),
        "effective_date":  eff,
        "expiry_date":     future_dates(eff, 365, 1825),
        "is_active":       weighted_choice([True, False], [0.70, 0.30], n),
        "created_at":      eff,
    })


def generate_reinsurance_claims() -> pd.DataFrame:
    """Synthetic reinsurance-claim-share records."""
    n = ROW_COUNTS["reinsurance_claims"]
    n_claims  = ROW_COUNTS["claims"]
    n_treaties = ROW_COUNTS["reinsurance_treaties"]
    statuses   = ["NOTIFIED", "UNDER_REVIEW", "APPROVED", "PAID", "DECLINED"]

    cession = lognormal(n, mean=50_000, sigma=1.2)
    return pd.DataFrame({
        "rei_claim_id":    sequential_ids(n),
        "claim_id":        foreign_keys(n, n_claims),
        "treaty_id":       foreign_keys(n, n_treaties),
        "cession_amount":  np.round(cession, 2),
        "recovery_amount": inject_nulls(pd.Series(np.round(cession * rng.uniform(0.7, 1.0, n), 2)), 0.30),
        "recovery_date":   inject_nulls(pd.Series(random_dates(n)), 0.30),
        "status":          weighted_choice(statuses, [0.10, 0.15, 0.30, 0.35, 0.10], n),
        "created_at":      random_dates(n),
    })


UNDERWRITING_GENERATORS = {
    "underwriting_assessments": generate_underwriting_assessments,
    "risk_scores":              generate_risk_scores,
    "quote_attempts":           generate_quote_attempts,
    "credit_checks":            generate_credit_checks,
    "inspection_reports":       generate_inspection_reports,
    "exclusions":               generate_exclusions,
    "reinsurance_treaties":     generate_reinsurance_treaties,
    "reinsurance_claims":       generate_reinsurance_claims,
}
