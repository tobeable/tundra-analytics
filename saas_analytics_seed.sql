-- Global SaaS Analytics synthetic dataset
-- Schema follows AGENTS.md exactly
-- Deterministic via setseed(); all generated with generate_series + random()

BEGIN;

SELECT setseed(0.42);

--------------------------------------------------------------------
-- Drop in reverse FK order
--------------------------------------------------------------------
DROP TABLE IF EXISTS customer_embeddings CASCADE;
DROP TABLE IF EXISTS invoices CASCADE;
DROP TABLE IF EXISTS usage_events CASCADE;
DROP TABLE IF EXISTS subscriptions CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS plans CASCADE;
DROP TABLE IF EXISTS countries CASCADE;

--------------------------------------------------------------------
-- 1. countries (~30)
--    PK: country_code CHAR(3) ISO-3 alpha-3
--------------------------------------------------------------------
CREATE TABLE countries (
    country_code  CHAR(3) PRIMARY KEY,
    country_name  TEXT NOT NULL,
    region        TEXT NOT NULL,
    latitude      NUMERIC(8,4) NOT NULL,
    longitude     NUMERIC(9,4) NOT NULL
);

INSERT INTO countries (country_code, country_name, region, latitude, longitude) VALUES
('USA','United States','North America',37.0902,-95.7129),
('CAN','Canada','North America',56.1304,-106.3468),
('MEX','Mexico','North America',23.6345,-102.5528),
('BRA','Brazil','South America',-14.2350,-51.9253),
('ARG','Argentina','South America',-38.4161,-63.6167),
('GBR','United Kingdom','Europe',55.3781,-3.4360),
('DEU','Germany','Europe',51.1657,10.4515),
('FRA','France','Europe',46.2276,2.2137),
('NLD','Netherlands','Europe',52.1326,5.2913),
('SWE','Sweden','Europe',60.1282,18.6435),
('ESP','Spain','Europe',40.4637,-3.7492),
('ITA','Italy','Europe',41.8719,12.5674),
('POL','Poland','Europe',51.9194,19.1451),
('CHE','Switzerland','Europe',46.8182,8.2275),
('IRL','Ireland','Europe',53.1424,-7.6921),
('IND','India','Asia',20.5937,78.9629),
('JPN','Japan','Asia',36.2048,138.2529),
('KOR','South Korea','Asia',35.9078,127.7669),
('SGP','Singapore','Asia',1.3521,103.8198),
('AUS','Australia','Oceania',-25.2744,133.7751),
('NZL','New Zealand','Oceania',-40.9006,174.8860),
('ISR','Israel','Middle East',31.0461,34.8516),
('ARE','United Arab Emirates','Middle East',23.4241,53.8478),
('ZAF','South Africa','Africa',-30.5595,22.9375),
('NGA','Nigeria','Africa',9.0820,8.6753),
('KEN','Kenya','Africa',-0.0236,37.9062),
('EGY','Egypt','Africa',26.8206,30.8025),
('COL','Colombia','South America',4.5709,-74.2973),
('CHL','Chile','South America',-35.6751,-71.5430),
('IDN','Indonesia','Asia',-0.7893,113.9213);

--------------------------------------------------------------------
-- 2. plans
--    PK: plan_id; plan_name (Starter/Pro/Enterprise); monthly_price; seat_limit; features TEXT[]
--------------------------------------------------------------------
CREATE TABLE plans (
    plan_id       SERIAL PRIMARY KEY,
    plan_name     TEXT NOT NULL UNIQUE,
    monthly_price NUMERIC(10,2) NOT NULL,
    seat_limit    INT NOT NULL,
    features      TEXT[] NOT NULL
);

INSERT INTO plans (plan_name, monthly_price, seat_limit, features) VALUES
('Starter',     29.00,   5,  ARRAY['dashboard','email_support','5_projects']),
('Pro',        149.00,  25,  ARRAY['dashboard','priority_support','unlimited_projects','api_access','sso']),
('Enterprise', 499.00, 200, ARRAY['dashboard','dedicated_csm','unlimited_projects','api_access','sso','audit_log','custom_integrations','sla_99_9']);

--------------------------------------------------------------------
-- 3. customers (~2000)
--    FK: country_code -> countries
--    industry: SaaS, Finance, Healthcare, Retail, Manufacturing, Media
--------------------------------------------------------------------
CREATE TABLE customers (
    customer_id    SERIAL PRIMARY KEY,
    company_name   TEXT NOT NULL,
    country_code   CHAR(3) NOT NULL REFERENCES countries(country_code),
    industry       TEXT NOT NULL,
    employee_count INT NOT NULL,
    signup_date    DATE NOT NULL,
    account_tier   TEXT NOT NULL,
    description    TEXT NOT NULL
);

-- Build a temp array of country codes for random selection
INSERT INTO customers (company_name, country_code, industry, employee_count, signup_date, account_tier, description)
SELECT
    'Company-' || lpad(g::text, 4, '0'),
    (ARRAY['USA','CAN','MEX','BRA','ARG','GBR','DEU','FRA','NLD','SWE',
           'ESP','ITA','POL','CHE','IRL','IND','JPN','KOR','SGP','AUS',
           'NZL','ISR','ARE','ZAF','NGA','KEN','EGY','COL','CHL','IDN'])[1 + (random()*29)::int],
    (ARRAY['SaaS','Finance','Healthcare','Retail','Manufacturing','Media'])[1 + (random()*5)::int],
    GREATEST(10, (random() * 5000)::int),
    (CURRENT_DATE - (random() * 730)::int),
    (ARRAY['free','growth','enterprise'])[1 + (random()*2)::int],
    'Auto-generated account #' || g || ' for analytics testing.'
FROM generate_series(1, 2000) AS g;

--------------------------------------------------------------------
-- 4. subscriptions (~2500)
--    FK: customer_id -> customers, plan_id -> plans
--    status: active / trial / churned (~15% churned)
--    subscription_period: TSTZRANGE
--    mrr = monthly_price * seats
--------------------------------------------------------------------
CREATE TABLE subscriptions (
    subscription_id    SERIAL PRIMARY KEY,
    customer_id        INT NOT NULL REFERENCES customers(customer_id),
    plan_id            INT NOT NULL REFERENCES plans(plan_id),
    seats              INT NOT NULL,
    mrr                NUMERIC(10,2) NOT NULL,
    status             TEXT NOT NULL CHECK (status IN ('active','trial','churned')),
    subscription_period TSTZRANGE,
    started_at         TIMESTAMPTZ NOT NULL,
    canceled_at        TIMESTAMPTZ
);

INSERT INTO subscriptions (customer_id, plan_id, seats, mrr, status, subscription_period, started_at, canceled_at)
SELECT
    1 + (random() * 1999)::int                             AS customer_id,
    plan_choice                                            AS plan_id,
    seat_count                                             AS seats,
    monthly_price * seat_count                             AS mrr,
    sub_status                                             AS status,
    CASE WHEN sub_status = 'churned'
         THEN tstzrange(start_ts, start_ts + churn_offset)
         ELSE tstzrange(start_ts, NULL)
    END                                                    AS subscription_period,
    start_ts                                               AS started_at,
    CASE WHEN sub_status = 'churned' THEN start_ts + churn_offset ELSE NULL END AS canceled_at
FROM (
    SELECT
        g,
        (ARRAY[1,1,1,2,2,3])[1 + (random()*5)::int]      AS plan_choice,
        GREATEST(1, (random() * 20)::int)                  AS seat_count,
        CASE
            WHEN random() < 0.15 THEN 'churned'
            WHEN random() < 0.12 THEN 'trial'
            ELSE 'active'
        END                                                AS sub_status,
        (now() - (random() * interval '365 days'))         AS start_ts,
        (interval '30 days' + random() * interval '180 days') AS churn_offset
    FROM generate_series(1, 2500) AS g
) sub
JOIN plans p ON p.plan_id = sub.plan_choice;

--------------------------------------------------------------------
-- 5. usage_events (~50000 over 12 months)
--    FK: customer_id -> customers
--    event_type: login, api_call, report_run, export
--------------------------------------------------------------------
CREATE TABLE usage_events (
    event_id     BIGSERIAL PRIMARY KEY,
    customer_id  INT NOT NULL REFERENCES customers(customer_id),
    event_date   DATE NOT NULL,
    event_type   TEXT NOT NULL,
    api_calls    INT NOT NULL DEFAULT 0,
    metadata     JSONB NOT NULL DEFAULT '{}'
);

INSERT INTO usage_events (customer_id, event_date, event_type, api_calls, metadata)
SELECT
    1 + (random() * 1999)::int,
    (CURRENT_DATE - (random() * 365)::int),
    (ARRAY['login','api_call','report_run','export'])[1 + (random()*3)::int],
    (random() * 100)::int,
    jsonb_build_object(
        'duration_ms', (random() * 5000)::int,
        'status',      (ARRAY['ok','warn','error'])[1 + (random()*2)::int],
        'source',      (ARRAY['web','mobile','api','sdk'])[1 + (random()*3)::int],
        'version',     'v' || (1 + (random()*4)::int) || '.' || (random()*9)::int
    )
FROM generate_series(1, 50000);

--------------------------------------------------------------------
-- 6. invoices (one per active/trial subscription per month, 12 months)
--    FK: customer_id -> customers
--    status: paid / pending / overdue
--    revenue = mrr * growth_ramp * seasonality * noise
--------------------------------------------------------------------
CREATE TABLE invoices (
    invoice_id   BIGSERIAL PRIMARY KEY,
    customer_id  INT NOT NULL REFERENCES customers(customer_id),
    amount       NUMERIC(12,2) NOT NULL,
    invoice_date DATE NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('paid','pending','overdue'))
);

INSERT INTO invoices (customer_id, invoice_date, amount, status)
SELECT
    s.customer_id,
    invoice_date,
    ROUND((
        s.mrr
        * (1.0 + 0.025 * m.mi)
        * (1.0 + 0.06 * sin(2 * pi() * (EXTRACT(MONTH FROM invoice_date) - 1) / 12.0))
        * (0.90 + random() * 0.20)
    )::numeric, 2) AS amount,
    CASE
        WHEN random() < 0.85 THEN 'paid'
        WHEN random() < 0.60 THEN 'pending'
        ELSE 'overdue'
    END AS status
FROM subscriptions s
CROSS JOIN LATERAL (
    SELECT
        gs AS mi,
        (CURRENT_DATE - ((12 - gs) * 30))::date AS invoice_date
    FROM generate_series(0, 11) AS gs
) m
WHERE s.status IN ('active','trial');

--------------------------------------------------------------------
-- 7. customer_embeddings (empty; populated later by Cortex EMBED)
--------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE customer_embeddings (
    customer_id INT PRIMARY KEY REFERENCES customers(customer_id),
    embedding   vector(1024)
);

--------------------------------------------------------------------
-- 8. Indexes on FKs and country_code
--------------------------------------------------------------------
CREATE INDEX idx_customers_country       ON customers(country_code);
CREATE INDEX idx_subscriptions_customer  ON subscriptions(customer_id);
CREATE INDEX idx_subscriptions_plan      ON subscriptions(plan_id);
CREATE INDEX idx_usage_events_customer   ON usage_events(customer_id);
CREATE INDEX idx_usage_events_date       ON usage_events(event_date);
CREATE INDEX idx_invoices_customer       ON invoices(customer_id);
CREATE INDEX idx_invoices_date           ON invoices(invoice_date);

COMMIT;
