SELECT 
	player_id,
	queue_type,
	tier,
	rank,
	league_points,
	wins,
	losses,
	timestamp,
	ROW_NUMBER() OVER (PARTITION BY player_id, queue_type ORDER BY timestamp DESC) as scan_number
FROM elo_history