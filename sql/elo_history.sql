CREATE TABLE elo_history (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,  -- Reference to puuid table
    queue_type VARCHAR(50) NOT NULL,  -- RANKED_SOLO_5x5 or RANKED_FLEX_SR
    tier VARCHAR(50) NOT NULL,
    rank VARCHAR(10),
    league_points INTEGER NOT NULL,
    wins INTEGER NOT NULL,
    losses INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES puuid(id)
);