#!/usr/bin/env bash
# One-off copy of GitHub repositories into a Gitea instance via Gitea's migration API.
# Requires bash, curl and jq. Usage: bash github-to-gitea.sh
#
# Environment:
#   GITEA_URL         Base URL of the Gitea instance (required)
#   GITEA_TOKEN       Gitea token with write:organization and write:repository (required)
#   GITHUB_TOKEN      GitHub token that can read the private repositories (default: `gh auth token`)
#   SYNC_PAIRS        Space-separated github_owner:gitea_owner pairs (required), e.g. "alice:alice acme:acme";
#                     a Gitea owner can be an existing user or an organization
#   INCLUDE_FORKS     1 to copy forks too (default: 0)
#   INCLUDE_ARCHIVED  0 to skip archived repositories (default: 1)
#   WITH_METADATA     0 to copy git data only, without issues, pull requests, releases and wiki (default: 1)
#   DRY_RUN           1 to only print what would happen (default: 0)
#
# Gitea owners that exist neither as user nor as organization are created as organizations. Repositories that already exist in Gitea are skipped.
set -euo pipefail

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
for tool in curl jq; do
  command -v "$tool" >/dev/null 2>&1 || die "Missing dependency: $tool"
done

: "${GITEA_URL:?GITEA_URL is required}"
: "${GITEA_TOKEN:?GITEA_TOKEN is required}"
: "${SYNC_PAIRS:?SYNC_PAIRS is required}"
GITEA_URL=${GITEA_URL%/}
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  command -v gh >/dev/null 2>&1 || die 'GITHUB_TOKEN is unset and gh is not installed.'
  GITHUB_TOKEN=$(gh auth token) || die 'Could not read a token from gh.'
fi
INCLUDE_FORKS=${INCLUDE_FORKS:-0}
INCLUDE_ARCHIVED=${INCLUDE_ARCHIVED:-1}
WITH_METADATA=${WITH_METADATA:-1}
DRY_RUN=${DRY_RUN:-0}

gitea() {
  local method=$1 path=$2 body=${3:-}
  curl -sS --fail-with-body -X "$method" "$GITEA_URL/api/v1$path" \
    -H "Authorization: token $GITEA_TOKEN" -H 'Content-Type: application/json' \
    ${body:+--data "$body"}
}

gitea_exists() {
  local code
  code=$(curl -sS -o /dev/null -w '%{http_code}' "$GITEA_URL/api/v1$1" -H "Authorization: token $GITEA_TOKEN")
  [[ "$code" == 200 ]]
}

github_repos() {
  local owner=$1 page=1 batch kind
  kind=$(curl -sS --fail -H "Authorization: Bearer $GITHUB_TOKEN" "https://api.github.com/users/$owner" | jq -r .type)
  while :; do
    if [[ "$kind" == Organization ]]; then
      batch=$(curl -sS --fail -H "Authorization: Bearer $GITHUB_TOKEN" \
        "https://api.github.com/orgs/$owner/repos?type=all&per_page=100&page=$page")
    else
      batch=$(curl -sS --fail -H "Authorization: Bearer $GITHUB_TOKEN" \
        "https://api.github.com/user/repos?affiliation=owner&per_page=100&page=$page" |
        jq --arg owner "$owner" '[.[] | select(.owner.login == $owner)]')
    fi
    [[ $(jq length <<<"$batch") -gt 0 ]] || break
    jq -c '.[]' <<<"$batch"
    page=$((page + 1))
  done
}

ensure_org() {
  local org=$1
  gitea_exists "/users/$org" && return
  gitea_exists "/orgs/$org" && return
  if [[ "$DRY_RUN" == 1 ]]; then
    printf 'would create organization %s\n' "$org"
    return
  fi
  gitea POST /orgs "$(jq -n --arg o "$org" '{username: $o, visibility: "private"}')" >/dev/null
  printf 'created organization %s\n' "$org"
}

migrated=0 skipped=0 failed=0
for pair in $SYNC_PAIRS; do
  owner=${pair%%:*} org=${pair#*:}
  [[ -n "$owner" && -n "$org" && "$pair" == *:* ]] || die "Bad pair: $pair"
  ensure_org "$org"
  while read -r repo; do
    name=$(jq -r .name <<<"$repo")
    if [[ "$INCLUDE_FORKS" != 1 && $(jq -r .fork <<<"$repo") == true ]]; then
      printf 'skip %s/%s (fork)\n' "$owner" "$name"; skipped=$((skipped + 1)); continue
    fi
    if [[ "$INCLUDE_ARCHIVED" != 1 && $(jq -r .archived <<<"$repo") == true ]]; then
      printf 'skip %s/%s (archived)\n' "$owner" "$name"; skipped=$((skipped + 1)); continue
    fi
    if gitea_exists "/repos/$org/$name"; then
      printf 'skip %s/%s (exists in Gitea)\n' "$org" "$name"; skipped=$((skipped + 1)); continue
    fi
    if [[ "$DRY_RUN" == 1 ]]; then
      printf 'would copy %s/%s -> %s/%s\n' "$owner" "$name" "$org" "$name"; continue
    fi
    meta=$([[ "$WITH_METADATA" == 1 ]] && echo true || echo false)
    body=$(jq -n --argjson r "$repo" --arg org "$org" --arg tok "$GITHUB_TOKEN" --argjson meta "$meta" '{
      service: "github", clone_addr: $r.clone_url, auth_token: $tok,
      repo_owner: $org, repo_name: $r.name, description: ($r.description // ""),
      private: $r.private, mirror: false, lfs: true,
      wiki: $meta, issues: $meta, pull_requests: $meta, releases: $meta,
      labels: $meta, milestones: $meta}')
    if gitea POST /repos/migrate "$body" >/dev/null; then
      printf 'copied %s/%s -> %s/%s\n' "$owner" "$name" "$org" "$name"; migrated=$((migrated + 1))
    else
      printf 'FAILED %s/%s\n' "$owner" "$name" >&2; failed=$((failed + 1))
    fi
  done < <(github_repos "$owner")
done
printf 'done: %d copied, %d skipped, %d failed\n' "$migrated" "$skipped" "$failed"
[[ "$failed" -eq 0 ]]
