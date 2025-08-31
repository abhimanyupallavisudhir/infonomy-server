#! /bin/bash
# first make sure the server is running
# then run this script to generate the client

openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g python \
  -o ../infonomy-client \
  --additional-properties packageName=infonomy_client,packageVersion=1.0.0 \
  --global-property packageLicense=MIT

# then manually edit "NoLicense" to "MIT" in the generated client's pyproject.toml because for some reason it's not doing it automatically

# and in wherever you're using the client run
# uv add --editable ../infonomy-client --config-settings editable_mode=strict