"""Create the independent trial ledger and evidence constraints."""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE m6_trials (
        id uuid PRIMARY KEY,
        request_key text NOT NULL UNIQUE,
        request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
        scenario text NOT NULL CHECK (scenario IN (
          'worker_saturation','faulty_release','database_connectivity',
          'worker_failure','downstream_latency','misleading_evidence')),
        target text NOT NULL,
        phase text NOT NULL DEFAULT 'requested' CHECK (phase IN (
          'requested','preflight','armed','injected','observing',
          'recovering','verifying','succeeded','failed','aborted','indeterminate')),
        approved_test_scope boolean NOT NULL DEFAULT false,
        cleanup_plan_confirmed boolean NOT NULL DEFAULT false,
        injection_acknowledged boolean NOT NULL DEFAULT false,
        independent_verified boolean NOT NULL DEFAULT false,
        cleanup_verified boolean NOT NULL DEFAULT false,
        abort_requested boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        approved_at timestamptz,
        approval_expires_at timestamptz,
        dispatch_id uuid UNIQUE,
        dispatch_intent_at timestamptz,
        dispatch_deadline timestamptz,
        target_uid text,
        target_version text,
        completed_at timestamptz,
        source_revision text NOT NULL CHECK (length(source_revision) BETWEEN 7 AND 64),
        error text,
        CONSTRAINT m6_success_requires_proof CHECK (
          phase <> 'succeeded' OR
          (injection_acknowledged AND independent_verified AND cleanup_verified)),
        CONSTRAINT m6_terminal_failure_requires_cleanup CHECK (
          phase NOT IN ('failed','aborted') OR dispatch_intent_at IS NULL OR cleanup_verified),
        CONSTRAINT m6_dispatch_identity CHECK (
          (dispatch_id IS NULL AND dispatch_intent_at IS NULL AND dispatch_deadline IS NULL)
          OR (dispatch_id IS NOT NULL AND dispatch_intent_at IS NOT NULL
              AND dispatch_deadline > dispatch_intent_at
              AND target_uid IS NOT NULL AND target_version IS NOT NULL)),
        CONSTRAINT m6_receipt_requires_dispatch CHECK (
          NOT injection_acknowledged OR dispatch_intent_at IS NOT NULL),
        CONSTRAINT m6_armed_requires_approval CHECK (
          phase NOT IN ('armed','injected','observing','recovering','verifying','succeeded') OR
          (approved_test_scope AND cleanup_plan_confirmed))
    );
    -- One active trial per exact target, including unapproved requests.
    -- Do not silently release uncertain injected trials on a timer.
    CREATE UNIQUE INDEX ux_m6_active_target ON m6_trials (target)
      WHERE phase IN ('requested','preflight','armed','injected',
                      'observing','recovering','verifying');
    CREATE INDEX ix_m6_trials_created ON m6_trials (created_at DESC);

    CREATE TABLE m6_trial_events (
       id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
       trial_id uuid NOT NULL REFERENCES m6_trials(id),
       kind text NOT NULL,
       details jsonb NOT NULL DEFAULT '{}'::jsonb,
       created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_m6_trial_events ON m6_trial_events(trial_id,id);
    -- Event rows are append-only for the normal application DB role.
    -- A database owner can still change this function, so this is not
    -- cryptographically tamper-proof evidence.
    CREATE FUNCTION m6_reject_event_mutation() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'M6 audit events are append-only';
    END
    $$;
    CREATE TRIGGER m6_events_append_only
      BEFORE UPDATE OR DELETE ON m6_trial_events
      FOR EACH ROW EXECUTE FUNCTION m6_reject_event_mutation();

    CREATE FUNCTION m6_protect_terminal_trial() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.phase IN ('succeeded','failed','aborted','indeterminate') THEN
        RAISE EXCEPTION 'M6 terminal trials are immutable';
      END IF;
      IF TG_OP = 'UPDATE' AND
        (OLD.id,OLD.request_key,OLD.request_hash,OLD.scenario,OLD.target,OLD.source_revision)
        IS DISTINCT FROM
        (NEW.id,NEW.request_key,NEW.request_hash,NEW.scenario,NEW.target,NEW.source_revision) THEN
        RAISE EXCEPTION 'M6 trial intent identity is immutable';
      END IF;
      RETURN NEW;
    END
    $$;
    CREATE TRIGGER m6_terminal_immutable BEFORE UPDATE OR DELETE ON m6_trials
      FOR EACH ROW EXECUTE FUNCTION m6_protect_terminal_trial();

    CREATE TABLE m6_target_leases (
       target text PRIMARY KEY,
       trial_id uuid NOT NULL UNIQUE REFERENCES m6_trials(id),
       fence_token uuid NOT NULL,
       created_at timestamptz NOT NULL DEFAULT now(),
       updated_at timestamptz NOT NULL DEFAULT now()
    );
    -- A persistent reservation, not a self-expiring permission to re-inject.
    CREATE TABLE m6_execution_leases (
       scope text PRIMARY KEY CHECK (scope='k3d-opsproof'),
       trial_id uuid NOT NULL UNIQUE REFERENCES m6_trials(id)
    );
    -- The six scenarios share a demo environment. Distinct resource names do
    -- not make simultaneous DB, release and worker faults independent.

    CREATE TABLE m6_trial_outbox (
       id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
       trial_id uuid NOT NULL REFERENCES m6_trials(id),
       event_type text NOT NULL CHECK (event_type IN ('preflight_requested','abort_requested')),
       dispatched_at timestamptz,
       created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_m6_outbox_pending ON m6_trial_outbox (id)
       WHERE dispatched_at IS NULL;

    CREATE TABLE m6_trial_artifacts (
       id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
       trial_id uuid NOT NULL REFERENCES m6_trials(id),
       kind text NOT NULL,
       relative_path text NOT NULL,
       sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
       created_at timestamptz NOT NULL DEFAULT now(),
       UNIQUE(trial_id,relative_path)
    );
    CREATE TABLE m6_trial_resolutions (
       trial_id uuid PRIMARY KEY REFERENCES m6_trials(id),
       reason text NOT NULL,
       created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TRIGGER m6_resolutions_append_only
      BEFORE UPDATE OR DELETE ON m6_trial_resolutions
      FOR EACH ROW EXECUTE FUNCTION m6_reject_event_mutation();
    CREATE TABLE m6_reuse_observations (
       id uuid PRIMARY KEY,
       target text NOT NULL CHECK (target='opsproof-reuse-test'),
       observed_at timestamptz NOT NULL,
       observations jsonb NOT NULL,
       finding jsonb NOT NULL
    );
    """)


def downgrade() -> None:
    # Deliberately explicit. Never downgrade during active or uncertain trials.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM m6_target_leases)
         OR EXISTS (SELECT 1 FROM m6_trials WHERE phase IN
           ('requested','preflight','armed','injected','observing','recovering','verifying')) THEN
        RAISE EXCEPTION 'Cannot downgrade with active or unresolved M6 trials';
      END IF;
    END $$""")
    op.execute("DROP TABLE m6_trial_resolutions")
    op.execute("DROP TABLE m6_reuse_observations")
    op.execute("DROP TABLE m6_trial_artifacts")
    op.execute("DROP TABLE m6_trial_outbox")
    op.execute("DROP TABLE m6_execution_leases")
    op.execute("DROP TABLE m6_target_leases")
    op.execute("DROP TABLE m6_trial_events")
    op.execute("DROP FUNCTION m6_reject_event_mutation()")
    op.execute("DROP TABLE m6_trials")
    op.execute("DROP FUNCTION m6_protect_terminal_trial()")
