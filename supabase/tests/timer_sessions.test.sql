-- Transactional fixtures: no users or timer data survive this test suite.
begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select no_plan();

insert into auth.users (id, email) values
    ('10000000-0000-0000-0000-000000000001', 'timer-owner@example.com'),
    ('10000000-0000-0000-0000-000000000002', 'timer-other@example.com');
insert into public.timer_sessions (id, user_id) values
    ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001'),
    ('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002');

select has_table('public', 'timer_sessions', 'Timer sessions table exists');
select col_type_is('public', 'timer_sessions', 'duration_seconds', 'double precision', 'Fractional seconds use double precision');
select col_type_is('public', 'timer_sessions', 'captured_at', 'timestamp with time zone', 'Capture time is timezone aware');
select ok((select relrowsecurity from pg_class where oid = 'public.timer_sessions'::regclass), 'RLS is enabled');
select ok(not has_table_privilege('authenticated', 'public.timer_sessions', 'TRUNCATE'), 'Clients cannot bypass RLS with TRUNCATE');

set local role anon;
select throws_ok($$ select * from public.timer_sessions $$, '42501', null, 'Anonymous reads are denied');
select throws_ok($$ insert into public.timer_sessions default values $$, '42501', null, 'Anonymous inserts are denied');
select throws_ok($$ update public.timer_sessions set session_label = 'bad' $$, '42501', null, 'Anonymous updates are denied');
select throws_ok($$ delete from public.timer_sessions $$, '42501', null, 'Anonymous deletes are denied');
reset role;

set local role authenticated;
set local request.jwt.claim.sub = '10000000-0000-0000-0000-000000000001';
select is((select count(*) from public.timer_sessions), 1::bigint, 'Owner sees only their own snapshot');
select lives_ok($$ insert into public.timer_sessions (session_label) values ('New focus') $$, 'Insert defaults ownership to authenticated UID');
select throws_ok($$ insert into public.timer_sessions (user_id) values ('10000000-0000-0000-0000-000000000002') $$, '42501', null, 'Cannot insert for another user');
select lives_ok($$ update public.timer_sessions set session_label = 'My focus' where id = '20000000-0000-0000-0000-000000000001' $$, 'Owner can update their snapshot');
select is((select session_label from public.timer_sessions where id = '20000000-0000-0000-0000-000000000001'), 'My focus', 'Own update persists');
select throws_ok($$ update public.timer_sessions set user_id = '10000000-0000-0000-0000-000000000002' where id = '20000000-0000-0000-0000-000000000001' $$, '42501', null, 'Cannot transfer ownership');
with changed as (update public.timer_sessions set session_label = 'bad' where id = '20000000-0000-0000-0000-000000000002' returning id) select is((select count(*) from changed), 0::bigint, 'Cannot update another user snapshot');
with removed as (delete from public.timer_sessions where id = '20000000-0000-0000-0000-000000000002' returning id) select is((select count(*) from removed), 0::bigint, 'Cannot delete another user snapshot');
with removed as (delete from public.timer_sessions where id = '20000000-0000-0000-0000-000000000001' returning id) select is((select count(*) from removed), 1::bigint, 'Owner can delete their snapshot');
reset role;

select throws_ok($$ insert into public.timer_sessions (user_id) values ('10000000-0000-0000-0000-000000000099') $$, '23503', null, 'Owner must exist in Auth');
select throws_ok($$ insert into public.timer_sessions (phase) values ('unknown') $$, '23514', null, 'Unknown phases rejected');
select throws_ok($$ insert into public.timer_sessions (duration_seconds) values (-1) $$, '23514', null, 'Negative durations rejected');
select throws_ok($$ insert into public.timer_sessions (duration_seconds) values (6040) $$, '23514', null, 'Duration beyond iOS maximum rejected');
select throws_ok($$ insert into public.timer_sessions (duration_seconds) values ('NaN') $$, '23514', null, 'NaN rejected');
select throws_ok($$ insert into public.timer_sessions (total_duration_seconds) values ('Infinity') $$, '23514', null, 'Infinite total rejected');
select throws_ok($$ insert into public.timer_sessions (remaining_seconds) values (-1) $$, '23514', null, 'Negative remaining rejected');
select throws_ok($$ insert into public.timer_sessions (remaining_seconds) values (1801) $$, '23514', null, 'Remaining cannot exceed active total');
select throws_ok($$ insert into public.timer_sessions (phase) values ('running') $$, '23514', null, 'Running requires deadline');
select throws_ok($$ insert into public.timer_sessions (phase) values ('complete') $$, '23514', null, 'Completed requires zero remaining');
select throws_ok($$ insert into public.timer_sessions (captured_at) values ('infinity') $$, '23514', null, 'Capture timestamp must be finite');
select throws_ok($$ insert into public.timer_sessions (end_date) values ('infinity') $$, '23514', null, 'Deadline must be finite');
select lives_ok($$ insert into public.timer_sessions (phase, remaining_seconds, end_date) values ('running', 1234.125, '2026-10-22T12:00:00Z') $$, 'Fractional running snapshots accepted');
select lives_ok($$ insert into public.timer_sessions (phase, duration_seconds, total_duration_seconds, remaining_seconds) values ('complete', 0, 0, 0) $$, 'Zero duration accepted');
select lives_ok($$ insert into public.timer_sessions (duration_seconds, total_duration_seconds, remaining_seconds) values (6039, 6039, 6039) $$, '99:99 duration accepted');
select lives_ok($$ insert into public.timer_sessions (phase, remaining_seconds, end_date) values ('paused', 12.5, '2026-10-22T12:00:00Z') $$, 'Paused snapshot may retain stale deadline like iOS');

delete from auth.users where id = '10000000-0000-0000-0000-000000000002';
select is((select count(*) from public.timer_sessions where user_id = '10000000-0000-0000-0000-000000000002'), 0::bigint, 'Deleting an account cascades to its snapshots');

select * from finish();
rollback;
