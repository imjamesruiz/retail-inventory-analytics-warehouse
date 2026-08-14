# Architecture decisions

## Why a separate project instead of extending the Discord bot

The bot (Node.js/TypeScript, Discord.js, Azure Functions, Cosmos DB/MongoDB) is
an application: poll -> diff against the last snapshot -> alert. Its data model
only needs the *latest* snapshot per product plus enough alert history to avoid
re-notifying. Attaching Snowflake to it would mean either (a) writing every poll
to both Mongo and Snowflake from the same process, coupling an alerting SLA to a
warehouse load, or (b) exporting from Mongo to Snowflake on a schedule, which is
just this project with an unnecessary extra hop. A clean batch/incremental ELT
system with its own raw-storage contract, its own retry/rate-limit tuning (no
alerting latency to protect), and its own repository is simpler to build,
reason about, and explain in an interview than a hybrid.

## Why Python for ingestion

dbt's ecosystem (dbt-snowflake, dbt_utils, dbt docs/lineage) is Python-native,
and the Snowflake Python connector's `write_pandas` gives a understandable,
inspectable load path. TypeScript would work too, but splitting the extraction
language from the transformation language buys nothing here and costs a second
toolchain.

## Why raw payloads are preserved

The Python normalization logic can have bugs, and retailer response shapes
change over time. If only normalized fields were stored, a normalization bug
found next month would be unfixable for past data -- there'd be nothing to
re-normalize. Storing the complete original response (as a NDJSON sidecar file
and again as a Snowflake `VARIANT` column) means normalization can always be
re-run against history.

## Why transformations happen in dbt, not in Python

The Python layer's job ends at "one clean, normalized event per observation."
Everything after that -- deduplication, state-change detection, daily rollups,
the dimensional model -- is relational logic best expressed, tested, and
documented as SQL: window functions for `LAG()`-based state changes are more
readable in SQL than reimplemented in Python, dbt's test framework gives
free data-quality coverage that a hand-rolled Python equivalent wouldn't, and
`dbt docs generate` produces a lineage graph automatically.

## Why a dimensional model

The analytics questions this project targets ("which retailer has the highest
availability," "how has price moved for this product") are exactly what a star
schema is for: fast aggregation across a fact table via foreign keys into small
dimensions, without repeated joins back to a wide raw table. It's also the
modeling style most directly transferable to other analytics engineering work.

## Why fixture mode is supported (and is the default)

A portfolio project that only works with a paid API key or a private company
integration can't actually be evaluated by a recruiter or reviewer. Fixture mode
makes the entire pipeline -- extraction through dashboard -- runnable with zero
external credentials, using data that's clearly labeled as synthetic
(`extractors/fixture_data.py` generates it deterministically; nothing claims to
be live production data). Live mode exists for the two sources with a
legitimately accessible method (see below) to prove the same code path works
against a real endpoint.

## Why Target and GameStop are fixture-only

The original bot's Target client called `redsky.target.com` with a hardcoded
internal API key recovered from inspecting network traffic, and its GameStop
client called an internal, undocumented page-data API. Neither is a documented,
permitted integration method -- they're reverse-engineered internal endpoints.
Walmart's Affiliate API is a registered, documented integration; Pokemon
Center's `<product>.json` is a standard, intentionally public feature of every
Shopify storefront (not an access-control bypass). Given that distinction, only
Walmart and Pokemon Center got live extractors. Target and GameStop keep their
normalization logic (useful, and portable to a real API if one becomes
available) but their `fetch_payloads()` raises `NotImplementedError` in live
mode with an explanation, rather than silently reusing the bot's original
unofficial endpoints.

## How idempotency and deduplication work

See [architecture.md](architecture.md#idempotency-and-deduplication-end-to-end)
for the full chain (raw storage never overwrites; `event_id` is a deterministic
hash; Snowflake loads via `MERGE ... WHEN NOT MATCHED`; dbt adds a belt-and-
suspenders `ROW_NUMBER()` dedup).

## Why some enterprise tools were intentionally excluded

Spark, Kafka, Airflow, Kubernetes, and Terraform would all be defensible choices
at a larger scale, but none of them solve a problem this project actually has:
data volume is small enough that pandas/Snowflake handle loads directly, there's
no continuous streaming requirement, Jenkins' cron trigger is sufficient
orchestration for a daily batch job, and Snowflake setup is simple enough
one-time SQL scripts document it without needing Terraform state to manage.
Adding them would demonstrate familiarity with the tools' existence, not with
solving this problem well -- and would make the project slower to set up and
harder to explain end-to-end in an interview, which defeats the point.
