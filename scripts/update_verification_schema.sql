-- Update verification schema to support threshold-based decision metrics
-- This enables calculation of CSI, hit rate, false alarm rate, etc.

-- Create threshold_verification table for decision metrics
CREATE TABLE IF NOT EXISTS threshold_verification (
    id SERIAL PRIMARY KEY,
    verification_score_id INTEGER REFERENCES verification_scores(id) ON DELETE CASCADE,
    threshold_value FLOAT NOT NULL,
    threshold_operator VARCHAR(10) NOT NULL DEFAULT '>',  -- '>', '<', '>=', '<='
    forecast_exceeds BOOLEAN NOT NULL,
    observed_exceeds BOOLEAN NOT NULL,
    outcome VARCHAR(20) NOT NULL,  -- 'hit', 'miss', 'false_alarm', 'correct_negative'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_threshold_outcome ON threshold_verification(outcome, threshold_value);
CREATE INDEX IF NOT EXISTS idx_threshold_model ON threshold_verification(verification_score_id);
CREATE INDEX IF NOT EXISTS idx_threshold_value ON threshold_verification(threshold_value, outcome);

-- Add comment
COMMENT ON TABLE threshold_verification IS 'Decision-relevant threshold verification results for operational forecast value assessment';
COMMENT ON COLUMN threshold_verification.outcome IS 'hit|miss|false_alarm|correct_negative - contingency table outcome';
COMMENT ON COLUMN threshold_verification.threshold_value IS 'Decision threshold value (e.g., 0.0 for freezing in Celsius)';

-- Create materialized view for quick skill metric queries
CREATE MATERIALIZED VIEW IF NOT EXISTS skill_metrics_summary AS
SELECT
    vs.model_name,
    vs.variable,
    vs.lead_time_hours,
    tv.threshold_value,
    COUNT(*) FILTER (WHERE tv.outcome = 'hit') as hits,
    COUNT(*) FILTER (WHERE tv.outcome = 'miss') as misses,
    COUNT(*) FILTER (WHERE tv.outcome = 'false_alarm') as false_alarms,
    COUNT(*) FILTER (WHERE tv.outcome = 'correct_negative') as correct_negatives,
    COUNT(*) as total_pairs,
    -- Statistical metrics
    AVG(vs.absolute_error) as mae,
    SQRT(AVG(vs.squared_error)) as rmse,
    AVG(vs.error) as bias,
    -- Decision metrics
    COUNT(*) FILTER (WHERE tv.outcome = 'hit')::FLOAT /
        NULLIF(COUNT(*) FILTER (WHERE tv.outcome IN ('hit', 'miss')), 0) as hit_rate,
    COUNT(*) FILTER (WHERE tv.outcome = 'false_alarm')::FLOAT /
        NULLIF(COUNT(*) FILTER (WHERE tv.outcome IN ('false_alarm', 'correct_negative')), 0) as false_alarm_rate,
    COUNT(*) FILTER (WHERE tv.outcome = 'false_alarm')::FLOAT /
        NULLIF(COUNT(*) FILTER (WHERE tv.outcome IN ('false_alarm', 'hit')), 0) as false_alarm_ratio,
    COUNT(*) FILTER (WHERE tv.outcome = 'hit')::FLOAT /
        NULLIF(COUNT(*) FILTER (WHERE tv.outcome IN ('hit', 'miss', 'false_alarm')), 0) as csi,
    (COUNT(*) FILTER (WHERE tv.outcome IN ('hit', 'correct_negative')))::FLOAT /
        NULLIF(COUNT(*), 0) as accuracy,
    DATE_TRUNC('day', vs.created_at) as verification_date
FROM verification_scores vs
JOIN threshold_verification tv ON tv.verification_score_id = vs.id
GROUP BY
    vs.model_name,
    vs.variable,
    vs.lead_time_hours,
    tv.threshold_value,
    DATE_TRUNC('day', vs.created_at);

CREATE INDEX IF NOT EXISTS idx_skill_model_var ON skill_metrics_summary(model_name, variable);
CREATE INDEX IF NOT EXISTS idx_skill_threshold ON skill_metrics_summary(threshold_value);
CREATE INDEX IF NOT EXISTS idx_skill_date ON skill_metrics_summary(verification_date);

COMMENT ON MATERIALIZED VIEW skill_metrics_summary IS 'Aggregated skill metrics for model selection - refresh after batch verification runs';
