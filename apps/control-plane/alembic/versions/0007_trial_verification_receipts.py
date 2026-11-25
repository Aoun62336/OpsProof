"""Bind independent verification receipts to the original dispatch identity."""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE m6_trial_artifacts ADD COLUMN observations jsonb NOT NULL DEFAULT '{}'::jsonb
      CHECK (jsonb_typeof(observations)='object' AND octet_length(observations::text)<=65536);
    CREATE TABLE m6_trial_verifications (
      id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      trial_id uuid NOT NULL REFERENCES m6_trials(id),
      dispatch_id uuid NOT NULL,
      observer_id uuid NOT NULL UNIQUE,
      target_uid text NOT NULL,
      report_sha256 char(64) NOT NULL CHECK (report_sha256 ~ '^[a-f0-9]{64}$'),
      observer_sha256 char(64) NOT NULL CHECK (observer_sha256 ~ '^[a-f0-9]{64}$'),
      verified_at timestamptz NOT NULL,
      cleanup_verified boolean NOT NULL CHECK (cleanup_verified),
      hypothesis_verified boolean NOT NULL,
      report jsonb NOT NULL,
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
    );
    CREATE INDEX ix_m6_verifications_trial
      ON m6_trial_verifications(trial_id,verified_at DESC,id DESC);
    CREATE TRIGGER m6_verifications_append_only
      BEFORE UPDATE OR DELETE ON m6_trial_verifications
      FOR EACH ROW EXECUTE FUNCTION m6_reject_event_mutation();
    CREATE TRIGGER m6_artifacts_append_only
      BEFORE UPDATE OR DELETE ON m6_trial_artifacts
      FOR EACH ROW EXECUTE FUNCTION m6_reject_event_mutation();
    CREATE FUNCTION m6_protect_dispatch_identity() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.dispatch_id IS NOT NULL AND
        (OLD.dispatch_id,OLD.dispatch_intent_at,OLD.target_uid,OLD.target_version)
        IS DISTINCT FROM
        (NEW.dispatch_id,NEW.dispatch_intent_at,NEW.target_uid,NEW.target_version) THEN
        RAISE EXCEPTION 'M6 committed dispatch identity is immutable';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER m6_dispatch_immutable BEFORE UPDATE ON m6_trials
      FOR EACH ROW EXECUTE FUNCTION m6_protect_dispatch_identity();
    CREATE FUNCTION m6_protect_reservation_release() RETURNS trigger
    LANGUAGE plpgsql AS $$
    DECLARE trial m6_trials%ROWTYPE;
    BEGIN
      SELECT * INTO STRICT trial FROM m6_trials WHERE id=OLD.trial_id;
      IF trial.dispatch_id IS NULL AND trial.phase IN ('aborted','failed') THEN
        RETURN OLD;
      END IF;
      IF EXISTS (SELECT 1 FROM m6_trial_verifications v
         WHERE v.trial_id=trial.id AND v.dispatch_id=trial.dispatch_id
           AND v.target_uid=trial.target_uid AND v.cleanup_verified) THEN
        RETURN OLD;
      END IF;
      RAISE EXCEPTION
        'M6 reservation release requires terminal uninjected state or independent cleanup';
    END $$;
    CREATE TRIGGER m6_target_release_guard BEFORE DELETE ON m6_target_leases
      FOR EACH ROW EXECUTE FUNCTION m6_protect_reservation_release();
    CREATE TRIGGER m6_scope_release_guard BEFORE DELETE ON m6_execution_leases
      FOR EACH ROW EXECUTE FUNCTION m6_protect_reservation_release();
    """)


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM m6_target_leases) THEN
        RAISE EXCEPTION 'Cannot remove verification safeguards with unresolved trials';
      END IF;
    END $$""")
    op.execute("DROP TRIGGER m6_dispatch_immutable ON m6_trials")
    op.execute("DROP FUNCTION m6_protect_dispatch_identity()")
    op.execute("DROP TRIGGER m6_artifacts_append_only ON m6_trial_artifacts")
    op.execute("DROP TRIGGER m6_target_release_guard ON m6_target_leases")
    op.execute("DROP TRIGGER m6_scope_release_guard ON m6_execution_leases")
    op.execute("DROP FUNCTION m6_protect_reservation_release()")
    op.execute("DROP TABLE m6_trial_verifications")
    op.execute("ALTER TABLE m6_trial_artifacts DROP COLUMN observations")
