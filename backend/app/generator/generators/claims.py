"""Generators for claims domain."""

import numpy as np
import pandas as pd

from config import ROW_COUNTS, WIDE_EXTRA_COLUMNS, FRAUD_RATE
from generators.base import (
    city_series, fake, foreign_keys, future_dates, generate_wide_columns,
    inject_nulls, lognormal, random_dates, rng, sequential_ids,
    state_series, weighted_choice,
)


def generate_claims() -> pd.DataFrame:
    """Synthetic claims records, one row per claim."""
    n = ROW_COUNTS["claims"]
    n_policies  = ROW_COUNTS["policies"]
    n_customers = ROW_COUNTS["customers"]

    incident_types = ["COLLISION", "THEFT", "FIRE", "FLOOD", "MEDICAL", "LIABILITY",
                      "WINDSTORM", "VANDALISM", "EARTHQUAKE", "SLIP_FALL"]
    statuses       = ["OPEN", "UNDER_REVIEW", "APPROVED", "REJECTED", "CLOSED", "LITIGATED"]
    priorities     = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    # More claims in winter (Dec-Feb) and summer (Jun-Jul)
    incident_dates = random_dates(n)
    reported_dates = pd.Series([
        incident_dates.iloc[i] + pd.Timedelta(days=int(rng.integers(0, 30)))
        for i in range(n)
    ])

    claimed = lognormal(n, mean=12_000, sigma=1.3)
    approved_rate = rng.uniform(0.40, 1.0, n)
    approved = np.round(claimed * approved_rate, 2)
    paid = np.round(approved * rng.uniform(0.80, 1.0, n), 2)

    fraud_flags = rng.random(n) < FRAUD_RATE
    litigated   = rng.random(n) < 0.08

    df = pd.DataFrame({
        "claim_id":           sequential_ids(n),
        "claim_number":       [f"CLM{i:010d}" for i in range(1, n + 1)],
        "policy_id":          foreign_keys(n, n_policies),
        "customer_id":        foreign_keys(n, n_customers),
        "incident_date":      incident_dates,
        "reported_date":      reported_dates,
        "incident_type":      weighted_choice(incident_types, [0.25,0.15,0.10,0.08,0.12,0.10,0.07,0.06,0.04,0.03], n),
        "incident_description": inject_nulls(pd.Series([fake.sentence(nb_words=12) for _ in range(n)]), 0.10),
        "incident_city":      city_series(n),
        "incident_state":     state_series(n),
        "claim_status":       weighted_choice(statuses, [0.15, 0.20, 0.30, 0.15, 0.18, 0.02], n),
        "priority":           weighted_choice(priorities, [0.35, 0.40, 0.20, 0.05], n),
        "claimed_amount":     np.round(claimed, 2),
        "approved_amount":    np.where(rng.random(n) < 0.15, None, approved),
        "paid_amount":        np.where(rng.random(n) < 0.20, None, paid),
        "reserve_amount":     np.round(claimed * rng.uniform(1.0, 1.3, n), 2),
        "salvage_amount":     inject_nulls(pd.Series(np.round(lognormal(n, 1_000, 0.8), 2)), 0.75),
        "subrogation_amount": inject_nulls(pd.Series(np.round(lognormal(n, 2_000, 0.9), 2)), 0.85),
        "adjuster_id":        inject_nulls(foreign_keys(n, 500), 0.05),
        "adjuster_name":      inject_nulls(pd.Series([fake.name() for _ in range(n)]), 0.05),
        "is_fraud_suspected": pd.Series(fraud_flags),
        "is_litigated":       pd.Series(litigated),
        "is_reinsured":       weighted_choice([True, False], [0.12, 0.88], n),
        "closed_date":        inject_nulls(pd.Series(random_dates(n)), 0.35),
        "created_at":         reported_dates,
        "updated_at":         reported_dates,
    })

    extra_df = pd.DataFrame(generate_wide_columns(n, WIDE_EXTRA_COLUMNS["claims"], "clm"))
    df = pd.concat([df, extra_df], axis=1)

    return df


def generate_claim_events() -> pd.DataFrame:
    """Synthetic claim event/audit-trail records."""
    n = ROW_COUNTS["claim_events"]
    n_claims = ROW_COUNTS["claims"]

    event_types = ["CLAIM_OPENED", "DOCUMENT_UPLOADED", "ADJUSTER_ASSIGNED", "SITE_INSPECTION",
                   "ESTIMATE_RECEIVED", "COVERAGE_DECISION", "PAYMENT_AUTHORIZED", "PAYMENT_MADE",
                   "CLAIM_CLOSED", "APPEAL_RECEIVED", "FRAUD_FLAGGED", "STATUS_UPDATED"]
    statuses    = ["OPEN", "UNDER_REVIEW", "APPROVED", "REJECTED", "CLOSED", "LITIGATED"]
    roles       = ["ADJUSTER", "SUPERVISOR", "SYSTEM", "CUSTOMER_SERVICE", "UNDERWRITER"]

    event_dates = random_dates(n)
    old_status  = weighted_choice(statuses, [0.20, 0.25, 0.25, 0.15, 0.14, 0.01], n)
    new_status  = weighted_choice(statuses, [0.15, 0.20, 0.30, 0.15, 0.18, 0.02], n)

    return pd.DataFrame({
        "event_id":          sequential_ids(n),
        "claim_id":          foreign_keys(n, n_claims),
        "event_type":        weighted_choice(event_types, [0.08,0.12,0.08,0.06,0.08,0.10,0.08,0.10,0.10,0.05,0.05,0.10], n),
        "event_description": inject_nulls(pd.Series([fake.sentence(nb_words=10) for _ in range(n)]), 0.20),
        "performed_by":      [fake.name() for _ in range(n)],
        "performed_by_role": weighted_choice(roles, [0.40, 0.15, 0.25, 0.12, 0.08], n),
        "event_date":        event_dates,
        "old_status":        pd.Series(old_status),
        "new_status":        pd.Series(new_status),
        "notes":             inject_nulls(pd.Series([fake.paragraph(nb_sentences=2) for _ in range(n)]), 0.50),
        "created_at":        event_dates,
    })


def generate_claim_payments() -> pd.DataFrame:
    """Synthetic claim payment records."""
    n = ROW_COUNTS["claim_payments"]
    n_claims    = ROW_COUNTS["claims"]
    n_policies  = ROW_COUNTS["policies"]
    n_customers = ROW_COUNTS["customers"]

    pay_types  = ["SETTLEMENT", "INTERIM", "MEDICAL", "LEGAL", "REPAIR", "EMERGENCY"]
    methods    = ["BANK_TRANSFER", "CHEQUE", "DIRECT_DEPOSIT", "VOUCHER"]
    payee_types = ["CUSTOMER", "REPAIR_SHOP", "MEDICAL_PROVIDER", "LEGAL_FIRM"]

    pay_dates = random_dates(n)
    return pd.DataFrame({
        "payment_id":     sequential_ids(n),
        "claim_id":       foreign_keys(n, n_claims),
        "policy_id":      foreign_keys(n, n_policies),
        "customer_id":    foreign_keys(n, n_customers),
        "payment_type":   weighted_choice(pay_types, [0.35, 0.20, 0.15, 0.10, 0.15, 0.05], n),
        "payment_date":   pay_dates,
        "amount":         lognormal(n, mean=5_000, sigma=1.2),
        "payment_method": weighted_choice(methods, [0.50, 0.20, 0.25, 0.05], n),
        "payee_name":     [fake.name() for _ in range(n)],
        "payee_type":     weighted_choice(payee_types, [0.50, 0.20, 0.18, 0.12], n),
        "bank_ref":       [f"BREF{fake.bothify('??########').upper()}" for _ in range(n)],
        "payment_status": weighted_choice(["PAID", "PENDING", "FAILED", "REVERSED"], [0.80, 0.12, 0.05, 0.03], n),
        "created_at":     pay_dates,
    })


def generate_claim_documents() -> pd.DataFrame:
    """Synthetic claim document/attachment metadata records."""
    n = ROW_COUNTS["claim_documents"]
    n_claims = ROW_COUNTS["claims"]
    doc_types = ["POLICE_REPORT", "MEDICAL_REPORT", "PHOTO_EVIDENCE", "REPAIR_ESTIMATE",
                 "WITNESS_STATEMENT", "ADJUSTER_REPORT", "INVOICE", "ID_PROOF"]

    upload_dates = random_dates(n)
    return pd.DataFrame({
        "document_id":   sequential_ids(n),
        "claim_id":      foreign_keys(n, n_claims),
        "document_type": weighted_choice(doc_types, [0.18,0.15,0.20,0.15,0.10,0.10,0.08,0.04], n),
        "document_name": [fake.file_name(extension="pdf") for _ in range(n)],
        "storage_ref":   [f"s3://ins-claims/{fake.uuid4()}" for _ in range(n)],
        "uploaded_by":   [fake.name() for _ in range(n)],
        "upload_date":   upload_dates,
        "is_verified":   weighted_choice([True, False], [0.65, 0.35], n),
        "created_at":    upload_dates,
    })


def generate_claim_assessments() -> pd.DataFrame:
    """Synthetic claim coverage-assessment records."""
    n = ROW_COUNTS["claim_assessments"]
    n_claims = ROW_COUNTS["claims"]
    decisions = ["COVERED", "PARTIAL", "EXCLUDED", "PENDING"]

    assess_dates = random_dates(n)
    recommended = lognormal(n, mean=10_000, sigma=1.2)
    final = np.round(recommended * rng.uniform(0.70, 1.10, n), 2)

    return pd.DataFrame({
        "assessment_id":    sequential_ids(n),
        "claim_id":         foreign_keys(n, n_claims),
        "adjuster_id":      inject_nulls(foreign_keys(n, 500), 0.05),
        "assessment_date":  assess_dates,
        "coverage_decision": weighted_choice(decisions, [0.55, 0.25, 0.12, 0.08], n),
        "coverage_notes":   inject_nulls(pd.Series([fake.paragraph(nb_sentences=2) for _ in range(n)]), 0.35),
        "recommended_amount": np.round(recommended, 2),
        "final_amount":     inject_nulls(pd.Series(final), 0.20),
        "created_at":       assess_dates,
    })


def generate_claim_fraud_flags() -> pd.DataFrame:
    """Synthetic claim fraud-flag/investigation records."""
    n = ROW_COUNTS["claim_fraud_flags"]
    n_claims = ROW_COUNTS["claims"]
    flag_types = ["DUPLICATE_CLAIM", "STAGED_ACCIDENT", "INFLATED_AMOUNT",
                  "PROVIDER_FRAUD", "IDENTITY_FRAUD", "SUSPICIOUS_TIMING"]
    flagged_by = ["SYSTEM", "ADJUSTER", "EXTERNAL_AGENCY", "HOTLINE"]
    invest_status = ["OPEN", "IN_PROGRESS", "CLOSED", "REFERRED"]
    outcomes   = ["CONFIRMED_FRAUD", "FALSE_POSITIVE", "INCONCLUSIVE", "PENDING"]

    return pd.DataFrame({
        "flag_id":              sequential_ids(n),
        "claim_id":             foreign_keys(n, n_claims),
        "flag_type":            weighted_choice(flag_types, [0.20,0.18,0.25,0.15,0.12,0.10], n),
        "fraud_score":          np.round(rng.beta(2, 3, n), 4),
        "flag_reason":          [fake.sentence(nb_words=10) for _ in range(n)],
        "flagged_by":           weighted_choice(flagged_by, [0.55, 0.25, 0.12, 0.08], n),
        "investigation_status": weighted_choice(invest_status, [0.30,0.35,0.25,0.10], n),
        "outcome":              inject_nulls(pd.Series(weighted_choice(outcomes, [0.20,0.40,0.25,0.15], n)), 0.30),
        "created_at":           random_dates(n),
    })


def generate_claim_litigations() -> pd.DataFrame:
    """Synthetic claim litigation/legal-case records."""
    n = ROW_COUNTS["claim_litigations"]
    n_claims = ROW_COUNTS["claims"]
    statuses = ["FILED", "IN_DISCOVERY", "TRIAL", "SETTLED", "DISMISSED", "JUDGMENT"]

    filed_dates = random_dates(n)
    return pd.DataFrame({
        "litigation_id":    sequential_ids(n),
        "claim_id":         foreign_keys(n, n_claims),
        "filed_date":       filed_dates,
        "court":            [f"{fake.city()} District Court" for _ in range(n)],
        "plaintiff":        [fake.name() for _ in range(n)],
        "defendant":        [fake.company() for _ in range(n)],
        "case_number":      [f"{fake.numerify('####')}-CV-{fake.numerify('######')}" for _ in range(n)],
        "legal_counsel":    [fake.name() for _ in range(n)],
        "status":           weighted_choice(statuses, [0.10,0.20,0.10,0.40,0.12,0.08], n),
        "settlement_amount": inject_nulls(pd.Series(lognormal(n, 25_000, 1.3)), 0.45),
        "closed_date":      inject_nulls(pd.Series(future_dates(filed_dates, 90, 1800)), 0.40),
        "created_at":       filed_dates,
    })


def generate_repair_shops() -> pd.DataFrame:
    """Synthetic repair-shop directory records."""
    n = ROW_COUNTS["repair_shops"]
    shop_types = ["AUTO", "PROPERTY", "MEDICAL", "GENERAL"]

    return pd.DataFrame({
        "shop_id":      sequential_ids(n),
        "shop_name":    [fake.company() for _ in range(n)],
        "shop_type":    weighted_choice(shop_types, [0.45, 0.30, 0.15, 0.10], n),
        "address_line1": [fake.street_address() for _ in range(n)],
        "city":         city_series(n),
        "state":        state_series(n),
        "zip_code":     [fake.zipcode() for _ in range(n)],
        "phone":        [fake.phone_number() for _ in range(n)],
        "is_preferred": weighted_choice([True, False], [0.35, 0.65], n),
        "is_active":    weighted_choice([True, False], [0.90, 0.10], n),
        "created_at":   random_dates(n),
    })


def generate_claim_repairs() -> pd.DataFrame:
    """Synthetic claim repair-job records."""
    n = ROW_COUNTS["claim_repairs"]
    n_claims = ROW_COUNTS["claims"]
    n_shops  = ROW_COUNTS["repair_shops"]
    repair_types = ["BODYWORK", "ENGINE", "ELECTRICAL", "STRUCTURAL", "WATER_DAMAGE",
                    "FIRE_DAMAGE", "ROOF", "PLUMBING", "MEDICAL_TREATMENT"]
    statuses = ["AUTHORIZED", "IN_PROGRESS", "COMPLETED", "DISPUTED"]

    start_dates = random_dates(n)
    return pd.DataFrame({
        "repair_id":          sequential_ids(n),
        "claim_id":           foreign_keys(n, n_claims),
        "shop_id":            inject_nulls(foreign_keys(n, n_shops), 0.10),
        "repair_type":        weighted_choice(repair_types, [0.18,0.12,0.10,0.10,0.10,0.08,0.10,0.08,0.14], n),
        "authorized_amount":  lognormal(n, mean=3_000, sigma=0.9),
        "actual_amount":      inject_nulls(pd.Series(lognormal(n, mean=3_200, sigma=0.9)), 0.25),
        "start_date":         start_dates,
        "completion_date":    inject_nulls(pd.Series(future_dates(start_dates, 1, 90)), 0.30),
        "repair_status":      weighted_choice(statuses, [0.15, 0.20, 0.55, 0.10], n),
        "customer_satisfaction": inject_nulls(pd.Series(rng.integers(1, 6, n)), 0.35),
        "created_at":         start_dates,
    })


def generate_medical_reports() -> pd.DataFrame:
    """Synthetic medical-report records tied to claims."""
    n = ROW_COUNTS["medical_reports"]
    n_claims    = ROW_COUNTS["claims"]
    n_customers = ROW_COUNTS["customers"]
    provider_types = ["HOSPITAL", "GP", "SPECIALIST", "PHYSIOTHERAPY", "MENTAL_HEALTH", "DENTAL"]
    diagnoses = [
        ("Z87.39", "Personal history of injury"), ("S06.0X", "Concussion"),
        ("M54.5", "Low back pain"), ("S82.0", "Fracture of patella"),
        ("F32.1", "Major depressive disorder"), ("M75.1", "Rotator cuff tear"),
        ("S52.5", "Fracture of lower end of radius"), ("T14.0", "Wound of unspecified region"),
    ]

    treatment_start = random_dates(n)
    total_cost = lognormal(n, mean=4_000, sigma=1.1)
    diag_choices = rng.integers(0, len(diagnoses), n)

    return pd.DataFrame({
        "report_id":       sequential_ids(n),
        "claim_id":        foreign_keys(n, n_claims),
        "customer_id":     foreign_keys(n, n_customers),
        "provider_name":   [fake.company() for _ in range(n)],
        "provider_type":   weighted_choice(provider_types, [0.30, 0.20, 0.20, 0.15, 0.10, 0.05], n),
        "diagnosis_code":  pd.Series([diagnoses[i][0] for i in diag_choices]),
        "diagnosis_desc":  pd.Series([diagnoses[i][1] for i in diag_choices]),
        "treatment_start": treatment_start,
        "treatment_end":   inject_nulls(pd.Series(future_dates(treatment_start, 7, 365)), 0.25),
        "total_cost":      np.round(total_cost, 2),
        "approved_cost":   np.round(total_cost * rng.uniform(0.60, 1.0, n), 2),
        "created_at":      treatment_start,
    })


CLAIM_GENERATORS = {
    "claims":             generate_claims,
    "claim_events":       generate_claim_events,
    "claim_payments":     generate_claim_payments,
    "claim_documents":    generate_claim_documents,
    "claim_assessments":  generate_claim_assessments,
    "claim_fraud_flags":  generate_claim_fraud_flags,
    "claim_litigations":  generate_claim_litigations,
    "repair_shops":       generate_repair_shops,
    "claim_repairs":      generate_claim_repairs,
    "medical_reports":    generate_medical_reports,
}
