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
)

SELECT 
    jd.summ_id, 
    sq.tier, 
    sq.rank, 
    sq."leaguePoints", 
    sq.wins, 
    sq.losses,
    (sq.wins + sq.losses) AS total_played,
    ROUND(((sq.wins::float / (sq.wins + sq.losses)) * 100)::numeric, 2) AS win_rate,
    sq."hotStreak"
FROM joined_data jd
INNER JOIN public.solo_queue sq
ON jd.puuid = sq.puuid
WHERE jd.puuid IS NOT NULL
ORDER BY win_rate DESC;
