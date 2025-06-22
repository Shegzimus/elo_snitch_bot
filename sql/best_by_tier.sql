WITH joined_data AS (
    SELECT 
        form_responses.index AS id, 
        form_responses.summ_id, 
        public.puuid.puuid
    FROM 
        public.form_responses
    LEFT JOIN 
        public.puuid 
    ON 
        form_responses.index = public.puuid.id
),
ranked_players AS (
    SELECT 
        jd.summ_id,
        sq.tier,
        sq.rank,
        sq."leaguePoints",
        sq.wins,
        sq.losses,
        (sq.wins + sq.losses) AS total_played,
        ROUND(((sq.wins::float / (sq.wins + sq.losses)) * 100)::numeric, 2) AS win_rate,
        sq."hotStreak",
        ROW_NUMBER() OVER (PARTITION BY sq.tier ORDER BY 
            ROUND(((sq.wins::float / (sq.wins + sq.losses)) * 100)::numeric, 2) DESC,
            sq."leaguePoints" DESC
        ) AS rn
    FROM joined_data jd
    INNER JOIN public.solo_queue sq
    ON jd.puuid = sq.puuid
    WHERE jd.puuid IS NOT NULL
)
SELECT 
    summ_id, 
    tier, 
    rank, 
    "leaguePoints", 
    wins, 
    losses,
    total_played,
    win_rate,
    "hotStreak"
FROM ranked_players
WHERE rn = 1
ORDER BY win_rate DESC;