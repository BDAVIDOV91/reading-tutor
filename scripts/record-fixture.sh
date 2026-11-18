#!/usr/bin/env bash
# Record one ADULT fixture clip with the text shown in a window (tests/fixtures/FIXTURES.md).
#
#   bash scripts/record-fixture.sh <fixture-id> [seconds]
#
# The text comes from tests/fixtures/sidecars/<fixture-id>.json (`read_aloud`, else `reference_transcript`).
# Timeline: recording starts and the window opens at once -> read once -> after <seconds> a pop-up says
# "ГОТОВО" and the window closes by itself. Closing the window early does NOT stop or spoil the recording.
# Output: tests/fixtures/audio-local/<fixture-id>.wav (gitignored, never synced). Adult voice only.
set -euo pipefail

id="${1:?usage: record-fixture.sh <fixture-id> [seconds]}"
secs="${2:-30}"
repo="$(cd "$(dirname "$0")/.." && pwd)"
sidecar="$repo/tests/fixtures/sidecars/$id.json"
out="$repo/tests/fixtures/audio-local/$id.wav"

[[ "$id" =~ ^f[0-9]{2}-[a-z0-9-]+$ ]] || { echo "fixture id looks like f09-t1-browser-repro" >&2; exit 2; }
[[ -f "$sidecar" ]] || { echo "no sidecar $sidecar" >&2; exit 2; }
(( secs >= 5 && secs <= 30 )) || { echo "seconds must be 5..30 (fixtures stay under 30 s)" >&2; exit 2; }

text="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1], encoding="utf-8")); print(d.get("read_aloud") or d["reference_transcript"])' "$sidecar")"
src="$(pactl get-default-source)"
mkdir -p "$(dirname "$out")"

# Recording starts BEFORE the window opens, so nothing read the moment the text appears is lost (2026-11-18:
# a 3 s delay cut "Ето мама и" from f09). Leading silence is harmless.
echo "● recording $id for ${secs} s ..."
ffmpeg -hide_banner -loglevel error -y -f pulse -i "$src" -ac 1 -ar 16000 -t "$secs" "$out" &
rec=$!
sleep 0.5
DISPLAY="${DISPLAY:-:0}" zenity --info --no-wrap --title="● ЗАПИС $id — затваря се само" --ok-label="(затваря се само)" \
  --text="<span size='xx-large'>${text}</span>

<i>Записът вече върви (${secs} s). Прочети веднъж, после мълчи.</i>" \
  >/dev/null 2>&1 &
win=$!
wait "$rec"
kill "$win" 2>/dev/null || true
notify-send -t 5000 "✔ ГОТОВО" "Записът е запазен. Можеш да затвориш." 2>/dev/null || true

echo "✔ saved $out"
ffmpeg -hide_banner -i "$out" -af volumedetect -f null - 2>&1 | grep -oE '(mean|max)_volume: [-0-9.]+ dB' | tr '\n' ' '
echo
