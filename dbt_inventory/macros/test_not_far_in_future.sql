{% test not_far_in_future(model, column_name, max_hours_ahead=2) %}

-- Reusable generic test: fails for any row whose timestamp column claims to
-- be more than max_hours_ahead hours in the future. Applied to every
-- timestamp that ultimately comes from a retailer response (real or
-- fixture) rather than from the pipeline's own clock, since those are the
-- ones a malformed payload or clock-skewed source could corrupt.
--
-- CURRENT_TIMESTAMP() is TIMESTAMP_LTZ; comparing it directly against a
-- TIMESTAMP_NTZ column makes Snowflake reinterpret the NTZ value in the
-- session's TIMEZONE parameter (not necessarily UTC), which can shift
-- genuinely-recent UTC timestamps to look hours into the future. Our NTZ
-- columns always hold UTC wall-clock values, so "now" must be pinned to
-- UTC explicitly rather than left to the session default.

select *
from {{ model }}
where {{ column_name }} > dateadd(
    'hour', {{ max_hours_ahead }}, convert_timezone('UTC', current_timestamp())::timestamp_ntz
)

{% endtest %}
