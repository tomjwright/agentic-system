#!/usr/bin/env bash
# Runs the previous release's API tests against this commit's database schema.
#
# The previous release keeps serving while a new migration runs, and a rollback returns to
# it, so it must still work on the new schema. Its own conftest.py drops the test schema
# and upgrades to head, so swapping in this commit's migrations makes those tests run on
# the new head schema. Its test_migrate.py is skipped: it pins that release's own list of
# revisions, which a new migration changes by design; this commit's tests cover migrating.
#
# Run from the repo root with TEST_DATABASE_URL set:
#     api/scripts/previous_release_tests.sh BASE_COMMIT
set -euo pipefail

base="$1"
previous="$(mktemp -d)/previous"
git worktree add --detach "$previous" "$base"
trap 'git worktree remove --force "$previous"' EXIT

rm -rf "$previous/api/migrations"
cp -r api/migrations "$previous/api/migrations"
echo "Previous release $(git rev-parse --short "$base"), migrations from $(git rev-parse --short HEAD)"

cd "$previous/api"
uv sync --locked
uv run pytest -q --ignore=tests/test_migrate.py
