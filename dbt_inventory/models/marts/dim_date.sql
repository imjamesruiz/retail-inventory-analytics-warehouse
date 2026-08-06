with spine as (
    {{
        dbt_utils.date_spine(
            datepart="day",
            start_date="cast('2024-01-01' as date)",
            end_date="cast(dateadd('year', 1, current_date()) as date)"
        )
    }}
)

select
    cast(date_day as date) as date_day,
    to_number(to_char(date_day, 'YYYYMMDD')) as date_key,
    year(date_day) as year,
    month(date_day) as month,
    day(date_day) as day_of_month,
    dayofweek(date_day) as day_of_week,
    dayname(date_day) as day_name,
    monthname(date_day) as month_name,
    weekofyear(date_day) as week_of_year,
    (dayofweek(date_day) in (0, 6)) as is_weekend
from spine
