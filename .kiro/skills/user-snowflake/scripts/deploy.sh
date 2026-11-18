#!/bin/bash
# Usage: deploy.sh <lib> <TAG> [<commit>]
# Deploys one commit of a registered Python library to the personal schema, without checking it out:
#   1. exports <commit> (default HEAD) of the library's repository with git archive;
#   2. builds the bundle with the library's own build script, into ~/data/test/snowflake/<TAG>/deploy-<hash>/;
#   3. uploads it to @FEATURELAB.DEV_<USER>.PYTHON_STAGE/<lib>/<tag lower>/<hash>/ and checks it landed;
#   4. creates FEATURELAB.DEV_<USER>.<PROCEDURE PREFIX>_<TAG>_<HASH> importing it.
# Prints "bundle <stage path>", "procedure <name>" and "vars <dbt --vars value>"; writes them to deploy.env too.
# Registered libraries are the cases below; a new one needs its build command, procedure definition and dbt vars.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LIB="$1"; TAG="$2"; REV="${3:-HEAD}"
python3 -B "$HERE/test_tag.py" check "$TAG"
source "$HOME/data/my-kiro-cli/.kiro/local-context.sh" >/dev/null 2>&1
C="$SNOWFLAKE_CONNECTION"
USER_ID="$(echo "$SNOWFLAKE_USER" | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z0-9_]/_/g')"
SCHEMA="DEV_${USER_ID}"

case "$LIB" in
  preprocess_evaluate)
    REPO="$HOME/data/preprocess_evaluate"
    PROCEDURE_PREFIX="PREPROCESS_FACTORS"
    ;;
  *) echo "unregistered library: $LIB (registered: preprocess_evaluate)" >&2; exit 1 ;;
esac

HASH="$(git -C "$REPO" rev-parse --short=7 "$REV^{commit}")"
HASH_UP="$(echo "$HASH" | tr '[:lower:]' '[:upper:]')"
TAG_LOWER="$(echo "$TAG" | tr '[:upper:]' '[:lower:]')"
LOCAL="$(python3 -B -c "import sys; sys.path.insert(0, '$HERE'); import test_tag; print(test_tag.local_dir('$TAG'))")/deploy-${HASH}"
STAGE_DIR="@FEATURELAB.${SCHEMA}.PYTHON_STAGE/${LIB}/${TAG_LOWER}/${HASH}"
PROCEDURE="FEATURELAB.${SCHEMA}.${PROCEDURE_PREFIX}_${TAG}_${HASH_UP}"
rm -rf "$LOCAL/src"; mkdir -p "$LOCAL/src"
git -C "$REPO" archive "$HASH" | tar -x -C "$LOCAL/src"

case "$LIB" in
  preprocess_evaluate)
    BUNDLE_FILE="$LOCAL/preprocess_evaluate.zip"
    (cd "$LOCAL/src" && conda run -n "$CONDA_ENV" python scripts/build_bundle.py --output "$BUNDLE_FILE" >/dev/null)
    BUNDLE="${STAGE_DIR}/preprocess_evaluate.zip"
    # PACKAGES follow the official template orchestration/create_preprocess_procedure.sql.
    DEFINITION="CREATE OR REPLACE PROCEDURE ${PROCEDURE}(
    CONFIG_NAME VARCHAR, RULE_ID NUMBER, STAGE VARCHAR,
    DATE_START DATE, DATE_END DATE, SRC_TABLE VARCHAR, WEIGHT_TABLE VARCHAR
)
RETURNS TABLE ()
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
ARTIFACT_REPOSITORY = snowflake.snowpark.pypi_shared_repository
PACKAGES = ('snowflake-snowpark-python', 'pandas==2.3.3', 'numpy==2.4.6',
            'scipy==1.17.1', 'pyarrow==25.0.1', 'pyyaml==6.0.3', 'hydra-core==1.3.2')
HANDLER = 'snowflake_preprocess.mart_handler'
IMPORTS = ('${BUNDLE}')
EXECUTE AS CALLER"
    VARS="{preprocess_bundle: \"${BUNDLE}\", preprocess_procedure: \"${PROCEDURE}\"}"
    ;;
esac

# Without --overwrite, snow stage copy skips a file already at the path; the path is per commit, so overwriting is safe.
COPY="$(snow stage copy -c "$C" --overwrite "$BUNDLE_FILE" "$STAGE_DIR")"
echo "$COPY" | grep -q "UPLOADED" || { echo "upload not done:"; echo "$COPY"; exit 1; } >&2
printf '%s;\n' "$DEFINITION" > "$LOCAL/create_procedure.sql"
snow sql -c "$C" -f "$LOCAL/create_procedure.sql" >/dev/null
rm -rf "$LOCAL/src"
{
  echo "commit $(git -C "$REPO" rev-parse "$HASH")"
  echo "bundle $BUNDLE"
  echo "procedure $PROCEDURE"
  echo "vars $VARS"
} | tee "$LOCAL/deploy.env"
