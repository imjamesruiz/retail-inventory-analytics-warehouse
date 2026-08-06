-- Singular test: fails the build if any row the dashboard actually queries
-- claims to be observed more than 2 hours in the future. This duplicates
-- the not_far_in_future generic test at the intermediate layer deliberately
-- -- it's a defense-in-depth check at the fact-table grain, catching a bug
-- introduced anywhere between staging and the marts (a bad join, a wrong
-- date cast) that a single-layer test wouldn't.

select event_id, observed_at
from {{ ref('fact_inventory_observation') }}
where observed_at > dateadd('hour', 2, current_timestamp())
