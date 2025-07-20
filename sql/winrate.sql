WITH latest_scans AS (
    SELECT 
        fr.summ_id,
        eh.queue_type,
        eh.tier,
        eh.rank,
        eh.league_points,
        eh.wins,
        eh.losses,
        eh.timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY fr.summ_id, eh.queue_type 
            ORDER BY eh.timestamp DESC
        ) AS scan_number
    FROM public.elo_history eh
    JOIN public.form_responses fr 
        ON eh.player_id = fr.index
),
filtered_scans AS (
    SELECT *
    FROM latest_scans
    WHERE scan_number = 1
)
SELECT 
    summ_id,
    queue_type,
    tier,
    rank,
    league_points,
    wins,
    losses,
    (wins + losses) AS total_games,
   	ROUND(((wins::numeric / NULLIF(wins + losses, 0)) * 100)::numeric, 2) AS win_rate,
    timestamp
FROM filtered_scans
ORDER BY win_rate DESC;
