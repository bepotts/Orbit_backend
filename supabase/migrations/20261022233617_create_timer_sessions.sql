-- TimerSession snapshots, owned by Supabase Auth users.
CREATE TABLE "public"."timer_sessions" (
  "id"                     uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "session_label"          text                     NOT NULL DEFAULT ''::text,
  "phase"                  text                     NOT NULL DEFAULT 'idle'::text,
  "duration_seconds"       double precision         NOT NULL DEFAULT 1800,
  "total_duration_seconds" double precision         NOT NULL DEFAULT 1800,
  "remaining_seconds"      double precision         NOT NULL DEFAULT 1800,
  "end_date"               timestamp with time zone,
  "captured_at"            timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT "timer_sessions_captured_at_finite_check" CHECK (isfinite(captured_at)),
  CONSTRAINT "timer_sessions_complete_check" CHECK (((phase <> 'complete'::text) OR (remaining_seconds = (0)::double precision))),
  CONSTRAINT "timer_sessions_duration_check" CHECK (((duration_seconds >= (0)::double precision) AND (duration_seconds <= (6039)::double precision))),
  CONSTRAINT "timer_sessions_end_date_finite_check" CHECK (((end_date IS NULL) OR isfinite(end_date))),
  CONSTRAINT "timer_sessions_phase_check" CHECK ((phase = ANY (ARRAY['idle'::text, 'running'::text, 'paused'::text, 'complete'::text]))),
  CONSTRAINT "timer_sessions_pkey" PRIMARY KEY (id),
  CONSTRAINT "timer_sessions_remaining_check" CHECK (((remaining_seconds >= (0)::double precision) AND (remaining_seconds <= (6039)::double precision))),
  CONSTRAINT "timer_sessions_remaining_total_check" CHECK ((remaining_seconds <= total_duration_seconds)),
  CONSTRAINT "timer_sessions_running_deadline_check" CHECK (((phase <> 'running'::text) OR (end_date IS NOT NULL))),
  CONSTRAINT "timer_sessions_total_duration_check" CHECK (((total_duration_seconds >= (0)::double precision) AND (total_duration_seconds <= (6039)::double precision))),
  "user_id"                uuid                     NOT NULL DEFAULT auth.uid()
);

ALTER TABLE "public"."timer_sessions"
  ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "public"."timer_sessions" FROM "anon";

COMMENT ON COLUMN "public"."timer_sessions"."captured_at" IS 'Time the client captured this snapshot, not the server insertion time.';

COMMENT ON COLUMN "public"."timer_sessions"."end_date" IS 'Authoritative wall-clock deadline only while the timer is running.';

COMMENT ON TABLE "public"."timer_sessions" IS 'User-owned snapshots of the Orbit timer; durations are fractional seconds.';

REVOKE ALL ON TABLE "public"."timer_sessions" FROM "authenticated";

GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE "public"."timer_sessions" TO "authenticated";

REVOKE ALL ON TABLE "public"."timer_sessions" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."timer_sessions" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."timer_sessions" TO "service_role";

ALTER TABLE "public"."timer_sessions"
  ADD CONSTRAINT "timer_sessions_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE INDEX timer_sessions_user_captured_idx ON public.timer_sessions USING btree (user_id, captured_at DESC);

CREATE POLICY "timer_sessions_delete_own" ON "public"."timer_sessions"
  FOR DELETE
  TO "authenticated"
  USING ((( SELECT auth.uid() AS uid) = user_id));

CREATE POLICY "timer_sessions_insert_own" ON "public"."timer_sessions"
  FOR INSERT
  TO "authenticated"
  WITH CHECK ((( SELECT auth.uid() AS uid) = user_id));

CREATE POLICY "timer_sessions_select_own" ON "public"."timer_sessions"
  FOR SELECT
  TO "authenticated"
  USING ((( SELECT auth.uid() AS uid) = user_id));

CREATE POLICY "timer_sessions_update_own" ON "public"."timer_sessions"
  FOR UPDATE
  TO "authenticated"
  USING ((( SELECT auth.uid() AS uid) = user_id))
  WITH CHECK ((( SELECT auth.uid() AS uid) = user_id));

COMMENT ON COLUMN "public"."timer_sessions"."user_id" IS 'Supabase Auth UID corresponding to UserProfile.id.';


-- Explicitly remove any PUBLIC privileges inherited from deployment defaults.
REVOKE ALL ON TABLE public.timer_sessions FROM PUBLIC;
