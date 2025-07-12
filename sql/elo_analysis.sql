-- Get ELO changes over time for a player
SELECT timestamp, tier, rank, league_points 
FROM elo_history 
WHERE player_id = ? 
ORDER BY timestamp;

-- Get average ELO points per day
SELECT 
    DATE(timestamp) as date,
    AVG(league_points) as avg_points
FROM elo_history
GROUP BY DATE(timestamp)
ORDER BY date;

-- Get number of players in each tier over time
SELECT 
    timestamp,
    tier,
    COUNT(*) as player_count
FROM elo_history
GROUP BY timestamp, tier
ORDER BY timestamp;