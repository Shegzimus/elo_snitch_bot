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
    fq.tier, 
    fq.rank, 
    fq."leaguePoints", 
    fq.wins, 
    fq.losses,
    (fq.wins + fq.losses) AS total_played,
    ROUND(((fq.wins::float / (fq.wins + fq.losses)) * 100)::numeric, 2) AS win_rate,
    fq."hotStreak"
FROM joined_data jd
INNER JOIN public.flex_queue fq
ON jd.puuid = fq.puuid
WHERE jd.puuid IS NOT NULL
ORDER BY win_rate DESC;
