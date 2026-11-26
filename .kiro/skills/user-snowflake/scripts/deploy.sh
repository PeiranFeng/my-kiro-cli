#!/bin/bash
# Usage: deploy.sh <lib> <TAG> [<commit>]
# Deploys one commit of a registered Python library to the personal schema, without checking it out:
#   1. exports <commit> (default HEAD) of the library's repository with git archive;
#   2. builds the bundle with the library's own build script, into ~/data/test/snowflake/<TAG>/deploy-<lib>-<hash>/;
#   3. uploads it to @FEATURELAB.DEV_<USER>.PYTHON_STAGE/<lib>/<tag lower>/<hash>/ and checks it landed;
#   4. for a library run through a stored procedure, creates FEATURELAB.DEV_<USER>.<PROCEDURE PREFIX>_<TAG>_<HASH>
#      importing it, with the parameters of the commit's own handler; a commit that has a mapping_handler also gets
#      PREPROCESS_FACTOR_MAPPING_<TAG>_<HASH>.
# Prints "commit <sha>" and "bundle <stage path>", plus "procedure <name>" and "vars <dbt --vars value>" for a
# procedure library (vars carries preprocess_mapping_procedure when the mapping procedure exists); writes them to deploy.env too.
# Registered libraries:
#   preprocess_evaluate  repo ~/data/preprocess_evaluate; scripts/build_bundle.py; procedure PREPROCESS_FACTORS_*.
#   evaluator_snowflake  repo ~/data/feature-lab; python/evaluator_snowflake/packaging.py build_zip, the same call
#                        as the Deploy workflow; no procedure. The models read it through the +imports config of
#                        dbt_project.yml, so a build points +imports of its exported copy at the printed bundle.
#   feature_lab_weight   repo ~/data/feature-lab; scripts/deploy_weight_lib.py build_zip, the same call as the Deploy
#                        workflow; no procedure. fact_weight_dense reads it through the imports of
#                        models/weight/_weight_models.yml, so a build points that line of its exported copy at the
#                        printed bundle.
# A new library needs its build command, and its procedure definition and dbt vars if it has a procedure.
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
  evaluator_snowflake)
    REPO="$HOME/data/feature-lab"
    PROCEDURE_PREFIX=""
    ;;
  feature_lab_weight)
    REPO="$HOME/data/feature-lab"
    PROCEDURE_PREFIX=""
    ;;
  *) echo "unregistered library: $LIB (registered: preprocess_evaluate, evaluator_snowflake, feature_lab_weight)" >&2; exit 1 ;;
esac

HASH="$(git -C "$REPO" rev-parse --short=7 "$REV^{commit}")"
HASH_UP="$(echo "$HASH" | tr '[:lower:]' '[:upper:]')"
TAG_LOWER="$(echo "$TAG" | tr '[:upper:]' '[:lower:]')"
LOCAL="$(python3 -B -c "import sys; sys.path.insert(0, '$HERE'); import test_tag; print(test_tag.local_dir('$TAG'))")/deploy-${LIB}-${HASH}"
STAGE_DIR="@FEATURELAB.${SCHEMA}.PYTHON_STAGE/${LIB}/${TAG_LOWER}/${HASH}"
PROCEDURE="FEATURELAB.${SCHEMA}.${PROCEDURE_PREFIX}_${TAG}_${HASH_UP}"
rm -rf "$LOCAL/src"; mkdir -p "$LOCAL/src"
git -C "$REPO" archive "$HASH" | tar -x -C "$LOCAL/src"

case "$LIB" in
  preprocess_evaluate)
    BUNDLE_FILE="$LOCAL/preprocess_evaluate.zip"
    (cd "$LOCAL/src" && conda run -n "$CONDA_ENV" python scripts/build_bundle.py --output "$BUNDLE_FILE" >/dev/null)
    BUNDLE="${STAGE_DIR}/preprocess_evaluate.zip"
    # Parameters are read from the exported handlers, so each commit gets the signature it implements.
    MAPPING_PROCEDURE="FEATURELAB.${SCHEMA}.PREPROCESS_FACTOR_MAPPING_${TAG}_${HASH_UP}"
    HANDLER_SIGNATURES="$(python3 -B -c '
import ast, sys
types = {"config_name": "VARCHAR", "rule_id": "NUMBER", "stage": "VARCHAR", "date_start": "DATE", "date_end": "DATE",
         "src_table": "VARCHAR", "weight_table": "VARCHAR", "mapping_table": "VARCHAR"}
for node in ast.parse(open(sys.argv[1]).read()).body:
    if isinstance(node, ast.FunctionDef) and node.name in ("mart_handler", "mapping_handler"):
        print(node.name, ", ".join(f"{a.arg.upper()} {types[a.arg]}" for a in node.args.args[1:]))
' "$LOCAL/src/snowflake_preprocess.py")"
    MART_PARAMS="$(echo "$HANDLER_SIGNATURES" | sed -n 's/^mart_handler //p')"
    MAPPING_PARAMS="$(echo "$HANDLER_SIGNATURES" | sed -n 's/^mapping_handler //p')"
    # PACKAGES follow the official template orchestration/create_preprocess_procedure.sql.
    DEFINITION="CREATE OR REPLACE PROCEDURE ${PROCEDURE}(${MART_PARAMS})
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
    if [ -n "$MAPPING_PARAMS" ]; then
      DEFINITION="${DEFINITION};
CREATE OR REPLACE PROCEDURE ${MAPPING_PROCEDURE}(${MAPPING_PARAMS})
RETURNS TABLE ()
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
ARTIFACT_REPOSITORY = snowflake.snowpark.pypi_shared_repository
PACKAGES = ('snowflake-snowpark-python', 'pandas==2.3.3', 'numpy==2.4.6',
            'scipy==1.17.1', 'pyarrow==25.0.1', 'pyyaml==6.0.3', 'hydra-core==1.3.2')
HANDLER = 'snowflake_preprocess.mapping_handler'
IMPORTS = ('${BUNDLE}')
EXECUTE AS CALLER"
      VARS="{preprocess_bundle: \"${BUNDLE}\", preprocess_procedure: \"${PROCEDURE}\", preprocess_mapping_procedure: \"${MAPPING_PROCEDURE}\"}"
    fi
    ;;
  evaluator_snowflake)
    BUNDLE_FILE="$LOCAL/evaluator_snowflake.zip"
    # packaging.py is stdlib-only, so no conda environment is needed.
    (cd "$LOCAL/src" && PYTHONPATH=python python3 -B -c \
      'import sys; from evaluator_snowflake.packaging import build_zip; build_zip(sys.argv[1])' "$BUNDLE_FILE")
    BUNDLE="${STAGE_DIR}/evaluator_snowflake.zip"
    ;;
  feature_lab_weight)
    BUNDLE_FILE="$LOCAL/feature_lab_weight.zip"
    (cd "$LOCAL/src" && python3 -B -c 'import sys; sys.path.insert(0, "scripts"); from deploy_weight_lib import build_zip; build_zip(sys.argv[1])' "$BUNDLE_FILE")
    BUNDLE="${STAGE_DIR}/feature_lab_weight.zip"
    ;;
esac

# Without --overwrite, snow stage copy skips a file already at the path; the path is per commit, so overwriting is safe.
COPY="$(snow stage copy -c "$C" --overwrite "$BUNDLE_FILE" "$STAGE_DIR")"
echo "$COPY" | grep -q "UPLOADED" || { echo "upload not done:"; echo "$COPY"; exit 1; } >&2
if [ -n "$PROCEDURE_PREFIX" ]; then
  printf '%s;\n' "$DEFINITION" > "$LOCAL/create_procedure.sql"
  snow sql -c "$C" -f "$LOCAL/create_procedure.sql" >/dev/null
fi
rm -rf "$LOCAL/src"
{
  echo "commit $(git -C "$REPO" rev-parse "$HASH")"
  echo "bundle $BUNDLE"
  if [ -n "$PROCEDURE_PREFIX" ]; then
    echo "procedure $PROCEDURE"
    echo "vars $VARS"
  fi
} | tee "$LOCAL/deploy.env"
