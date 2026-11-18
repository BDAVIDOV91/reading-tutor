# Speed spike

Throwaway measurement of local Bulgarian STT engines on this laptop: load time, transcription time, real-time
factor and peak memory. Not part of the app: nothing under `src/` imports it, and it is exempt from TDD (plan
decision Q4). Results go to `docs/research/2026-11-18_speed-spike.md`.

## Audio

An adult (the owner) reads a public-domain passage slowly, partly syllable by syllable, with pauses, for about
two minutes:

```
ffmpeg -f pulse -i default -ac 1 -ar 16000 -t 150 spike/audio/slow.wav
```

`spike/audio/` and `spike/out/` are gitignored. Never put a child's recording here.

## Run

```
uv sync --project spike
# once, online: fetch the weights into the Hugging Face cache
for e in whisper-small whisper-medium whisper-turbo ctc-bg parakeet-v3; do
  uv run --project spike python spike/speed.py --engine "$e" --download
done
# offline (HF_HUB_OFFLINE=1 is set by the script), one fresh process per engine
spike/run_all.sh spike/audio/slow.wav
```

Each run prints one JSON line (timings and memory, no text). The transcript goes to `spike/out/<engine>.txt`;
`/usr/bin/time -v` output goes to `spike/out/<engine>.time`.

## Pass figure (fixed before measuring, plan Q2)

For a 2-minute read: transcription ≤ 1× real time = interactive; ≤ 5× = offline batch only (still evaluated);
slower, or peak RSS > 3.0 GB, or out of memory = not viable on this laptop.
