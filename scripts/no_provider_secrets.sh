#!/usr/bin/env bash
# Fails if a provider key name, a provider API URL or a synthetic test credential appears in a
# built page. The deploy workflow and CI's vercel-build job both scan with this one list.
#
#     scripts/no_provider_secrets.sh .vercel/output
set -euo pipefail

if grep -rl \
  -e "api.heigit.org" -e "HEIGIT_API_KEY" \
  -e "onemap.gov.sg/api" -e "ONEMAP_API_TOKEN" \
  -e "must-not-ship" \
  "$1"; then
  echo "A provider key or URL reached the built page (files above)." >&2
  exit 1
fi
echo "No provider key or URL in $1"
