-- Add timestamp column to elo_history table
ALTER TABLE elo_history 
ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- Update existing records with current timestamp
UPDATE elo_history 
SET timestamp = CURRENT_TIMESTAMP 
WHERE timestamp IS NULL;

-- Add index for timestamp column for better query performance
CREATE INDEX IF NOT EXISTS idx_elo_history_timestamp ON elo_history(timestamp);
