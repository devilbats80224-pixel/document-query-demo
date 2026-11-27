#!/bin/bash
# Download exactly the tested image for the repository's current protected main.
set -euo pipefail
repo=devilbats80224-pixel/document-query-demo
name=document-query-demo
gh_bin=${GH_BIN:-gh}
base=http://127.0.0.1:8875
token="$HOME/Library/Application Support/光寶備考/loopback-token"
artifact=$(mktemp -d)
trap 'rm -rf "$artifact"' EXIT
[ "$(uname -s):$(uname -m)" = 'Darwin:arm64' ] || { echo 'Requires Apple Silicon Mac' >&2; exit 2; }
main=$("$gh_bin" api "repos/$repo/git/ref/heads/main" --jq .object.sha)
run=$("$gh_bin" run list -R "$repo" --workflow verify-demo.yml --branch main --commit "$main" --event push --status success --limit 1 --json databaseId --jq '.[0].databaseId // empty')
[[ "$run" =~ ^[0-9]+$ ]] || { echo 'No passing main delivery run' >&2; exit 3; }
"$gh_bin" run download "$run" -R "$repo" -n "document-query-demo-arm64-$main" -D "$artifact"
(cd "$artifact" && shasum -a 256 -c SHA256SUMS)
test "$(cat "$artifact/COMMIT")" = "$main"
test "$("$gh_bin" api "repos/$repo/git/ref/heads/main" --jq .object.sha)" = "$main"
docker load -i "$artifact/document-query-demo-arm64.tar.gz"
id=$(cat "$artifact/IMAGE_ID")
[[ "$id" =~ ^sha256:[0-9a-f]{64}$ ]]
test "$(docker image inspect "document-query-demo:$main" --format '{{.Id}} {{.Architecture}} {{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$id arm64 $main"

# Do not touch similarly named or foreign containers. Preserve an old instance
# for rollback; its in-memory uploaded documents are not migrated on upgrades.
if docker inspect "$name" >/dev/null 2>&1; then
    test "$(docker inspect "$name" --format '{{index .Config.Labels "app.scope"}}')" = document-query-demo
    if [ "$(docker inspect "$name" --format '{{.Image}} {{.State.Running}}')" = "$id true" ]; then
        curl -fsS --max-time 3 "$base/health"
        exit 0
    fi
fi
args=(--label app.scope=document-query-demo --read-only
      --cap-drop ALL --security-opt=no-new-privileges --pids-limit 128
      --user "$(id -u):$(id -g)" --tmpfs /tmp:rw,noexec,nosuid,size=96m)
if [ -r "$token" ] && [ -s "$token" ]; then
    args+=(-e LITEON_MODEL_TRANSPORT=docker-desktop
           --mount "type=bind,src=$token,dst=/run/secrets/demo-model-token,readonly")
fi
healthy() {
    for _ in $(seq 1 30); do
        if curl -fsS --max-time 1 "$1/health" | grep -q '"local_offline"'; then return 0; fi
        sleep 1
    done
    return 1
}

# Check the exact image first, on a disposable loopback-only port.
trial=$(docker run -d "${args[@]}" -p '127.0.0.1::8775' "$id")
trap 'docker rm -f "$trial" >/dev/null 2>&1 || true; rm -rf "$artifact"' EXIT
trial_port=$(docker port "$trial" 8775/tcp | awk -F: 'NR==1{print $NF}')
healthy "http://127.0.0.1:$trial_port"
docker rm -f "$trial" >/dev/null
trap 'rm -rf "$artifact"' EXIT

old=''
if docker inspect "$name" >/dev/null 2>&1; then
    old="$name-rollback-$(date +%s)"
    docker stop "$name" >/dev/null
    docker rename "$name" "$old"
fi
if ! docker run -d --name "$name" --restart unless-stopped "${args[@]}" -p '127.0.0.1:8875:8775' "$id" || ! healthy "$base"; then
    docker rm -f "$name" >/dev/null 2>&1 || true
    if [ -n "$old" ]; then
        docker rename "$old" "$name"
        docker start "$name" >/dev/null
    fi
    echo 'Deployment failed the local readiness check' >&2
    exit 4
fi
printf 'Demo: %s/workspace\n' "$base"
