"""
DDL definitions for all 50 tables.

Notes:
  - Deliberately NOT perfectly normalised (mirrors industry reality)
  - customer address columns intentionally duplicated across 3 tables
  - Some wide tables have placeholder cols (ext_col_001 etc) — these are
    filled dynamically by the generators with realistic data
  - FKs are defined but NOT enforced at generation time (data loaded via COPY)
    — enforced at Supabase level via connector/loader.py
"""

TABLES: dict[str, str] = {}

# ── CUSTOMERS & PARTIES ────────────────────────────────────────────────────

TABLES["customers"] = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id         SERIAL PRIMARY KEY,
    customer_ref        VARCHAR(20)  UNIQUE NOT NULL,
    first_name          VARCHAR(80),
    last_name           VARCHAR(80),
    date_of_birth       DATE,
    gender              VARCHAR(20),
    marital_status      VARCHAR(30),
    ssn_hash            VARCHAR(64),
    email               VARCHAR(120),
    phone_primary       VARCHAR(30),
    phone_secondary     VARCHAR(30),
    occupation          VARCHAR(100),
    employer_name       VARCHAR(120),
    annual_income       NUMERIC(14,2),
    income_band         VARCHAR(20),
    -- Address block A (deliberate denorm — also in customer_addresses)
    address_line1       VARCHAR(200),
    address_line2       VARCHAR(200),
    city                VARCHAR(80),
    state               VARCHAR(5),
    zip_code            VARCHAR(12),
    country             VARCHAR(50) DEFAULT 'US',
    -- Address block B (legacy — old mailing address)
    mail_address1       VARCHAR(200),
    mail_city           VARCHAR(80),
    mail_state          VARCHAR(5),
    mail_zip            VARCHAR(12),
    -- Segment / marketing
    customer_segment    VARCHAR(40),
    acquisition_channel VARCHAR(60),
    acquisition_date    DATE,
    -- Risk profile (denorm from underwriting — stored here for fast lookup)
    risk_tier           VARCHAR(20),
    credit_score_band   VARCHAR(20),
    lifetime_value      NUMERIC(14,2),
    churn_score         NUMERIC(5,4),
    -- Metadata
    is_active           BOOLEAN DEFAULT TRUE,
    is_vip              BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    -- Legacy / wide columns added dynamically
    ext_col_start       INT DEFAULT 0  -- marker; actual ext cols appended by generator
);
"""

TABLES["customer_addresses"] = """
CREATE TABLE IF NOT EXISTS customer_addresses (
    address_id      SERIAL PRIMARY KEY,
    customer_id     INT NOT NULL,
    address_type    VARCHAR(30),  -- MAILING, BILLING, PROPERTY, PREVIOUS
    address_line1   VARCHAR(200),
    address_line2   VARCHAR(200),
    city            VARCHAR(80),
    state           VARCHAR(5),
    zip_code        VARCHAR(12),
    country         VARCHAR(50) DEFAULT 'US',
    is_current      BOOLEAN DEFAULT TRUE,
    valid_from      DATE,
    valid_to        DATE,
    created_at      TIMESTAMP DEFAULT NOW()
);
"""

TABLES["customer_contacts"] = """
CREATE TABLE IF NOT EXISTS customer_contacts (
    contact_id          SERIAL PRIMARY KEY,
    customer_id         INT NOT NULL,
    contact_type        VARCHAR(30),  -- EMAIL, MOBILE, HOME, WORK
    contact_value       VARCHAR(150),
    is_primary          BOOLEAN DEFAULT FALSE,
    is_verified         BOOLEAN DEFAULT FALSE,
    opt_in_marketing    BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["beneficiaries"] = """
CREATE TABLE IF NOT EXISTS beneficiaries (
    beneficiary_id      SERIAL PRIMARY KEY,
    policy_id           INT NOT NULL,
    customer_id         INT,
    first_name          VARCHAR(80),
    last_name           VARCHAR(80),
    relationship        VARCHAR(50),
    date_of_birth       DATE,
    share_percentage    NUMERIC(5,2),
    is_primary          BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["agents"] = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id            SERIAL PRIMARY KEY,
    agent_code          VARCHAR(20) UNIQUE,
    first_name          VARCHAR(80),
    last_name           VARCHAR(80),
    email               VARCHAR(120),
    phone               VARCHAR(30),
    license_number      VARCHAR(50),
    license_state       VARCHAR(5),
    license_expiry      DATE,
    agency_name         VARCHAR(120),
    region              VARCHAR(60),
    manager_agent_id    INT,
    commission_tier     VARCHAR(20),
    hire_date           DATE,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["agent_performance"] = """
CREATE TABLE IF NOT EXISTS agent_performance (
    perf_id             SERIAL PRIMARY KEY,
    agent_id            INT NOT NULL,
    period_year         SMALLINT,
    period_month        SMALLINT,
    policies_sold       INT DEFAULT 0,
    policies_renewed    INT DEFAULT 0,
    policies_cancelled  INT DEFAULT 0,
    total_premium       NUMERIC(14,2),
    total_commission    NUMERIC(14,2),
    claims_generated    INT DEFAULT 0,
    customer_satisfaction_score NUMERIC(4,2),
    conversion_rate     NUMERIC(5,4),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["third_parties"] = """
CREATE TABLE IF NOT EXISTS third_parties (
    third_party_id      SERIAL PRIMARY KEY,
    party_type          VARCHAR(40),  -- CLAIMANT, WITNESS, LEGAL_REP, EXPERT
    first_name          VARCHAR(80),
    last_name           VARCHAR(80),
    company_name        VARCHAR(120),
    phone               VARCHAR(30),
    email               VARCHAR(120),
    address_line1       VARCHAR(200),
    city                VARCHAR(80),
    state               VARCHAR(5),
    zip_code            VARCHAR(12),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["employers"] = """
CREATE TABLE IF NOT EXISTS employers (
    employer_id         SERIAL PRIMARY KEY,
    employer_name       VARCHAR(150),
    industry            VARCHAR(80),
    sic_code            VARCHAR(10),
    address_line1       VARCHAR(200),
    city                VARCHAR(80),
    state               VARCHAR(5),
    zip_code            VARCHAR(12),
    employee_count_band VARCHAR(30),
    group_policy_eligible BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

# ── POLICIES ───────────────────────────────────────────────────────────────

TABLES["policies"] = """
CREATE TABLE IF NOT EXISTS policies (
    policy_id           SERIAL PRIMARY KEY,
    policy_number       VARCHAR(30) UNIQUE NOT NULL,
    customer_id         INT NOT NULL,
    product_id          INT NOT NULL,
    agent_id            INT,
    -- Dates
    quote_date          DATE,
    inception_date      DATE,
    expiry_date         DATE,
    cancellation_date   DATE,
    -- Status
    policy_status       VARCHAR(30),  -- ACTIVE, LAPSED, CANCELLED, EXPIRED, PENDING
    payment_frequency   VARCHAR(20),  -- MONTHLY, QUARTERLY, ANNUAL
    payment_method      VARCHAR(30),
    -- Financials
    annual_premium      NUMERIC(12,2),
    gross_premium       NUMERIC(12,2),
    net_premium         NUMERIC(12,2),
    tax_amount          NUMERIC(10,2),
    discount_amount     NUMERIC(10,2),
    sum_insured         NUMERIC(14,2),
    deductible_amount   NUMERIC(10,2),
    -- Policy type flags (denorm for speed — also in coverage_details)
    covers_property     BOOLEAN DEFAULT FALSE,
    covers_vehicle      BOOLEAN DEFAULT FALSE,
    covers_life         BOOLEAN DEFAULT FALSE,
    covers_health       BOOLEAN DEFAULT FALSE,
    covers_liability    BOOLEAN DEFAULT FALSE,
    -- Address of insured (denorm from customers)
    insured_address1    VARCHAR(200),
    insured_city        VARCHAR(80),
    insured_state       VARCHAR(5),
    insured_zip         VARCHAR(12),
    -- Metadata
    underwriter_id      INT,
    channel             VARCHAR(40),
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    ext_col_start       INT DEFAULT 0
);
"""

TABLES["policy_versions"] = """
CREATE TABLE IF NOT EXISTS policy_versions (
    version_id          SERIAL PRIMARY KEY,
    policy_id           INT NOT NULL,
    version_number      SMALLINT,
    change_type         VARCHAR(40),  -- ENDORSEMENT, RENEWAL, CORRECTION, CANCELLATION
    changed_by          VARCHAR(80),
    change_reason       VARCHAR(200),
    previous_premium    NUMERIC(12,2),
    new_premium         NUMERIC(12,2),
    effective_date      DATE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["policy_endorsements"] = """
CREATE TABLE IF NOT EXISTS policy_endorsements (
    endorsement_id      SERIAL PRIMARY KEY,
    policy_id           INT NOT NULL,
    endorsement_type    VARCHAR(60),
    description         TEXT,
    premium_adjustment  NUMERIC(10,2),
    effective_date      DATE,
    expiry_date         DATE,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["policy_documents"] = """
CREATE TABLE IF NOT EXISTS policy_documents (
    document_id         SERIAL PRIMARY KEY,
    policy_id           INT NOT NULL,
    document_type       VARCHAR(60),
    document_name       VARCHAR(200),
    storage_ref         VARCHAR(300),
    file_size_kb        INT,
    uploaded_by         VARCHAR(80),
    upload_date         DATE,
    is_current          BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["policy_payments"] = """
CREATE TABLE IF NOT EXISTS policy_payments (
    payment_id          SERIAL PRIMARY KEY,
    policy_id           INT NOT NULL,
    customer_id         INT NOT NULL,
    payment_date        DATE,
    due_date            DATE,
    amount              NUMERIC(12,2),
    payment_status      VARCHAR(30),  -- PAID, PENDING, FAILED, REVERSED
    payment_method      VARCHAR(30),
    transaction_ref     VARCHAR(60),
    days_overdue        SMALLINT DEFAULT 0,
    late_fee            NUMERIC(8,2),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["policy_cancellations"] = """
CREATE TABLE IF NOT EXISTS policy_cancellations (
    cancellation_id     SERIAL PRIMARY KEY,
    policy_id           INT NOT NULL,
    customer_id         INT NOT NULL,
    cancellation_date   DATE,
    cancellation_reason VARCHAR(100),
    initiated_by        VARCHAR(30),  -- CUSTOMER, INSURER, SYSTEM
    refund_amount       NUMERIC(12,2),
    refund_status       VARCHAR(30),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["policy_renewals"] = """
CREATE TABLE IF NOT EXISTS policy_renewals (
    renewal_id          SERIAL PRIMARY KEY,
    policy_id           INT NOT NULL,
    customer_id         INT NOT NULL,
    renewal_date        DATE,
    previous_premium    NUMERIC(12,2),
    new_premium         NUMERIC(12,2),
    premium_change_pct  NUMERIC(6,2),
    auto_renewed        BOOLEAN DEFAULT FALSE,
    renewal_status      VARCHAR(30),
    offer_sent_date     DATE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["coverage_details"] = """
CREATE TABLE IF NOT EXISTS coverage_details (
    coverage_id         SERIAL PRIMARY KEY,
    policy_id           INT NOT NULL UNIQUE,
    -- Core limits
    property_limit      NUMERIC(14,2),
    vehicle_limit       NUMERIC(14,2),
    liability_limit     NUMERIC(14,2),
    medical_limit       NUMERIC(14,2),
    personal_prop_limit NUMERIC(14,2),
    -- Deductibles
    property_deductible NUMERIC(10,2),
    vehicle_deductible  NUMERIC(10,2),
    medical_deductible  NUMERIC(10,2),
    -- Coverage flags (wide section)
    fire_covered        BOOLEAN DEFAULT FALSE,
    flood_covered       BOOLEAN DEFAULT FALSE,
    earthquake_covered  BOOLEAN DEFAULT FALSE,
    theft_covered       BOOLEAN DEFAULT FALSE,
    vandalism_covered   BOOLEAN DEFAULT FALSE,
    windstorm_covered   BOOLEAN DEFAULT FALSE,
    hail_covered        BOOLEAN DEFAULT FALSE,
    collision_covered   BOOLEAN DEFAULT FALSE,
    comprehensive_covered BOOLEAN DEFAULT FALSE,
    uninsured_motorist  BOOLEAN DEFAULT FALSE,
    roadside_assist     BOOLEAN DEFAULT FALSE,
    rental_coverage     BOOLEAN DEFAULT FALSE,
    -- Life/health
    accidental_death    BOOLEAN DEFAULT FALSE,
    disability_covered  BOOLEAN DEFAULT FALSE,
    critical_illness    BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT NOW(),
    ext_col_start       INT DEFAULT 0
);
"""

TABLES["products"] = """
CREATE TABLE IF NOT EXISTS products (
    product_id          SERIAL PRIMARY KEY,
    product_code        VARCHAR(20) UNIQUE,
    product_name        VARCHAR(100),
    product_category    VARCHAR(50),  -- AUTO, HOME, LIFE, HEALTH, COMMERCIAL
    product_line        VARCHAR(50),
    is_active           BOOLEAN DEFAULT TRUE,
    min_sum_insured     NUMERIC(14,2),
    max_sum_insured     NUMERIC(14,2),
    base_rate           NUMERIC(6,4),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["product_pricing_rules"] = """
CREATE TABLE IF NOT EXISTS product_pricing_rules (
    rule_id             SERIAL PRIMARY KEY,
    product_id          INT NOT NULL,
    rule_name           VARCHAR(100),
    rule_type           VARCHAR(40),  -- LOADING, DISCOUNT, BASE
    factor_name         VARCHAR(80),
    factor_value        NUMERIC(8,4),
    effective_date      DATE,
    expiry_date         DATE,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

# ── CLAIMS ─────────────────────────────────────────────────────────────────

TABLES["claims"] = """
CREATE TABLE IF NOT EXISTS claims (
    claim_id            SERIAL PRIMARY KEY,
    claim_number        VARCHAR(30) UNIQUE NOT NULL,
    policy_id           INT NOT NULL,
    customer_id         INT NOT NULL,
    -- Incident
    incident_date       DATE,
    reported_date       DATE,
    incident_type       VARCHAR(60),
    incident_description TEXT,
    incident_city       VARCHAR(80),
    incident_state      VARCHAR(5),
    -- Status
    claim_status        VARCHAR(40),  -- OPEN, UNDER_REVIEW, APPROVED, REJECTED, CLOSED, LITIGATED
    priority            VARCHAR(20),
    -- Financials
    claimed_amount      NUMERIC(14,2),
    approved_amount     NUMERIC(14,2),
    paid_amount         NUMERIC(14,2),
    reserve_amount      NUMERIC(14,2),
    salvage_amount      NUMERIC(10,2),
    subrogation_amount  NUMERIC(10,2),
    -- Handlers
    adjuster_id         INT,
    adjuster_name       VARCHAR(80),
    -- Flags
    is_fraud_suspected  BOOLEAN DEFAULT FALSE,
    is_litigated        BOOLEAN DEFAULT FALSE,
    is_reinsured        BOOLEAN DEFAULT FALSE,
    -- Dates
    closed_date         DATE,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    ext_col_start       INT DEFAULT 0
);
"""

TABLES["claim_events"] = """
CREATE TABLE IF NOT EXISTS claim_events (
    event_id            SERIAL PRIMARY KEY,
    claim_id            INT NOT NULL,
    event_type          VARCHAR(60),
    event_description   TEXT,
    performed_by        VARCHAR(80),
    performed_by_role   VARCHAR(50),
    event_date          TIMESTAMP,
    old_status          VARCHAR(40),
    new_status          VARCHAR(40),
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["claim_payments"] = """
CREATE TABLE IF NOT EXISTS claim_payments (
    payment_id          SERIAL PRIMARY KEY,
    claim_id            INT NOT NULL,
    policy_id           INT NOT NULL,
    customer_id         INT NOT NULL,
    payment_type        VARCHAR(40),  -- SETTLEMENT, INTERIM, MEDICAL, LEGAL
    payment_date        DATE,
    amount              NUMERIC(14,2),
    payment_method      VARCHAR(30),
    payee_name          VARCHAR(120),
    payee_type          VARCHAR(30),  -- CUSTOMER, REPAIR_SHOP, MEDICAL, LEGAL
    bank_ref            VARCHAR(80),
    payment_status      VARCHAR(30),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["claim_documents"] = """
CREATE TABLE IF NOT EXISTS claim_documents (
    document_id         SERIAL PRIMARY KEY,
    claim_id            INT NOT NULL,
    document_type       VARCHAR(60),
    document_name       VARCHAR(200),
    storage_ref         VARCHAR(300),
    uploaded_by         VARCHAR(80),
    upload_date         DATE,
    is_verified         BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["claim_assessments"] = """
CREATE TABLE IF NOT EXISTS claim_assessments (
    assessment_id       SERIAL PRIMARY KEY,
    claim_id            INT NOT NULL,
    adjuster_id         INT,
    assessment_date     DATE,
    coverage_decision   VARCHAR(30),  -- COVERED, PARTIAL, EXCLUDED, PENDING
    coverage_notes      TEXT,
    recommended_amount  NUMERIC(14,2),
    final_amount        NUMERIC(14,2),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["claim_fraud_flags"] = """
CREATE TABLE IF NOT EXISTS claim_fraud_flags (
    flag_id             SERIAL PRIMARY KEY,
    claim_id            INT NOT NULL,
    flag_type           VARCHAR(60),
    fraud_score         NUMERIC(5,4),
    flag_reason         VARCHAR(200),
    flagged_by          VARCHAR(40),  -- SYSTEM, ADJUSTER, EXTERNAL
    investigation_status VARCHAR(30),
    outcome             VARCHAR(30),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["claim_litigations"] = """
CREATE TABLE IF NOT EXISTS claim_litigations (
    litigation_id       SERIAL PRIMARY KEY,
    claim_id            INT NOT NULL,
    filed_date          DATE,
    court               VARCHAR(120),
    plaintiff           VARCHAR(120),
    defendant           VARCHAR(120),
    case_number         VARCHAR(60),
    legal_counsel       VARCHAR(120),
    status              VARCHAR(40),
    settlement_amount   NUMERIC(14,2),
    closed_date         DATE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["repair_shops"] = """
CREATE TABLE IF NOT EXISTS repair_shops (
    shop_id             SERIAL PRIMARY KEY,
    shop_name           VARCHAR(150),
    shop_type           VARCHAR(40),  -- AUTO, PROPERTY, MEDICAL, GENERAL
    address_line1       VARCHAR(200),
    city                VARCHAR(80),
    state               VARCHAR(5),
    zip_code            VARCHAR(12),
    phone               VARCHAR(30),
    is_preferred        BOOLEAN DEFAULT FALSE,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["claim_repairs"] = """
CREATE TABLE IF NOT EXISTS claim_repairs (
    repair_id           SERIAL PRIMARY KEY,
    claim_id            INT NOT NULL,
    shop_id             INT,
    repair_type         VARCHAR(60),
    authorized_amount   NUMERIC(12,2),
    actual_amount       NUMERIC(12,2),
    start_date          DATE,
    completion_date     DATE,
    repair_status       VARCHAR(30),
    customer_satisfaction SMALLINT,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["medical_reports"] = """
CREATE TABLE IF NOT EXISTS medical_reports (
    report_id           SERIAL PRIMARY KEY,
    claim_id            INT NOT NULL,
    customer_id         INT NOT NULL,
    provider_name       VARCHAR(150),
    provider_type       VARCHAR(60),
    diagnosis_code      VARCHAR(20),
    diagnosis_desc      VARCHAR(200),
    treatment_start     DATE,
    treatment_end       DATE,
    total_cost          NUMERIC(12,2),
    approved_cost       NUMERIC(12,2),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

# ── UNDERWRITING & RISK ────────────────────────────────────────────────────

TABLES["underwriting_assessments"] = """
CREATE TABLE IF NOT EXISTS underwriting_assessments (
    assessment_id       SERIAL PRIMARY KEY,
    policy_id           INT NOT NULL,
    customer_id         INT NOT NULL,
    assessed_date       DATE,
    underwriter_id      INT,
    overall_risk_score  NUMERIC(6,2),
    risk_category       VARCHAR(30),  -- LOW, MEDIUM, HIGH, VERY_HIGH
    decision            VARCHAR(30),  -- APPROVED, DECLINED, REFERRED, MODIFIED
    decision_notes      TEXT,
    base_premium        NUMERIC(12,2),
    loading_pct         NUMERIC(6,2),
    discount_pct        NUMERIC(6,2),
    final_premium       NUMERIC(12,2),
    created_at          TIMESTAMP DEFAULT NOW(),
    ext_col_start       INT DEFAULT 0
);
"""

TABLES["risk_scores"] = """
CREATE TABLE IF NOT EXISTS risk_scores (
    score_id            SERIAL PRIMARY KEY,
    customer_id         INT NOT NULL,
    score_date          DATE,
    score_type          VARCHAR(40),  -- CREDIT, FRAUD, CHURN, CLAIMS, OVERALL
    score_value         NUMERIC(7,2),
    score_band          VARCHAR(20),
    model_version       VARCHAR(20),
    contributing_factors JSONB,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["quote_attempts"] = """
CREATE TABLE IF NOT EXISTS quote_attempts (
    quote_id            SERIAL PRIMARY KEY,
    quote_ref           VARCHAR(30) UNIQUE,
    customer_id         INT,
    product_id          INT,
    agent_id            INT,
    quote_date          DATE,
    channel             VARCHAR(40),
    quoted_premium      NUMERIC(12,2),
    sum_insured         NUMERIC(14,2),
    converted           BOOLEAN DEFAULT FALSE,
    policy_id           INT,  -- NULL if not converted
    abandon_reason      VARCHAR(100),
    session_duration_sec INT,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["credit_checks"] = """
CREATE TABLE IF NOT EXISTS credit_checks (
    check_id            SERIAL PRIMARY KEY,
    customer_id         INT NOT NULL,
    check_date          DATE,
    bureau              VARCHAR(40),
    credit_score        SMALLINT,
    credit_band         VARCHAR(20),
    derogatory_marks    SMALLINT DEFAULT 0,
    bankruptcy          BOOLEAN DEFAULT FALSE,
    response_code       VARCHAR(10),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["inspection_reports"] = """
CREATE TABLE IF NOT EXISTS inspection_reports (
    inspection_id       SERIAL PRIMARY KEY,
    policy_id           INT NOT NULL,
    inspection_date     DATE,
    inspector_name      VARCHAR(100),
    inspection_type     VARCHAR(40),
    property_condition  VARCHAR(30),
    risk_notes          TEXT,
    passed              BOOLEAN,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["exclusions"] = """
CREATE TABLE IF NOT EXISTS exclusions (
    exclusion_id        SERIAL PRIMARY KEY,
    policy_id           INT NOT NULL,
    exclusion_type      VARCHAR(80),
    description         TEXT,
    effective_date      DATE,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["reinsurance_treaties"] = """
CREATE TABLE IF NOT EXISTS reinsurance_treaties (
    treaty_id           SERIAL PRIMARY KEY,
    treaty_name         VARCHAR(100),
    reinsurer_name      VARCHAR(120),
    treaty_type         VARCHAR(40),  -- QUOTA_SHARE, EXCESS_LOSS, FACULTATIVE
    share_percentage    NUMERIC(5,2),
    retention_limit     NUMERIC(14,2),
    effective_date      DATE,
    expiry_date         DATE,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["reinsurance_claims"] = """
CREATE TABLE IF NOT EXISTS reinsurance_claims (
    rei_claim_id        SERIAL PRIMARY KEY,
    claim_id            INT NOT NULL,
    treaty_id           INT NOT NULL,
    cession_amount      NUMERIC(14,2),
    recovery_amount     NUMERIC(14,2),
    recovery_date       DATE,
    status              VARCHAR(30),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

# ── FINANCE & ACCOUNTING ───────────────────────────────────────────────────

TABLES["general_ledger"] = """
CREATE TABLE IF NOT EXISTS general_ledger (
    ledger_id           SERIAL PRIMARY KEY,
    posting_date        DATE,
    account_code        VARCHAR(20),
    account_name        VARCHAR(100),
    entity_type         VARCHAR(30),  -- POLICY, CLAIM, COMMISSION, TAX
    entity_id           INT,
    debit_amount        NUMERIC(14,2) DEFAULT 0,
    credit_amount       NUMERIC(14,2) DEFAULT 0,
    currency            VARCHAR(3) DEFAULT 'USD',
    description         VARCHAR(200),
    batch_ref           VARCHAR(40),
    period_id           INT,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["invoices"] = """
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id          SERIAL PRIMARY KEY,
    invoice_number      VARCHAR(30) UNIQUE,
    policy_id           INT NOT NULL,
    customer_id         INT NOT NULL,
    invoice_date        DATE,
    due_date            DATE,
    amount              NUMERIC(12,2),
    tax_amount          NUMERIC(10,2),
    total_amount        NUMERIC(12,2),
    status              VARCHAR(20),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["refunds"] = """
CREATE TABLE IF NOT EXISTS refunds (
    refund_id           SERIAL PRIMARY KEY,
    policy_id           INT,
    claim_id            INT,
    customer_id         INT NOT NULL,
    refund_date         DATE,
    refund_amount       NUMERIC(12,2),
    refund_reason       VARCHAR(100),
    refund_method       VARCHAR(30),
    status              VARCHAR(20),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["commissions"] = """
CREATE TABLE IF NOT EXISTS commissions (
    commission_id       SERIAL PRIMARY KEY,
    agent_id            INT NOT NULL,
    policy_id           INT NOT NULL,
    commission_type     VARCHAR(40),  -- NEW_BUSINESS, RENEWAL, BONUS
    base_amount         NUMERIC(12,2),
    rate_pct            NUMERIC(5,2),
    commission_amount   NUMERIC(12,2),
    period_year         SMALLINT,
    period_month        SMALLINT,
    payment_status      VARCHAR(20),
    paid_date           DATE,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["tax_records"] = """
CREATE TABLE IF NOT EXISTS tax_records (
    tax_id              SERIAL PRIMARY KEY,
    policy_id           INT NOT NULL,
    customer_id         INT NOT NULL,
    tax_year            SMALLINT,
    tax_type            VARCHAR(40),
    taxable_amount      NUMERIC(12,2),
    tax_rate            NUMERIC(5,4),
    tax_amount          NUMERIC(10,2),
    filing_status       VARCHAR(20),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["reserve_estimates"] = """
CREATE TABLE IF NOT EXISTS reserve_estimates (
    reserve_id          SERIAL PRIMARY KEY,
    claim_id            INT NOT NULL,
    estimate_date       DATE,
    estimator_id        INT,
    reserve_type        VARCHAR(40),  -- CASE, IBNR, BULK
    gross_reserve       NUMERIC(14,2),
    net_reserve         NUMERIC(14,2),
    ceded_reserve       NUMERIC(14,2),
    method_used         VARCHAR(60),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["financial_periods"] = """
CREATE TABLE IF NOT EXISTS financial_periods (
    period_id           SERIAL PRIMARY KEY,
    period_year         SMALLINT,
    period_month        SMALLINT,
    period_label        VARCHAR(20),
    start_date          DATE,
    end_date            DATE,
    is_closed           BOOLEAN DEFAULT FALSE,
    closed_at           TIMESTAMP,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

# ── OPERATIONS & COMPLIANCE ────────────────────────────────────────────────

TABLES["audit_logs"] = """
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id              SERIAL PRIMARY KEY,
    event_time          TIMESTAMP NOT NULL,
    user_id             VARCHAR(80),
    user_role           VARCHAR(50),
    action              VARCHAR(60),
    entity_type         VARCHAR(50),
    entity_id           INT,
    old_values          JSONB,
    new_values          JSONB,
    ip_address          VARCHAR(45),
    session_id          VARCHAR(80),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["complaints"] = """
CREATE TABLE IF NOT EXISTS complaints (
    complaint_id        SERIAL PRIMARY KEY,
    customer_id         INT NOT NULL,
    policy_id           INT,
    claim_id            INT,
    received_date       DATE,
    complaint_type      VARCHAR(60),
    channel             VARCHAR(30),
    description         TEXT,
    status              VARCHAR(30),
    resolution          TEXT,
    resolved_date       DATE,
    satisfaction_score  SMALLINT,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["regulatory_filings"] = """
CREATE TABLE IF NOT EXISTS regulatory_filings (
    filing_id           SERIAL PRIMARY KEY,
    filing_type         VARCHAR(60),
    jurisdiction        VARCHAR(60),
    period_year         SMALLINT,
    filing_date         DATE,
    due_date            DATE,
    status              VARCHAR(30),
    submitted_by        VARCHAR(80),
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["compliance_checks"] = """
CREATE TABLE IF NOT EXISTS compliance_checks (
    check_id            SERIAL PRIMARY KEY,
    customer_id         INT NOT NULL,
    check_type          VARCHAR(40),  -- AML, SANCTIONS, PEP, KYC
    check_date          DATE,
    result              VARCHAR(20),  -- PASS, FAIL, REVIEW
    risk_level          VARCHAR(20),
    checked_by          VARCHAR(40),  -- SYSTEM, MANUAL
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["call_center_interactions"] = """
CREATE TABLE IF NOT EXISTS call_center_interactions (
    interaction_id      SERIAL PRIMARY KEY,
    customer_id         INT NOT NULL,
    agent_id            INT,
    interaction_date    TIMESTAMP,
    channel             VARCHAR(30),  -- PHONE, CHAT, EMAIL, VIDEO
    direction           VARCHAR(10),  -- INBOUND, OUTBOUND
    duration_seconds    INT,
    purpose             VARCHAR(80),
    outcome             VARCHAR(60),
    satisfaction_score  SMALLINT,
    policy_id           INT,
    claim_id            INT,
    recording_ref       VARCHAR(100),
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["notifications"] = """
CREATE TABLE IF NOT EXISTS notifications (
    notification_id     SERIAL PRIMARY KEY,
    customer_id         INT NOT NULL,
    policy_id           INT,
    claim_id            INT,
    notification_type   VARCHAR(60),
    channel             VARCHAR(20),  -- EMAIL, SMS, PUSH, LETTER
    sent_at             TIMESTAMP,
    subject             VARCHAR(200),
    status              VARCHAR(20),  -- SENT, DELIVERED, FAILED, BOUNCED
    opened_at           TIMESTAMP,
    created_at          TIMESTAMP DEFAULT NOW()
);
"""

TABLES["system_config"] = """
CREATE TABLE IF NOT EXISTS system_config (
    config_id           SERIAL PRIMARY KEY,
    config_key          VARCHAR(100) UNIQUE,
    config_value        TEXT,
    config_type         VARCHAR(30),
    description         VARCHAR(200),
    is_active           BOOLEAN DEFAULT TRUE,
    last_modified_by    VARCHAR(80),
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    ext_col_start       INT DEFAULT 0
);
"""


def get_ddl(table_name: str, schema: str = "public") -> str:
    """One table's CREATE TABLE statement, qualified to `schema`."""
    ddl = TABLES[table_name]
    return ddl.replace(
        f"CREATE TABLE IF NOT EXISTS {table_name}",
        f"CREATE TABLE IF NOT EXISTS {schema}.{table_name}",
        1,
    )


def all_table_names() -> list[str]:
    """Every table name this schema defines DDL for."""
    return list(TABLES.keys())
