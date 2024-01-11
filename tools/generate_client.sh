#!/bin/bash

set -u

OPENAPI_GENERATOR_VERSION=v6.6.0

# detect errors on spectacular
generr=$(poetry run python manage.py spectacular 2>&1 > /dev/null | grep ERROR);
if [ "$generr" != "" ]; then
  echo "Error(s) occur on generating OpenAPI spec from API implementation:";
  echo "$generr";
  exit 1;
fi

# generate OpenAPI spec
poetry run python manage.py spectacular --file spec.yaml;

# generate/format client code
dst=${1:-frontend/src/apiclient/autogenerated}
docker run --rm -u "$(id -u):$(id -g)" -v "${PWD}:/local" openapitools/openapi-generator-cli:$OPENAPI_GENERATOR_VERSION generate -i /local/spec.yaml -g typescript-fetch -o /local/"$dst" --additional-properties=typescriptThreePlus=true;
npx prettier --write "$dst"
