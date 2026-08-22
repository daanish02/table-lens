"""Generators for finance & accounting and operations & compliance domains."""

import numpy as np
import pandas as pd

from config import ROW_COUNTS, WIDE_EXTRA_COLUMNS, DATA_START_YEAR, DATA_END_YEAR
from generators.base import (
    city_series, fake, foreign_keys, future_dates, generate_wide_columns,
    inject_nulls, lognormal, random_dates, rng, seasonal_dates,
    sequential_ids, state_series, weighted_choice,
)


# ── FINANCE ────────────────────────────────────────────────────────────────

def generate_financial_periods() -> pd.DataFrame:
    """One row per month from DATA_START_YEAR to DATA_END_YEAR."""
    import calendar
    from datetime import date

    rows = []
    pid = 1
    for year in range(DATA_START_YEAR, DATA_END_YEAR + 1):
        for month in range(1, 13):
            last_day = calendar.monthrange(year, month)[1]
            rows.append({
                "period_id":    pid,
                "period_year":  year,
                "period_month": month,
                "period_label": f"{year}-{month:02d}",
                "start_date":   date(year, month, 1),
                "end_date":     date(year, month, last_day),
                "is_closed":    year < DATA_END_YEAR,
                "closed_at":    None if year >= DATA_END_YEAR else f"{year}-{month:02d}-{last_day} 23:59:59",
                "created_at":   date(year, month, 1),
            })
            pid += 1
    return pd.DataFrame(rows[:ROW_COUNTS["financial_periods"]])


def generate_general_ledger() -> pd.DataFrame:
    n = ROW_COUNTS["general_ledger"]
    n_periods = ROW_COUNTS["financial_periods"]

    entity_types  = ["POLICY", "CLAIM", "COMMISSION", "TAX", "REINSURANCE", "EXPENSE"]
    account_codes = {
        "POLICY":       ("4001", "Premium Income"),
        "CLAIM":        ("5001", "Claims Expense"),
        "COMMISSION":   ("5101", "Commission Expense"),
        "TAX":          ("2301", "Tax Payable"),
        "REINSURANCE":  ("4101", "Reinsurance Premium"),
        "EXPENSE":      ("6001", "Operating Expense"),
    }

    entity_type = weighted_choice(entity_types, [0.30, 0.25, 0.15, 0.10, 0.10, 0.10], n)
    amounts = lognormal(n, mean=2_000, sigma=1.2)

    # Debit vs credit depends on entity type
    is_debit = pd.Series([
        et in ("CLAIM", "COMMISSION", "EXPENSE", "REINSURANCE")
        for et in entity_type
    ])

    posting_dates = seasonal_dates(n, peak_months=[3, 6, 9, 12])

    return pd.DataFrame({
        "ledger_id":     sequential_ids(n),
        "posting_date":  posting_dates,
        "account_code":  pd.Series([account_codes[et][0] for et in entity_type]),
        "account_name":  pd.Series([account_codes[et][1] for et in entity_type]),
        "entity_type":   pd.Series(entity_type),
        "entity_id":     foreign_keys(n, 50_000),
        "debit_amount":  np.where(is_debit, np.round(amounts, 2), 0.0),
        "credit_amount": np.where(~is_debit, np.round(amounts, 2), 0.0),
        "currency":      "USD",
        "description":   [fake.sentence(nb_words=6) for _ in range(n)],
        "batch_ref":     [f"BATCH{fake.numerify('########')}" for _ in range(n)],
        "period_id":     foreign_keys(n, n_periods),
        "created_at":    posting_dates,
    })


def generate_invoices() -> pd.DataFrame:
    n = ROW_COUNTS["invoices"]
    n_policies  = ROW_COUNTS["policies"]
    n_customers = ROW_COUNTS["customers"]
    statuses    = ["PAID", "UNPAID", "OVERDUE", "CANCELLED", "PARTIAL"]

    invoice_date = seasonal_dates(n, peak_months=[1, 4, 7, 10])
    due_date = pd.Series([
        invoice_date.iloc[i] + pd.Timedelta(days=int(rng.integers(14, 30)))
        for i in range(n)
    ])
    amount    = lognormal(n, mean=1_800, sigma=0.8)
    tax       = np.round(amount * rng.uniform(0.02, 0.08, n), 2)
    total     = np.round(amount + tax, 2)

    return pd.DataFrame({
        "invoice_id":     sequential_ids(n),
        "invoice_number": [f"INV{i:010d}" for i in range(1, n + 1)],
        "policy_id":      foreign_keys(n, n_policies),
        "customer_id":    foreign_keys(n, n_customers),
        "invoice_date":   invoice_date,
        "due_date":       due_date,
        "amount":         np.round(amount, 2),
        "tax_amount":     tax,
        "total_amount":   total,
        "status":         weighted_choice(statuses, [0.75, 0.10, 0.08, 0.04, 0.03], n),
        "created_at":     invoice_date,
    })


def generate_refunds() -> pd.DataFrame:
    n = ROW_COUNTS["refunds"]
    n_policies  = ROW_COUNTS["policies"]
    n_claims    = ROW_COUNTS["claims"]
    n_customers = ROW_COUNTS["customers"]
    reasons  = ["CANCELLATION", "OVERPAYMENT", "CLAIM_REJECTION", "POLICY_CHANGE", "ERROR"]
    methods  = ["BANK_TRANSFER", "CHEQUE", "CREDIT_CARD", "ORIGINAL_METHOD"]
    statuses = ["PROCESSED", "PENDING", "FAILED"]

    refund_dates = random_dates(n)
    return pd.DataFrame({
        "refund_id":     sequential_ids(n),
        "policy_id":     inject_nulls(foreign_keys(n, n_policies), 0.20),
        "claim_id":      inject_nulls(foreign_keys(n, n_claims), 0.50),
        "customer_id":   foreign_keys(n, n_customers),
        "refund_date":   refund_dates,
        "refund_amount": lognormal(n, mean=350, sigma=0.9),
        "refund_reason": weighted_choice(reasons, [0.40, 0.25, 0.15, 0.12, 0.08], n),
        "refund_method": weighted_choice(methods, [0.45, 0.25, 0.20, 0.10], n),
        "status":        weighted_choice(statuses, [0.80, 0.15, 0.05], n),
        "created_at":    refund_dates,
    })


def generate_commissions() -> pd.DataFrame:
    n = ROW_COUNTS["commissions"]
    n_agents   = ROW_COUNTS["agents"]
    n_policies = ROW_COUNTS["policies"]
    comm_types = ["NEW_BUSINESS", "RENEWAL", "BONUS", "OVERRIDE"]
    statuses   = ["PAID", "PENDING", "WITHHELD"]

    years  = rng.integers(DATA_START_YEAR, DATA_END_YEAR + 1, n)
    months = rng.integers(1, 13, n)
    base   = lognormal(n, mean=180, sigma=0.85)
    rate   = np.round(rng.uniform(2, 15, n), 2)
    amount = np.round(base * rate / 100, 2)

    paid_mask  = rng.random(n) < 0.85
    paid_dates = pd.Series([
        f"{years[i]}-{months[i]:02d}-28" if paid_mask[i] else None
        for i in range(n)
    ])

    return pd.DataFrame({
        "commission_id":    sequential_ids(n),
        "agent_id":         foreign_keys(n, n_agents),
        "policy_id":        foreign_keys(n, n_policies),
        "commission_type":  weighted_choice(comm_types, [0.40, 0.35, 0.15, 0.10], n),
        "base_amount":      np.round(base, 2),
        "rate_pct":         rate,
        "commission_amount": amount,
        "period_year":      years,
        "period_month":     months,
        "payment_status":   weighted_choice(statuses, [0.85, 0.12, 0.03], n),
        "paid_date":        paid_dates,
        "created_at":       random_dates(n),
    })


def generate_tax_records() -> pd.DataFrame:
    n = ROW_COUNTS["tax_records"]
    n_policies  = ROW_COUNTS["policies"]
    n_customers = ROW_COUNTS["customers"]
    tax_types = ["PREMIUM_TAX", "STAMP_DUTY", "IPT", "GST", "SURCHARGE"]
    statuses  = ["FILED", "PENDING", "AMENDED", "UNDER_REVIEW"]

    taxable = lognormal(n, mean=1_800, sigma=0.8)
    rates   = np.round(rng.uniform(0.02, 0.12, n), 4)

    return pd.DataFrame({
        "tax_id":         sequential_ids(n),
        "policy_id":      foreign_keys(n, n_policies),
        "customer_id":    foreign_keys(n, n_customers),
        "tax_year":       rng.integers(DATA_START_YEAR, DATA_END_YEAR + 1, n),
        "tax_type":       weighted_choice(tax_types, [0.35, 0.20, 0.15, 0.20, 0.10], n),
        "taxable_amount": np.round(taxable, 2),
        "tax_rate":       rates,
        "tax_amount":     np.round(taxable * rates, 2),
        "filing_status":  weighted_choice(statuses, [0.75, 0.15, 0.06, 0.04], n),
        "created_at":     random_dates(n),
    })


def generate_reserve_estimates() -> pd.DataFrame:
    n = ROW_COUNTS["reserve_estimates"]
    n_claims = ROW_COUNTS["claims"]
    reserve_types = ["CASE", "IBNR", "BULK", "CATASTROPHE"]
    methods       = ["CHAIN_LADDER", "BORNHUETTER_FERGUSON", "CAPE_COD", "EXPECTED_LOSS"]

    gross  = lognormal(n, mean=15_000, sigma=1.3)
    ceded  = np.round(gross * rng.uniform(0, 0.50, n), 2)
    net    = np.round(gross - ceded, 2)

    return pd.DataFrame({
        "reserve_id":    sequential_ids(n),
        "claim_id":      foreign_keys(n, n_claims),
        "estimate_date": random_dates(n),
        "estimator_id":  inject_nulls(foreign_keys(n, 100), 0.20),
        "reserve_type":  weighted_choice(reserve_types, [0.50, 0.25, 0.15, 0.10], n),
        "gross_reserve": np.round(gross, 2),
        "net_reserve":   net,
        "ceded_reserve": ceded,
        "method_used":   weighted_choice(methods, [0.40, 0.30, 0.20, 0.10], n),
        "created_at":    random_dates(n),
    })


# ── OPERATIONS ─────────────────────────────────────────────────────────────

def generate_audit_logs() -> pd.DataFrame:
    n = ROW_COUNTS["audit_logs"]
    actions      = ["CREATE", "UPDATE", "DELETE", "VIEW", "EXPORT", "LOGIN", "LOGOUT",
                    "APPROVE", "REJECT", "SUBMIT", "PRINT"]
    entity_types = ["POLICY", "CLAIM", "CUSTOMER", "PAYMENT", "DOCUMENT", "USER"]
    roles        = ["ADJUSTER", "UNDERWRITER", "CUSTOMER_SERVICE", "MANAGER",
                    "ADMIN", "SYSTEM", "AUDITOR"]

    event_times = seasonal_dates(n)

    return pd.DataFrame({
        "log_id":      sequential_ids(n),
        "event_time":  event_times,
        "user_id":     [f"USR{rng.integers(1, 1000):06d}" for _ in range(n)],
        "user_role":   weighted_choice(roles, [0.25, 0.15, 0.20, 0.10, 0.05, 0.20, 0.05], n),
        "action":      weighted_choice(actions, [0.20,0.30,0.05,0.20,0.05,0.05,0.05,0.04,0.02,0.02,0.02], n),
        "entity_type": weighted_choice(entity_types, [0.30, 0.25, 0.20, 0.10, 0.10, 0.05], n),
        "entity_id":   foreign_keys(n, 100_000),
        "old_values":  inject_nulls(pd.Series([None] * n), 0.50),  # JSONB
        "new_values":  inject_nulls(pd.Series([None] * n), 0.30),  # JSONB
        "ip_address":  [fake.ipv4() for _ in range(n)],
        "session_id":  [fake.uuid4() for _ in range(n)],
        "created_at":  event_times,
    })


def generate_complaints() -> pd.DataFrame:
    n = ROW_COUNTS["complaints"]
    n_customers = ROW_COUNTS["customers"]
    n_policies  = ROW_COUNTS["policies"]
    n_claims    = ROW_COUNTS["claims"]
    comp_types  = ["CLAIM_HANDLING", "PREMIUM_DISPUTE", "SERVICE_QUALITY",
                   "POLICY_TERMS", "BILLING", "AGENT_CONDUCT", "OTHER"]
    channels    = ["PHONE", "EMAIL", "LETTER", "ONLINE", "REGULATOR"]
    statuses    = ["OPEN", "IN_PROGRESS", "RESOLVED", "ESCALATED", "CLOSED"]

    received = random_dates(n)
    return pd.DataFrame({
        "complaint_id":    sequential_ids(n),
        "customer_id":     foreign_keys(n, n_customers),
        "policy_id":       inject_nulls(foreign_keys(n, n_policies), 0.20),
        "claim_id":        inject_nulls(foreign_keys(n, n_claims), 0.50),
        "received_date":   received,
        "complaint_type":  weighted_choice(comp_types, [0.30,0.15,0.20,0.10,0.10,0.10,0.05], n),
        "channel":         weighted_choice(channels, [0.35,0.30,0.10,0.20,0.05], n),
        "description":     [fake.paragraph(nb_sentences=3) for _ in range(n)],
        "status":          weighted_choice(statuses, [0.10, 0.20, 0.50, 0.05, 0.15], n),
        "resolution":      inject_nulls(pd.Series([fake.sentence(nb_words=15) for _ in range(n)]), 0.35),
        "resolved_date":   inject_nulls(pd.Series(future_dates(received, 1, 90)), 0.35),
        "satisfaction_score": inject_nulls(pd.Series(rng.integers(1, 6, n)), 0.40),
        "created_at":      received,
    })


def generate_regulatory_filings() -> pd.DataFrame:
    n = ROW_COUNTS["regulatory_filings"]
    filing_types  = ["ANNUAL_RETURN", "QUARTERLY_REPORT", "SOLVENCY_II", "AML_REPORT",
                     "COMPLAINTS_REPORT", "MARKET_CONDUCT", "PREMIUM_TAX_RETURN"]
    jurisdictions = ["FEDERAL", "CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "WA"]
    statuses      = ["SUBMITTED", "PENDING", "ACCEPTED", "QUERIED", "AMENDED"]

    filing_dates = random_dates(n)
    return pd.DataFrame({
        "filing_id":    sequential_ids(n),
        "filing_type":  weighted_choice(filing_types, [0.20,0.20,0.15,0.10,0.10,0.15,0.10], n),
        "jurisdiction": weighted_choice(jurisdictions, [0.20,0.12,0.12,0.10,0.08,0.08,0.08,0.08,0.07,0.07], n),
        "period_year":  rng.integers(DATA_START_YEAR, DATA_END_YEAR + 1, n),
        "filing_date":  filing_dates,
        "due_date":     pd.Series([
            filing_dates.iloc[i] - pd.Timedelta(days=int(rng.integers(-5, 20)))
            for i in range(n)
        ]),
        "status":       weighted_choice(statuses, [0.60, 0.15, 0.15, 0.05, 0.05], n),
        "submitted_by": [fake.name() for _ in range(n)],
        "notes":        inject_nulls(pd.Series([fake.sentence() for _ in range(n)]), 0.60),
        "created_at":   filing_dates,
    })


def generate_compliance_checks() -> pd.DataFrame:
    n = ROW_COUNTS["compliance_checks"]
    n_customers = ROW_COUNTS["customers"]
    check_types = ["AML", "SANCTIONS", "PEP", "KYC", "FRAUD_SCREEN"]
    results     = ["PASS", "FAIL", "REVIEW"]
    risk_levels = ["LOW", "MEDIUM", "HIGH"]

    return pd.DataFrame({
        "check_id":    sequential_ids(n),
        "customer_id": foreign_keys(n, n_customers),
        "check_type":  weighted_choice(check_types, [0.25, 0.20, 0.15, 0.25, 0.15], n),
        "check_date":  random_dates(n),
        "result":      weighted_choice(results, [0.88, 0.04, 0.08], n),
        "risk_level":  weighted_choice(risk_levels, [0.70, 0.22, 0.08], n),
        "checked_by":  weighted_choice(["SYSTEM", "MANUAL"], [0.80, 0.20], n),
        "notes":       inject_nulls(pd.Series([fake.sentence() for _ in range(n)]), 0.70),
        "created_at":  random_dates(n),
    })


def generate_call_center_interactions() -> pd.DataFrame:
    n = ROW_COUNTS["call_center_interactions"]
    n_customers = ROW_COUNTS["customers"]
    n_agents    = ROW_COUNTS["agents"]
    n_policies  = ROW_COUNTS["policies"]
    n_claims    = ROW_COUNTS["claims"]

    channels   = ["PHONE", "CHAT", "EMAIL", "VIDEO"]
    directions = ["INBOUND", "OUTBOUND"]
    purposes   = ["POLICY_INQUIRY", "CLAIM_UPDATE", "BILLING", "COMPLAINT",
                  "RENEWAL", "CANCELLATION", "NEW_QUOTE", "GENERAL"]
    outcomes   = ["RESOLVED", "ESCALATED", "CALLBACK_SCHEDULED", "TRANSFERRED", "ABANDONED"]

    # More calls Mon-Fri, dip weekends; peaks 9am-5pm but we store date only
    interaction_dates = seasonal_dates(n, peak_months=[1, 3, 6, 9, 11])
    # Duration: inbound calls longer
    direction = weighted_choice(directions, [0.75, 0.25], n)
    duration  = np.where(
        direction == "INBOUND",
        rng.integers(60, 1800, n),
        rng.integers(30, 600, n)
    )

    return pd.DataFrame({
        "interaction_id":   sequential_ids(n),
        "customer_id":      foreign_keys(n, n_customers),
        "agent_id":         inject_nulls(foreign_keys(n, n_agents), 0.05),
        "interaction_date": interaction_dates,
        "channel":          weighted_choice(channels, [0.55, 0.25, 0.15, 0.05], n),
        "direction":        pd.Series(direction),
        "duration_seconds": duration,
        "purpose":          weighted_choice(purposes, [0.20,0.20,0.15,0.10,0.12,0.05,0.08,0.10], n),
        "outcome":          weighted_choice(outcomes, [0.60, 0.12, 0.15, 0.08, 0.05], n),
        "satisfaction_score": inject_nulls(pd.Series(rng.integers(1, 6, n)), 0.45),
        "policy_id":        inject_nulls(foreign_keys(n, n_policies), 0.35),
        "claim_id":         inject_nulls(foreign_keys(n, n_claims), 0.55),
        "recording_ref":    inject_nulls(pd.Series([f"REC-{fake.uuid4()}" for _ in range(n)]), 0.30),
        "created_at":       interaction_dates,
    })


def generate_notifications() -> pd.DataFrame:
    n = ROW_COUNTS["notifications"]
    n_customers = ROW_COUNTS["customers"]
    n_policies  = ROW_COUNTS["policies"]
    n_claims    = ROW_COUNTS["claims"]

    notif_types = ["RENEWAL_REMINDER", "PAYMENT_DUE", "CLAIM_UPDATE", "POLICY_ISSUED",
                   "CANCELLATION_NOTICE", "DOCUMENT_READY", "FRAUD_ALERT", "SURVEY"]
    channels    = ["EMAIL", "SMS", "PUSH", "LETTER"]
    statuses    = ["SENT", "DELIVERED", "FAILED", "BOUNCED"]

    sent_times = seasonal_dates(n)
    return pd.DataFrame({
        "notification_id":  sequential_ids(n),
        "customer_id":      foreign_keys(n, n_customers),
        "policy_id":        inject_nulls(foreign_keys(n, n_policies), 0.25),
        "claim_id":         inject_nulls(foreign_keys(n, n_claims), 0.55),
        "notification_type": weighted_choice(notif_types, [0.20,0.20,0.15,0.12,0.10,0.10,0.05,0.08], n),
        "channel":          weighted_choice(channels, [0.45, 0.30, 0.15, 0.10], n),
        "sent_at":          sent_times,
        "subject":          inject_nulls(pd.Series([fake.sentence(nb_words=6) for _ in range(n)]), 0.30),
        "status":           weighted_choice(statuses, [0.20, 0.70, 0.06, 0.04], n),
        "opened_at":        inject_nulls(pd.Series(future_dates(sent_times, 0, 7)), 0.55),
        "created_at":       sent_times,
    })


def generate_system_config() -> pd.DataFrame:
    n = ROW_COUNTS["system_config"]
    config_types = ["STRING", "INTEGER", "BOOLEAN", "JSON", "DATE"]
    keys = [
        f"{'_'.join(fake.words(nb=3, unique=True)).upper()}"
        for _ in range(n)
    ]
    # Deduplicate keys
    seen = set()
    unique_keys = []
    for k in keys:
        while k in seen:
            k = k + "_1"
        seen.add(k)
        unique_keys.append(k)

    df = pd.DataFrame({
        "config_id":        sequential_ids(n),
        "config_key":       pd.Series(unique_keys),
        "config_value":     [fake.word() for _ in range(n)],
        "config_type":      weighted_choice(config_types, [0.35, 0.25, 0.20, 0.12, 0.08], n),
        "description":      inject_nulls(pd.Series([fake.sentence() for _ in range(n)]), 0.30),
        "is_active":        weighted_choice([True, False], [0.85, 0.15], n),
        "last_modified_by": inject_nulls(pd.Series([fake.name() for _ in range(n)]), 0.20),
        "created_at":       random_dates(n),
        "updated_at":       random_dates(n),
    })

    extra_df = pd.DataFrame(generate_wide_columns(n, WIDE_EXTRA_COLUMNS["system_config"], "cfg"))
    df = pd.concat([df, extra_df], axis=1)

    return df


FINANCE_GENERATORS = {
    "financial_periods": generate_financial_periods,
    "general_ledger":    generate_general_ledger,
    "invoices":          generate_invoices,
    "refunds":           generate_refunds,
    "commissions":       generate_commissions,
    "tax_records":       generate_tax_records,
    "reserve_estimates": generate_reserve_estimates,
}

OPS_GENERATORS = {
    "audit_logs":               generate_audit_logs,
    "complaints":               generate_complaints,
    "regulatory_filings":       generate_regulatory_filings,
    "compliance_checks":        generate_compliance_checks,
    "call_center_interactions": generate_call_center_interactions,
    "notifications":            generate_notifications,
    "system_config":            generate_system_config,
}
