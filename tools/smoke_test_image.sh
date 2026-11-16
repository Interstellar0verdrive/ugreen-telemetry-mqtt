#!/usr/bin/env bash
# Start one platform of the container image the way the UGOS Compose file does,
# and check that both services work, before the image is published.
#
# Usage: tools/smoke_test_image.sh IMAGE PLATFORM [VERSION]
# Example: tools/smoke_test_image.sh ugreen-telemetry-smoke:arm64 linux/arm64
# Without VERSION, the version declared in pyproject.toml is expected.
# Another architecture needs QEMU emulation, as set up by docker/setup-qemu-action.
set -euo pipefail

image=$1
platform=$2
version=${3:-$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')}

# The hardening shared by both services in compose.ugos.ghcr.yaml.
run=(docker run --platform "$platform" --read-only --cap-drop ALL
     --security-opt no-new-privileges:true --tmpfs /tmp:size=16m,mode=1777)
setup=""
reader=""

cleanup() {
    for container in $setup $reader; do
        docker rm -f -v "$container" >/dev/null 2>&1 || true
    done
}
trap cleanup EXIT

fail() {
    echo "FAIL on $platform: $*" >&2
    for container in $setup $reader; do
        echo "--- log of $container, setup token redacted" >&2
        docker logs "$container" 2>&1 | sed -E 's/(Setup token[^:]*:).*/\1 [redacted]/' >&2 || true
    done
    exit 1
}

# Stop a container as Docker does on a project update, and expect a clean exit.
stop_cleanly() {
    docker stop -t 30 "$2" >/dev/null
    local code
    code=$(docker inspect -f '{{.State.ExitCode}}' "$2")
    [ "$code" = 0 ] || fail "the $1 service exited with code $code when stopped"
}

echo "== $image on $platform, expecting version $version"

installed=$("${run[@]}" --rm --user 10001:10001 --network none --entrypoint python "$image" \
    -c 'import paho.mqtt.client, ugreen_telemetry; print(ugreen_telemetry.__version__)') \
    || fail "the package or the MQTT client does not import"
[ "$installed" = "$version" ] || fail "the image contains version $installed"
echo "package $installed and MQTT client import"

smartctl=$("${run[@]}" --rm --user 0:0 --network none --entrypoint smartctl "$image" --version) \
    || fail "smartctl does not run"
echo "${smartctl%%$'\n'*}"

# The setup service: web wizard and publisher, unprivileged, no disk access.
setup=$("${run[@]}" -d --user 10001:10001 -p 127.0.0.1::8765 \
    -v /data -v /secrets --tmpfs /snapshots:size=8m,mode=1777 \
    -e TARGETS_FILE=/snapshots/targets.json \
    --entrypoint python "$image" -m ugreen_telemetry.web)
port=$(docker port "$setup" 8765/tcp | head -n 1)
port=${port##*:}
headers=""
for _ in $(seq 120); do
    if headers=$(curl -fsS -D - -o /dev/null "http://127.0.0.1:$port/" 2>/dev/null); then
        break
    fi
    [ "$(docker inspect -f '{{.State.Running}}' "$setup")" = true ] || fail "the setup service stopped"
    sleep 1
done
[ -n "$headers" ] || fail "the setup page did not answer within two minutes"
served=$(printf '%s' "$headers" | tr -d '\r' | sed -n 's/^[Xx]-[Tt]elemetry-[Vv]ersion: //p')
[ "$served" = "$version" ] || fail "the setup page reports version '$served'"
printf '%s' "$headers" | grep -qi '^content-security-policy:' || fail "the setup page has no content security policy"
for asset in app.js update-check.js style.css app-icon-light.webp favicon-light.png; do
    curl -fsS -o /dev/null "http://127.0.0.1:$port/$asset" || fail "the setup page does not serve $asset"
done
docker logs "$setup" 2>&1 | grep -q 'Setup token (keep private): .\{20,\}' \
    || fail "the setup service logged no setup token"
echo "setup page answers with version $served and serves its assets"

# The reader service: no network, raw disk I/O only. Without selected disks it waits.
reader=$("${run[@]}" -d --user 0:0 --network none --cap-add SYS_RAWIO \
    --tmpfs /snapshots:size=8m,mode=1777 -e TARGETS_FILE=/snapshots/targets.json \
    --entrypoint python "$image" -m ugreen_telemetry.reader)
sleep 15
[ "$(docker inspect -f '{{.State.Running}}' "$reader")" = true ] || fail "the reader service stopped"
echo "reader keeps running without selected disks"

stop_cleanly setup "$setup"
stop_cleanly reader "$reader"
echo "both services stop cleanly"
echo "== PASS on $platform"
