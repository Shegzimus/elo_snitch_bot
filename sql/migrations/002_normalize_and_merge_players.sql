-- 002_normalize_and_merge_players.sql
--
-- Fixes two defects in players that 001 carried over unchanged.
--
-- 1. Legacy rows kept the raw Google Sheet value, which for several players
--    includes a trailing space ("Khanedi " vs "Khanedi"). The old fetch script
--    only ever stripped '#' from the tag, never the summoner name. Once the
--    fetch script started trimming, those players no longer matched their own
--    row and were re-inserted as duplicates.
--
-- 2. Some submissions contain Unicode format characters -- bidi isolates
--    (U+2066/U+2069), zero-width spaces, non-breaking spaces -- pasted in from
--    phone keyboards, and a '#' left inside the tag where it was not the first
--    character. Riot ignores these; the unique index does not.
--
-- Order matters: the unique index has to come off before normalising, or
-- collapsing "Khanedi " to "Khanedi" collides with the existing "Khanedi"
-- mid-statement.
--
-- Safe to re-run.

BEGIN;

-- Normalisation applied here and mirrored in fetch_google_forms_data.py.
CREATE OR REPLACE FUNCTION public.normalize_riot_component(value TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE
AS $$
    SELECT btrim(
        regexp_replace(
            replace(value, '#', ''),
            -- zero-width + bidi format chars + non-breaking space
            '[​-‏⁠-⁩ ]', '', 'g'
        )
    );
$$;


DROP INDEX IF EXISTS public.players_riot_id_key;


-- 1. Merge duplicates that differ only by characters Riot ignores.
--    Keeper: the row that already has a puuid (it owns the scan history),
--    tie-broken by lowest id.
CREATE TEMP TABLE player_merges ON COMMIT DROP AS
WITH normalised AS (
    SELECT id,
           puuid,
           lower(public.normalize_riot_component(summ_id))    AS n_summ,
           lower(public.normalize_riot_component(player_tag)) AS n_tag
    FROM public.players
),
ranked AS (
    SELECT id, puuid, n_summ, n_tag,
           first_value(id) OVER (
               PARTITION BY n_summ, n_tag
               ORDER BY (puuid IS NOT NULL) DESC, id
           ) AS keeper_id
    FROM normalised
)
SELECT id AS duplicate_id, keeper_id
FROM ranked
WHERE id <> keeper_id;

-- Carry a puuid over if the keeper somehow lacks one.
UPDATE public.players k
SET    puuid = d.puuid
FROM   player_merges m
JOIN   public.players d ON d.id = m.duplicate_id
WHERE  k.id = m.keeper_id
  AND  k.puuid IS NULL
  AND  d.puuid IS NOT NULL;

-- Move any scan history off the duplicate before deleting it.
UPDATE public.elo_history eh
SET    player_key = m.keeper_id
FROM   player_merges m
WHERE  eh.player_key = m.duplicate_id;

DELETE FROM public.players p
USING  player_merges m
WHERE  p.id = m.duplicate_id;


-- 2. Normalise what remains.
UPDATE public.players
SET    summ_id    = public.normalize_riot_component(summ_id),
       player_tag = public.normalize_riot_component(player_tag)
WHERE  summ_id    <> public.normalize_riot_component(summ_id)
   OR  player_tag <> public.normalize_riot_component(player_tag);

-- Registrations that normalise to nothing usable cannot be looked up.
DELETE FROM public.players
WHERE (summ_id IS NULL OR btrim(summ_id) = '' OR player_tag IS NULL OR btrim(player_tag) = '')
  AND NOT EXISTS (SELECT 1 FROM public.elo_history eh WHERE eh.player_key = players.id);


-- 3. Re-assert uniqueness on the cleaned values.
CREATE UNIQUE INDEX players_riot_id_key
    ON public.players (lower(summ_id), lower(player_tag));

COMMIT;
