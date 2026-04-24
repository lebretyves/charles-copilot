-- ╔══════════════════════════════════════════════════════════════╗
-- ║  CHARLES — Schema PostgreSQL                                ║
-- ╚══════════════════════════════════════════════════════════════╝

-- Patients / Cas opératoires
CREATE TABLE IF NOT EXISTS cases (
    id              SERIAL PRIMARY KEY,
    case_id         VARCHAR(32) UNIQUE NOT NULL,
    patient_age     INT,
    patient_sex     VARCHAR(1),  -- M/F
    patient_weight  FLOAT,
    patient_height  FLOAT,
    asa_score       INT CHECK (asa_score BETWEEN 1 AND 5),
    surgery_type    VARCHAR(128),
    surgery_approach VARCHAR(64),
    anesthesia_type VARCHAR(64),  -- AG, ALR, sedation, combinee
    room_id         VARCHAR(16),
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    status          VARCHAR(16) DEFAULT 'active'  -- active, ended, cancelled
);

-- Alertes générées par le moteur
CREATE TABLE IF NOT EXISTS alerts (
    id              SERIAL PRIMARY KEY,
    case_id         VARCHAR(32) REFERENCES cases(case_id),
    room_id         VARCHAR(16),
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    level           VARCHAR(16) NOT NULL,  -- info, warning, critical
    rule_id         VARCHAR(64),
    title           VARCHAR(256),
    detail          TEXT,
    parameters      JSONB,       -- vitaux impliqués + valeurs
    acknowledged    BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(64)
);

-- Analyses LLM
CREATE TABLE IF NOT EXISTS llm_analyses (
    id              SERIAL PRIMARY KEY,
    case_id         VARCHAR(32) REFERENCES cases(case_id),
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    trigger_type    VARCHAR(32),   -- alert, threshold, manual, periodic
    model           VARCHAR(128),
    prompt_tokens   INT,
    completion_tokens INT,
    latency_ms      INT,
    analysis        JSONB,         -- situation, risques, recommandations
    feedback        VARCHAR(16),   -- useful, not_useful, null
    feedback_comment TEXT
);

-- Feedback IADE sur les alertes (pour ML)
CREATE TABLE IF NOT EXISTS alert_feedback (
    id              SERIAL PRIMARY KEY,
    alert_id        INT REFERENCES alerts(id),
    case_id         VARCHAR(32),
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    label           VARCHAR(16) NOT NULL, -- true_positive, false_positive, missed
    comment         TEXT
);

-- Administrations médicamenteuses (feuille d'anesthésie light)
CREATE TABLE IF NOT EXISTS drug_administrations (
    id              SERIAL PRIMARY KEY,
    case_id         VARCHAR(32) REFERENCES cases(case_id),
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    drug_name       VARCHAR(128) NOT NULL,
    dose            FLOAT,
    dose_unit       VARCHAR(16),
    route           VARCHAR(32),   -- IV, inhalation, epidural, etc.
    bolus_or_continuous VARCHAR(16), -- bolus, continuous, target
    rate            FLOAT,         -- pour perfusion continue (mL/h, µg/kg/min)
    rate_unit       VARCHAR(32),
    administered_by VARCHAR(64)
);

-- Événements peropératoires
CREATE TABLE IF NOT EXISTS case_events (
    id              SERIAL PRIMARY KEY,
    case_id         VARCHAR(32) REFERENCES cases(case_id),
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    event_type      VARCHAR(64) NOT NULL,  -- induction, intubation, incision, clampage, declampage, extubation, transfert_sspi
    detail          TEXT,
    recorded_by     VARCHAR(64)
);

-- Bilan entrées/sorties
CREATE TABLE IF NOT EXISTS fluid_balance (
    id              SERIAL PRIMARY KEY,
    case_id         VARCHAR(32) REFERENCES cases(case_id),
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    type            VARCHAR(16) NOT NULL,   -- input, output
    category        VARCHAR(64),             -- cristalloide, colloide, sang, diurese, pertes_sang, aspirations
    volume_ml       INT,
    product_name    VARCHAR(128)
);

-- Utilisateurs applicatifs
CREATE TABLE IF NOT EXISTS app_users (
    username            VARCHAR(64) PRIMARY KEY,
    password_hash       TEXT NOT NULL,
    role                VARCHAR(16) NOT NULL CHECK (role IN ('iade', 'mar', 'admin')),
    name                VARCHAR(128) NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    source              VARCHAR(32) NOT NULL DEFAULT 'admin',
    created_by          VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index pour les requêtes fréquentes
CREATE INDEX idx_alerts_case ON alerts(case_id);
CREATE INDEX idx_alerts_timestamp ON alerts(timestamp);
CREATE INDEX idx_drug_admin_case ON drug_administrations(case_id);
CREATE INDEX idx_case_events_case ON case_events(case_id);
CREATE INDEX idx_fluid_case ON fluid_balance(case_id);
CREATE INDEX idx_app_users_role ON app_users(role);
CREATE INDEX idx_app_users_active ON app_users(is_active);
