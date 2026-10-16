-- Execute in a dedicated PharmaSentinel database; source text remains local.
CREATE TABLE IF NOT EXISTS passages (
    passage_id VARCHAR(96) PRIMARY KEY,
    source_group VARCHAR(96) NOT NULL,
    split_name VARCHAR(32) NOT NULL,
    original_text LONGTEXT NOT NULL,
    annotation_status VARCHAR(24) NOT NULL,
    character_count INT NOT NULL,
    INDEX idx_passages_split (split_name),
    INDEX idx_passages_source (source_group)
) CHARACTER SET utf8mb4;

CREATE TABLE IF NOT EXISTS experiment_runs (
    run_id VARCHAR(120) PRIMARY KEY,
    model_type VARCHAR(32) NOT NULL,
    configuration_json JSON NOT NULL,
    metrics_json JSON NOT NULL
) CHARACTER SET utf8mb4;

CREATE TABLE IF NOT EXISTS event_records (
    passage_id VARCHAR(96) NOT NULL,
    record_kind VARCHAR(16) NOT NULL,
    run_id VARCHAR(120) NOT NULL,
    event_index INT NOT NULL,
    event_type VARCHAR(48) NOT NULL,
    drug_text TEXT,
    effect_text TEXT,
    evidence_json JSON NOT NULL,
    raw_confidence DOUBLE,
    calibrated_confidence DOUBLE,
    is_correct BOOLEAN,
    PRIMARY KEY (passage_id, record_kind, run_id, event_index),
    FOREIGN KEY (passage_id) REFERENCES passages(passage_id),
    FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id),
    INDEX idx_events_type (event_type),
    INDEX idx_events_run (run_id)
) CHARACTER SET utf8mb4;

