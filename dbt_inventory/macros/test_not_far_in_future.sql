{% test not_far_in_future(model, column_name, max_hours_ahead=2) %}

-- Reusable generic test: fails for any row whose timestamp column claims to
-- be more than max_hours_ahead hours in the future. Applied to every
-- timestamp that ultimately comes from a retailer response (real or
-- fixture) rather than from the pipeline's own clock, since those are the
-- ones a malformed payload or clock-skewed source could corrupt.

select *
from {{ model }}
where {{ column_name }} > dateadd('hour', {{ max_hours_ahead }}, current_timestamp())

{% endtest %}
