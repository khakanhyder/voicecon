-- Put one user's workspace on the Voice AI plan at no charge (a "manual" subscription).
-- Mirrors POST /api/v1/admin/organizations/{id}/grant-plan, minus the admin audit row.
--
-- Usage from Dokploy: open the Postgres service -> Terminal, then
--   psql -U <POSTGRES_USER> -d <POSTGRES_DB>
-- and paste this whole file. Change the two values below first.

\set target_email 'asadhackerasad@gmail.com'
\set target_plan  'voice-ai'

BEGIN;
SELECT set_config('grant.email', :'target_email', true), set_config('grant.plan', :'target_plan', true);

-- 1) Show what we are about to change.
SELECT u.email, o.id AS org_id, o.name AS org, s.id AS sub_id, s.status, s.source,
       p.slug AS plan, s.trial_end, s.current_period_end
FROM users u
JOIN organizations o
  ON o.id = COALESCE(u.active_organization_id,
                     (SELECT id FROM organizations WHERE owner_id = u.id ORDER BY created_at LIMIT 1))
LEFT JOIN subscriptions s ON s.organization_id = o.id
LEFT JOIN subscription_plans p ON p.id = s.plan_id
WHERE lower(u.email) = lower(:'target_email')
ORDER BY s.created_at DESC NULLS LAST;

-- 2) Apply the plan.
DO $$
DECLARE
  v_email   text := current_setting('grant.email');
  v_slug    text := current_setting('grant.plan');
  v_user_id uuid;
  v_org_id  uuid;
  v_plan_id uuid;
  v_sub     subscriptions%ROWTYPE;
  v_now     timestamp := (now() AT TIME ZONE 'utc');
BEGIN
  SELECT id, COALESCE(active_organization_id,
                      (SELECT id FROM organizations WHERE owner_id = users.id ORDER BY created_at LIMIT 1))
    INTO v_user_id, v_org_id
  FROM users WHERE lower(email) = lower(v_email) AND deleted_at IS NULL;
  IF v_user_id IS NULL THEN RAISE EXCEPTION 'No user with email %', v_email; END IF;
  IF v_org_id  IS NULL THEN RAISE EXCEPTION 'User % owns no organization', v_email; END IF;

  SELECT id INTO v_plan_id FROM subscription_plans WHERE slug = v_slug AND is_active;
  IF v_plan_id IS NULL THEN RAISE EXCEPTION 'No active plan with slug %', v_slug; END IF;

  -- The org's one live subscription, if any (same rule as the app's partial unique index).
  SELECT * INTO v_sub FROM subscriptions
   WHERE organization_id = v_org_id
     AND status IN ('trialing','active','past_due','grace')
   ORDER BY created_at DESC LIMIT 1;

  IF v_sub.id IS NOT NULL AND v_sub.source IN ('stripe','polar') THEN
    RAISE EXCEPTION 'Org % pays through %. Change it in that provider instead.', v_org_id, v_sub.source;
  END IF;

  IF v_sub.id IS NOT NULL THEN
    UPDATE subscriptions SET
      plan_id              = v_plan_id,
      source               = 'manual',
      status               = 'active',
      current_period_start = v_now,
      current_period_end   = v_now + interval '30 days',
      grace_period_end     = NULL,
      expired_at           = NULL,
      cancel_at_period_end = false,
      scheduled_plan_id    = NULL,
      trial_converted_at   = CASE WHEN v_sub.source = 'trial' THEN v_now ELSE trial_converted_at END,
      updated_at           = v_now
    WHERE id = v_sub.id;
    RAISE NOTICE 'Updated live subscription % (was % / % )', v_sub.id, v_sub.status, v_sub.source;
  ELSE
    INSERT INTO subscriptions (id, organization_id, plan_id, status, billing_period, source,
      current_period_start, current_period_end, cancel_at_period_end,
      current_period_minutes, current_period_calls, current_period_sms, current_period_emails,
      stripe_metadata, created_at, updated_at)
    VALUES (gen_random_uuid(), v_org_id, v_plan_id, 'active', 'monthly', 'manual',
      v_now, v_now + interval '30 days', false, 0, 0, 0, 0, '{}'::json, v_now, v_now)
    RETURNING * INTO v_sub;
    RAISE NOTICE 'Created new manual subscription %', v_sub.id;
  END IF;

  -- Ledger entry so the admin console's history explains this state.
  INSERT INTO subscription_events (id, organization_id, subscription_id, event_type,
    from_status, to_status, from_plan_id, to_plan_id, actor_type, actor_id, payload, created_at)
  VALUES (gen_random_uuid(), v_org_id, v_sub.id, 'activated',
    v_sub.status, 'active', v_sub.plan_id, v_plan_id, 'admin', NULL,
    json_build_object('reason', 'Granted via SQL for testing', 'comp', true), v_now);
END $$;

-- 3) Verify.
SELECT u.email, o.name AS org, s.status, s.source, p.slug AS plan,
       s.current_period_start, s.current_period_end, s.trial_converted_at
FROM users u
JOIN organizations o
  ON o.id = COALESCE(u.active_organization_id,
                     (SELECT id FROM organizations WHERE owner_id = u.id ORDER BY created_at LIMIT 1))
JOIN subscriptions s ON s.organization_id = o.id
JOIN subscription_plans p ON p.id = s.plan_id
WHERE lower(u.email) = lower(:'target_email')
ORDER BY s.created_at DESC;

COMMIT;
