#!/usr/bin/env bash
# Run every spike engine, one fresh process each, one after another.
# Prints one JSON line per engine on stdout; /usr/bin/time's max RSS goes to spike/out/<engine>.time.
# Transcripts stay in spike/out/ and are never printed.
set -euo pipefail
cd "$(dirname "$0")/.."
audio="${1:-spike/audio/slow.wav}"
mkdir -p spike/out
for engine in whisper-small whisper-medium whisper-turbo ctc-bg parakeet-v3; do
  if /usr/bin/time -v -o "spike/out/${engine}.time" \
      uv run --frozen --offline --project spike python spike/speed.py --engine "$engine" --audio "$audio"; then
    :
  else
    echo "{\"engine\": \"${engine}\", \"run_status\": \"failed\", \"exit\": $?}"
  fi
done
