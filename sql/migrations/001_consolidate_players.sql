-- 001_consolidate_players.sql
--
-- Collapses form_responses / form_responses_2 / puuid into a single players
-- table and remaps elo_history onto it.
--
-- Why: player identity was the pandas row index of the Google Sheet, carried
-- as form_responses.index -> puuid.id -> elo_history.player_id. Deleting or
-- reordering a sheet row silently reassigns every historical scan to the wrong
-- person. players is keyed on the Riot ID (summ_id + player_tag) instead, which
-- is stable regardless of what the sheet does.
--
-- Safe to re-run. Does NOT drop the legacy tables or elo_history.player_id --
-- that happens in 002 once you have confirmed the backfill.

BEGIN;

CREATE TABLE IF NOT EXISTS public.players (
    id            SERIAL PRIMARY KEY,
    summ_id       TEXT NOT NULL,
    player_tag    TEXT NOT NULL,
    region        TEXT,
    puuid         TEXT UNIQUE,
    -- Earliest sheet row index this player was seen under. Audit trail only --
    -- duplicate registrations mean it is NOT a reliable join key (see step 4).
    legacy_id     INTEGER UNIQUE,
    registered_at TIMESTAMP,        -- form submission time
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);

-- Riot IDs are case-insensitive for lookup purposes; store as entered, match folded.
CREATE UNIQUE INDEX IF NOT EXISTS players_riot_id_key
    ON public.players (lower(summ_id), lower(player_tag));


-- 1. Seed from form_responses_2 (current landing table, has puuid).
DO $$
BEGIN
    IF to_regclass('public.form_responses_2') IS NOT NULL THEN
        INSERT INTO public.players (summ_id, player_tag, region, puuid, legacy_id, registered_at)
        SELECT DISTINCT ON (lower(fr.summ_id), lower(fr.player_tag))
               fr.summ_id,
               fr.player_tag,
               fr.region,
               NULLIF(btrim(fr.puuid), ''),
               fr.index,
               fr.timestamp
        FROM public.form_responses_2 fr
        WHERE fr.summ_id IS NOT NULL
          AND btrim(fr.summ_id) <> ''
          AND fr.player_tag IS NOT NULL
        -- earliest submission wins when someone registered twice
        ORDER BY lower(fr.summ_id), lower(fr.player_tag), fr.timestamp NULLS LAST
        ON CONFLICT DO NOTHING;
    END IF;
END $$;


-- 2. Seed anyone who only ever existed in the original form_responses table.
--    No puuid column there; it gets filled in from the legacy puuid table below.
DO $$
BEGIN
    IF to_regclass('public.form_responses') IS NOT NULL THEN
        INSERT INTO public.players (summ_id, player_tag, region, legacy_id, registered_at)
        SELECT DISTINCT ON (lower(fr.summ_id), lower(fr.player_tag))
               fr.summ_id,
               fr.player_tag,
               fr.region,
               fr.index,
               fr.timestamp
        FROM public.form_responses fr
        WHERE fr.summ_id IS NOT NULL
          AND btrim(fr.summ_id) <> ''
          AND fr.player_tag IS NOT NULL
        ORDER BY lower(fr.summ_id), lower(fr.player_tag), fr.timestamp NULLS LAST
        ON CONFLICT DO NOTHING;
    END IF;
END $$;


-- 3. Backfill puuids from the legacy puuid table for players still missing one.
--    Legacy shape is (index, id, puuid) where id == the sheet row index.
DO $$
BEGIN
    IF to_regclass('public.puuid') IS NOT NULL
       AND EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'puuid' AND column_name = 'id'
       )
    THEN
        UPDATE public.players p
        SET    puuid = legacy.puuid
        FROM  (
            SELECT DISTINCT ON (id) id, puuid
            FROM public.puuid
            WHERE puuid IS NOT NULL AND btrim(puuid) <> ''
            ORDER BY id
        ) legacy
        WHERE p.legacy_id = legacy.id
          AND p.puuid IS NULL
          -- do not collide with a puuid already claimed by another row
          AND NOT EXISTS (SELECT 1 FROM public.players x WHERE x.puuid = legacy.puuid);
    END IF;
END $$;


-- 4. Remap elo_history onto players.id.
--    New column rather than an in-place rewrite of player_id, so the old value
--    stays available for auditing until 002 drops it.
--
--    The remap goes through the Riot ID, NOT through players.legacy_id. Someone
--    who filled the form twice has two sheet indexes and scan history under
--    both (Drowsytroll is indexes 7 and 52, with 21 and 8 scans). legacy_id can
--    only hold one of them, so a legacy_id join would silently orphan the rest.
--    Joining on summ_id+player_tag reunites the split history under one player.
ALTER TABLE public.elo_history ADD COLUMN IF NOT EXISTS player_key INTEGER;

DO $$
BEGIN
    IF to_regclass('public.form_responses_2') IS NOT NULL THEN
        UPDATE public.elo_history eh
        SET    player_key = p.id
        FROM   public.form_responses_2 fr
        JOIN   public.players p
               ON lower(p.summ_id)    = lower(fr.summ_id)
              AND lower(p.player_tag) = lower(fr.player_tag)
        WHERE  fr.index = eh.player_id
          AND  eh.player_key IS NULL;
    END IF;
END $$;

-- Fallback for scans whose sheet index only ever existed in the original table.
DO $$
BEGIN
    IF to_regclass('public.form_responses') IS NOT NULL THEN
        UPDATE public.elo_history eh
        SET    player_key = p.id
        FROM   public.form_responses fr
        JOIN   public.players p
               ON lower(p.summ_id)    = lower(fr.summ_id)
              AND lower(p.player_tag) = lower(fr.player_tag)
        WHERE  fr.index = eh.player_id
          AND  eh.player_key IS NULL;
    END IF;
END $$;

-- elo_check.py now writes player_key only. If the legacy player_id column is
-- still NOT NULL (per sql/elo_history.sql) every new insert would fail, so
-- relax it here rather than in 002.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'elo_history'
          AND column_name = 'player_id'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE public.elo_history ALTER COLUMN player_id DROP NOT NULL;
    END IF;
END $$;

-- Same hazard for the old FK pointing at the puuid table: it would reject any
-- row whose player_id is NULL... but more importantly it blocks dropping the
-- puuid table in 002. Remove it now that player_key carries the relationship.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'elo_history_player_id_fkey'
    ) THEN
        ALTER TABLE public.elo_history DROP CONSTRAINT elo_history_player_id_fkey;
    END IF;
END $$;

-- The scan-diffing queries all partition by player + queue ordered by time.
CREATE INDEX IF NOT EXISTS idx_elo_history_player_queue_ts
    ON public.elo_history (player_key, queue_type, timestamp DESC);


-- 5. Attach the foreign key only if every row mapped cleanly. If some rows are
--    orphaned, leave the constraint off and surface the count -- see 001_verify.sql.
DO $$
DECLARE
    orphans BIGINT;
BEGIN
    SELECT count(*) INTO orphans FROM public.elo_history WHERE player_key IS NULL;

    IF orphans = 0 THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'elo_history_player_key_fkey'
        ) THEN
            ALTER TABLE public.elo_history
                ADD CONSTRAINT elo_history_player_key_fkey
                FOREIGN KEY (player_key) REFERENCES public.players (id);
        END IF;
        RAISE NOTICE 'elo_history fully remapped; foreign key attached.';
    ELSE
        RAISE WARNING '% elo_history rows have no matching player. FK not attached -- run 001_verify.sql.', orphans;
    END IF;
END $$;

COMMIT;
