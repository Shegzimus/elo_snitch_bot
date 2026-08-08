-- 001_verify.sql
-- Read-only checks to run after 001_consolidate_players.sql.
-- Every result here should be empty or zero before you run 002.

\echo '--- players created ---'
SELECT count(*) AS players,
       count(puuid) AS with_puuid,
       count(*) - count(puuid) AS missing_puuid
FROM public.players;

\echo '--- elo_history remap coverage ---'
SELECT count(*) AS total_scans,
       count(player_key) AS remapped,
       count(*) - count(player_key) AS orphaned
FROM public.elo_history;

\echo '--- orphaned scans: legacy player_ids with no players row (expect 0 rows) ---'
SELECT eh.player_id AS legacy_player_id,
       count(*) AS scan_count,
       min(eh.timestamp) AS first_seen,
       max(eh.timestamp) AS last_seen
FROM public.elo_history eh
WHERE eh.player_key IS NULL
GROUP BY eh.player_id
ORDER BY scan_count DESC;

\echo '--- duplicate Riot IDs that collapsed into one player (informational) ---'
SELECT p.id, p.summ_id, p.player_tag, p.legacy_id, p.puuid IS NOT NULL AS has_puuid
FROM public.players p
ORDER BY p.legacy_id NULLS LAST;

\echo '--- sanity: scan counts per player before vs after remap (deltas expect 0) ---'
SELECT p.summ_id,
       p.player_tag,
       count(eh.*) AS scans_after_remap
FROM public.players p
LEFT JOIN public.elo_history eh ON eh.player_key = p.id
GROUP BY p.id, p.summ_id, p.player_tag
ORDER BY scans_after_remap DESC;
