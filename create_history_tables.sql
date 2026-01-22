-- Professional Analysis History Schema
-- Based on industry best practices (Power BI, Tableau, MLflow)

-- Table 1: datasets
-- Tracks all uploaded files with metadata
CREATE TABLE IF NOT EXISTS datasets (
    id SERIAL PRIMARY KEY,
    original_filename VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL UNIQUE,
    file_hash VARCHAR(64) NOT NULL,
    file_size_bytes BIGINT,
    rows_count INTEGER,
    columns_count INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for datasets table
CREATE INDEX IF NOT EXISTS idx_datasets_table_name ON datasets(table_name);
CREATE INDEX IF NOT EXISTS idx_datasets_file_hash ON datasets(file_hash);
CREATE INDEX IF NOT EXISTS idx_datasets_uploaded_at ON datasets(uploaded_at);

-- Table 2: analysis_history
-- Tracks all analysis runs with config and results
CREATE TABLE IF NOT EXISTS analysis_history (
    id SERIAL PRIMARY KEY,
    dataset_id INTEGER NOT NULL,
    config_json JSONB NOT NULL,
    config_hash VARCHAR(64) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, completed, failed
    execution_time_ms INTEGER,
    result_preview JSONB,  -- Store summary/preview only
    result_row_count INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Foreign key to datasets
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
);

-- Indexes for analysis_history table
CREATE INDEX IF NOT EXISTS idx_analysis_dataset ON analysis_history(dataset_id);
CREATE INDEX IF NOT EXISTS idx_analysis_config_hash ON analysis_history(config_hash);
CREATE INDEX IF NOT EXISTS idx_analysis_status ON analysis_history(status);
CREATE INDEX IF NOT EXISTS idx_analysis_created_at ON analysis_history(created_at);

-- Comments for documentation
COMMENT ON TABLE datasets IS 'Stores metadata for all uploaded files';
COMMENT ON TABLE analysis_history IS 'Tracks all analysis runs with config and results';
COMMENT ON COLUMN analysis_history.config_json IS 'Complete analysis configuration as JSON';
COMMENT ON COLUMN analysis_history.config_hash IS 'SHA256 hash of config for caching';
COMMENT ON COLUMN analysis_history.result_preview IS 'Preview of results (first 100 rows max)';
