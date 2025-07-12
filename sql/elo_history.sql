-- Create puuid table with primary key
CREATE TABLE IF NOT EXISTS puuid (
    id SERIAL PRIMARY KEY,
    puuid VARCHAR(255) NOT NULL UNIQUE
);

-- Create elo_history table with foreign key reference
CREATE TABLE IF NOT EXISTS elo_history (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL,  -- Reference to puuid table
    queue_type VARCHAR(50) NOT NULL,  -- RANKED_SOLO_5x5 or RANKED_FLEX_SR
    tier VARCHAR(50) NOT NULL,
    rank VARCHAR(10),
    league_points INTEGER NOT NULL,
    wins INTEGER NOT NULL,
    losses INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES puuid(id)
);

-- Create indexes for better query performance
CREATE INDEX idx_elo_history_player_id ON elo_history(player_id);
CREATE INDEX idx_elo_history_queue_type ON elo_history(queue_type);
CREATE INDEX idx_elo_history_timestamp ON elo_history(timestamp);