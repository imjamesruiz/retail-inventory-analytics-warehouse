// CI validation pipeline -- mirrors the old .github/workflows/pr-validation.yml:
// lint, unit tests, dbt parse (no warehouse needed) on every run, and an
// optional live dbt build against Snowflake gated behind a parameter since
// (unlike GitHub Actions) Jenkins has no built-in "only if this secret is
// configured" condition.
pipeline {
    agent any

    options {
        timestamps()
        ansiColor('xterm')
        disableConcurrentBuilds()
    }

    parameters {
        booleanParam(
            name: 'RUN_DBT_BUILD',
            defaultValue: false,
            description: 'Also ingest fixtures, load Snowflake, and dbt build against a CI-only schema. Requires the snowflake-* credentials below.'
        )
    }

    environment {
        VENV = "${WORKSPACE}/.venv"
    }

    stages {
        stage('Install dependencies') {
            steps {
                sh '''
                    python3 -m venv "$VENV"
                    "$VENV/bin/pip" install --upgrade pip -q
                    "$VENV/bin/pip" install -e ".[dev,dbt]" -q
                '''
            }
        }

        stage('Ruff lint') {
            steps {
                sh '"$VENV/bin/ruff" check src tests dashboard'
            }
        }

        stage('Ruff format check') {
            steps {
                sh '"$VENV/bin/ruff" format --check src tests dashboard'
            }
        }

        stage('Unit tests') {
            steps {
                sh '"$VENV/bin/pytest" tests/unit -v'
            }
        }

        stage('dbt deps') {
            steps {
                dir('dbt_inventory') {
                    sh '"$VENV/bin/dbt" deps'
                }
            }
        }

        stage('dbt parse') {
            // Validates YAML/Jinja/ref graph without needing a live warehouse.
            environment {
                SNOWFLAKE_ACCOUNT  = 'placeholder'
                SNOWFLAKE_USER     = 'placeholder'
                SNOWFLAKE_PASSWORD = 'placeholder'
            }
            steps {
                dir('dbt_inventory') {
                    sh '"$VENV/bin/dbt" parse --profiles-dir .'
                }
            }
        }

        stage('Ingest + load + dbt build (live)') {
            when {
                expression { params.RUN_DBT_BUILD }
            }
            environment {
                DATA_SOURCE_MODE   = 'fixture'
                RAW_STORAGE_BACKEND = 'local'
                RAW_DATA_PATH      = './data/ci-raw'
                DBT_TARGET         = 'ci'
            }
            steps {
                withCredentials([
                    file(credentialsId: 'snowflake-private-key', variable: 'SNOWFLAKE_PRIVATE_KEY_PATH'),
                    string(credentialsId: 'snowflake-account', variable: 'SNOWFLAKE_ACCOUNT'),
                    string(credentialsId: 'snowflake-user', variable: 'SNOWFLAKE_USER'),
                    string(credentialsId: 'snowflake-role', variable: 'SNOWFLAKE_ROLE'),
                    string(credentialsId: 'snowflake-warehouse', variable: 'SNOWFLAKE_WAREHOUSE'),
                    string(credentialsId: 'snowflake-database', variable: 'SNOWFLAKE_DATABASE'),
                    string(credentialsId: 'snowflake-schema', variable: 'SNOWFLAKE_SCHEMA'),
                ]) {
                    sh '"$VENV/bin/python" -m inventory_pipeline.cli ingest --source-mode fixture --backfill-days 3'
                    sh '"$VENV/bin/python" -m inventory_pipeline.cli load-snowflake'
                    dir('dbt_inventory') {
                        withEnv(['SNOWFLAKE_SCHEMA_ANALYTICS=CI_ANALYTICS']) {
                            sh '"$VENV/bin/dbt" build --profiles-dir .'
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}
