# Reading tutor prototype: requirements research

Date: 2026-11-18. Scope: brief Part 2 (`docs/PROTOTYPE_BRIEF.md`). Nothing was built.
Method: two web-research sweeps (search plus fetches of primary pages) and one local hardware check.
`[fetched]` = the page was opened and read. `UNVERIFIED` = not confirmed from a primary source. Legal points are
research, not legal advice.

## Answer first

1. **A zero-budget, fully local prototype is possible, but the laptop is the constraint.** Free local engines
   cover Bulgarian (Whisper, NVIDIA Parakeet v3, Bulgarian CTC models). This laptop has 4 cores, 7.2 GB RAM
   (about 3.4 GB free) and no GPU, so only small or medium models are realistic and their speed here is unmeasured.
2. **The main risk to the product idea is known in the literature: Whisper tends to hide reading mistakes.** It
   outputs a real or expected word when the child said something else: few false flags, many missed mistakes.
   CTC and phoneme models catch more mistakes but raise more false alarms. The prototype must measure both
   error types, not word error rate.
3. **No published evidence exists for Bulgarian children on any engine.** Every child number found is Dutch or
   English. The prototype's own testing log is the only way to answer the brief's question.
4. **The paid engines named in the brief are out.** OpenAI has no free tier; Google and Azure need a billing
   account. Cloud free tiers exist (Groq, AssemblyAI, Deepgram, Speechmatics, ElevenLabs) but send audio off
   the laptop, so they fit only adult-recorded fixtures unless the owner decides otherwise.
5. **Phone microphone needs HTTPS or localhost.** Simplest local route: USB `adb reverse` on day one (adb is
   installed), then a local certificate (mkcert) for untethered use. No tunnel, no public URL.
6. **Most of the usual grade 1 reading canon is still under copyright** (Ran Bosilek until 2029, Karaliychev,
   Gabe, Mileva). Original short texts are the practical choice.

## 1. Speech-to-text for Bulgarian at zero cost

### Local engines (audio never leaves the laptop)

| Engine | Bulgarian evidence | Size | Notes |
|---|---|---|---|
| Whisper via [faster-whisper](https://github.com/SYSTRAN/faster-whisper) or [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | large-v3 FLEURS CER 4.06 %, Common Voice 25 CER 4.29 % ([BuzzASR card](https://huggingface.co/BuzzASR/bulgarian) [fetched]); 15.2 % FLEURS WER is a vendor figure ([ElevenLabs](https://elevenlabs.io/speech-to-text/bulgarian)) | small 244 M, medium 769 M, turbo 809 M, large 1550 M params ([openai/whisper](https://github.com/openai/whisper) [fetched]) | CPU int8 supported; built-in VAD. CPU speed on this laptop UNVERIFIED: measure. |
| Whisper Bulgarian fine-tunes | [BuzzASR/bulgarian](https://huggingface.co/BuzzASR/bulgarian) (large-v3): FLEURS WER 13.33; its Common Voice WER 1.44 may reflect train/test overlap. [shripadbhat/whisper-medium-bg](https://huggingface.co/shripadbhat/whisper-medium-bg/blob/main/README.md): CV11 WER 18.76 | as base model | Fine-tunes on adult read speech may "correct" even more. |
| [NVIDIA Parakeet-tdt-0.6b-v3](https://build.nvidia.com/nvidia/parakeet-tdt-0_6b/modelcard) | Bulgarian FLEURS WER 12.64 (NVIDIA's own card) | 0.6 B params | Best non-Whisper candidate. Needs NeMo or an ONNX runtime. CPU speed UNVERIFIED. |
| Bulgarian wav2vec2 XLS-R CTC ([anuragshas](https://huggingface.co/anuragshas/wav2vec2-large-xls-r-300m-bg), [infinitejoy](https://huggingface.co/infinitejoy/wav2vec2-large-xls-r-300m-bulgarian/blob/main/README.md)) | WER 30 to 47 % without a language model | 300 M params | Weak as a transcriber, but it has no word-level language model, so it outputs what it hears. Useful as the "literal" engine. |
| [MMS-1b-all](https://huggingface.co/facebook/mms-1b-all) `bul` adapter | No published Bulgarian WER | 1 B params | CC-BY-NC: fine for the prototype, not for a commercial app. Likely too heavy here. |
| Whisper in the phone browser (transformers.js) | none | tiny/base only | No measured data on cheap phones; tiny/base are weak. Not needed with phone-to-laptop. |

### Not local

- **Browser Web Speech API:** sends audio to Google by default ([MDN](https://developer.mozilla.org/docs/Web/API/Web_Speech_API/Using_the_Web_Speech_API)); the on-device mode is "Not supported" on Chrome Android ([Can I use](https://caniuse.com/mdn-api_speechrecognition_processlocally) [fetched]). bg-BG availability UNVERIFIED. Conflicts with "local only".
- **Cloud free tiers** (all send audio out; card requirement, EU region and retention terms mostly UNVERIFIED because pricing pages failed to load):
  - Groq-hosted Whisper large-v3 / turbo: free tier, rate limited ([docs](https://console.groq.com/docs/speech-to-text) [fetched])
  - AssemblyAI: free tier, no card ([pricing](https://www.assemblyai.com/pricing) [fetched]); Bulgarian coverage UNVERIFIED
  - Deepgram Nova-3: Bulgarian `bg` added ([blog](https://deepgram.com/blog/deepgram-expands-nova-3-with-11-new-languages-across-europe-and-asia)); free credit UNVERIFIED
  - Speechmatics, ElevenLabs Scribe: Bulgarian listed; free quotas conflict or UNVERIFIED
  - Gladia: free-plan audio may be used for training. Exclude.
- **Brief's named engines:** Google Cloud STT (60 free minutes a month but needs a billing account, [pricing](https://cloud.google.com/speech-to-text/pricing) [fetched]); Azure (5 free hours a month, account and probably card); OpenAI (paid).

## 2. Children's speech and hidden mistakes

- **Accuracy on children, other languages.** Whisper large-v3 zero-shot: WER 12.6 on MyST (grades 3 to 5) and 19.9 on CSLU OGI ([Fan et al., Interspeech 2024](https://arxiv.org/pdf/2406.10507)). Dutch children 6 to 13 reading aloud: faster-whisper large-v2 WER 9.8 % against 6.7 % for adults ([Gao et al. 2024](https://arxiv.org/abs/2406.07060) [fetched]). Error grows as age drops ([Singh et al.](https://arxiv.org/html/2502.08587v1) [fetched]). A widely quoted "84.6 % WER for kindergartners" is secondary-source only: UNVERIFIED.
- **Bulgarian children: nothing published** for any engine. Only a small preschool speech database prototype exists ([Kraleva](https://arxiv.org/pdf/1605.07735)).
- **Syllable-by-syllable reading:** no study found. Expect it to be the weakest case; measure with fixtures.
- **Whisper "corrects" misreadings.** In the Dutch study wav2vec2 had the highest mistake recall (0.83) and Whisper the highest precision ([Gao et al. 2024](https://arxiv.org/abs/2406.07060)); the exact precision and recall per condition conflict between summaries, UNVERIFIED. A Basque study states conventional ASR normalises mispronunciations into correct text ([arXiv 2403.08187](https://arxiv.org/pdf/2403.08187)). Comparing a transcript to the text "performs poorly when ASR inaccurately transcribes verbatim speech" ([Smith et al., Interspeech 2025](https://www.isca-archive.org/interspeech_2025/smith25_interspeech.html) [fetched]).
- **Prompting Whisper with the target text** raised Dutch mistake-detection F1 from 0.39 to 0.73 and cut WER from 9.4 % to 5.1 % ([Gao et al., Interspeech 2025](https://www.isca-archive.org/interspeech_2025/gao25c_interspeech.html) [fetched]). Same mechanism could also pull output toward the expected word, so it must be tested as its own labelled variant with deliberate-mistake fixtures.
- **Silence and pauses.** Whisper can hallucinate text on non-speech ([Calm-Whisper](https://arxiv.org/pdf/2505.12969)). Mitigations are practitioner-level: VAD filter, `condition_on_previous_text=False`, no-speech thresholds. A slow reader pauses mid-word, so the VAD silence gap must be long (over about 1 s) and tested.
- **Prior art makes the same trade-off.** Project LISTEN accepted about 97 % of correct reading but caught about a quarter of misreadings ([Beck, Jia, Mostow](https://typeset.io/pdf/automatically-assessing-oral-reading-fluency-in-a-computer-64jmt5nbh0.pdf)). Google Read Along tuned its on-device recogniser so feedback feels encouraging ([Android Developers Blog](https://android-developers.googleblog.com/2020/06/on-device-ML-design-insights.html)).

## 3. Align and score

- **Aligner:** a custom word-level dynamic-programming aligner, not plain edit distance. A published reading tracker uses: advance one word free, stay or jump back nearly free, forward skip costs the number of words skipped ([SLaTE 2011](https://people.es.aau.dk/~zt/doc/Tracking-paper_SLaTE2011.pdf), summary only). Children skip and jump, so the utterance cannot be forced onto the text ([Banerjee et al. 2003](https://www.isca-archive.org/eurospeech_2003/banerjee03_eurospeech.pdf)).
- **Behaviours to handle:**
  - repeat: collapse, not an error
  - self-correction: last attempt wins
  - syllable reading: try joining 2 to 4 consecutive fragments before comparing
  - skipped line: local alignment to find where reading resumed
  - stopped early: "not attempted", distinct from skipped
- **Scoring convention** from oral reading fluency practice: omissions, substitutions and hesitations over about 3 s are errors; repetitions and insertions are not; self-corrections count as correct ([DIBELS 8 rules](https://learning.amplify.com/m/32d101f5a7450c3f/original/mCLASSPD_DIBELS8thEd_TeacherAdministeredScoringRules.pdf), [UMD CBM](https://terpconnect.umd.edu/~dlspeece/cbmreading/examinermat/scoring.html)). No Bulgarian words-per-minute norms found.
- **Libraries:** [RapidFuzz](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html) for character similarity (avoid `partial_ratio`, it matches substrings); [jiwer](https://jitsi.github.io/jiwer/) only for per-engine WER.
- **Fuzzy threshold:** nothing published for Bulgarian. Starting rule to tune from the log: exact = correct; short words exact only; similarity of 0.8 or more on words of 5+ letters = "unsure", shown to the parent.
- **Forced alignment** gives timings, not correctness. Options: [ctc-forced-aligner](https://github.com/MahmoudAshraf97/ctc-forced-aligner) (MMS-based, CPU) and [Montreal Forced Aligner Bulgarian models](https://mfa-models.readthedocs.io/en/latest/acoustic/Bulgarian/index.html). WhisperX has no default Bulgarian model. Not needed for the first loop.
- **Bulgarian normalisation:**
  - casefold; strip punctuation and all dash types
  - map `ѝ` to `и` and strip stress marks on both sides
  - map Latin look-alike letters only inside mixed-script tokens
  - `num2words` has no Bulgarian ([repo](https://github.com/savoirfairelinux/num2words)): write numbers as words in texts and keep a small digit lookup
  - no Bulgarian syllabification library found; a vowel-based rule is feasible

## 4. Privacy and law

- **Voice for transcription only is ordinary personal data**, not special category: biometric data requires processing for unique identification ([GDPR Art. 4(14)](https://gdpr-info.eu/art-4-gdpr/), [Recital 51](https://gdpr-info.eu/recitals/no-51/)); EDPB treats voice *identification* as biometric ([Guidelines 02/2021](https://www.edpb.europa.eu/system/files/2021-07/edpb_guidelines_202102_on_vva_v2.0_adopted_en.pdf)). So: no speaker ID, no voiceprints.
- **Age of digital consent in Bulgaria is 14** (ЗЗЛД Art. 25в, read from a [republication](https://trudipravo.bg/znanie-za-vas/zakon-za-zashtita-na-lichnite-danni/); official text not loaded).
- **Household exemption** ([Art. 2(2)(c)](https://gdpr-info.eu/art-2-gdpr/), [Recital 18](https://gdpr-info.eu/recitals/no-18/)) plausibly covers a parent testing with their own children on their own devices. It is read narrowly, and stops fitting once recordings or logs are shared, other families test, or the data feeds the commercial product. A cloud engine brings the provider's terms in.
- **Commercial app later:** parental consent, DPIA, minimisation, EU processing, deletion flow, processor agreements. No КЗЛД guidance found (site did not load).
- **EU AI Act:** Annex III 3(b) lists systems that evaluate learning outcomes in educational institutions ([Annex III](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)). A home parent app is probably outside; selling to schools could bring it in. UNVERIFIED, needs a lawyer before launch.

## 5. Prototype shape

- **Secure context:** `getUserMedia` works only on HTTPS or `localhost`; `http://192.168.x.x` does not qualify ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia), [Secure contexts](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts)).
- **Local options:**
  1. `adb reverse` over USB: the phone opens `http://localhost:PORT`, no certificate, nothing on the Wi-Fi ([Android docs](https://developer.android.com/develop/ui/views/layout/webapps/access-local-server)). Android only, phone cabled.
  2. [mkcert](https://github.com/FiloSottile/mkcert) certificate for the laptop's LAN address, root CA installed once on the phone through Settings (Android 11+). Whether Chrome Android accepts it is a device check.
  3. Self-signed click-through and the Chrome insecure-origin flag: conflicting reports, test only if 2 fails.
  4. Tailscale: needs an account and publishes machine names to public certificate logs. Avoid.
- **Audio:** Chrome Android records `webm/opus`, iOS Safari `mp4/aac` ([WebKit](https://webkit.org/blog/11353/mediarecorder-api/)). Keep the original, derive 16 kHz mono WAV with ffmpeg (installed) so every engine gets identical audio. Log the real mime type and track settings.
- **Storage:** SQLite plus audio files under gitignored `data/`; attempt ids, no names; CSV export script.

## 6. Live highlighting (optional scope)

- Whisper streaming lags about 3.3 s on a GPU ([Macháček et al.](https://arxiv.org/pdf/2307.14743)); slower on this CPU. Too slow for word-by-word.
- No Bulgarian Vosk model ([model list](https://alphacephei.com/vosk/models) checked); none found for sherpa-onnx streaming.
- The plausible route is tracking against the known text with a CTC model ([Sunder et al.](https://arxiv.org/pdf/2310.11486), [Reading Ahead 2026](https://aclanthology.org/2026.nlp4call-1.21.pdf)). Untested for Bulgarian; defer until the core loop has numbers.

## 7. Prior art

No Bulgarian or Slavic reading tutor with speech recognition was found. Google Read Along (on-device; Bulgarian
not in the languages seen), Microsoft Reading Coach (method unpublished), Amira (company-reported 96.9 %
agreement with humans), SoapBox Labs (phoneme-level scoring, languages not found), Project LISTEN (above).

## 8. Texts

- Copyright is life plus 70 years from 1 January after death ([ЗАПСП Art. 27, 31](https://www.lex.bg/laws/ldoc/2133094401)); folklore is not protected (Art. 4).
- Free now: Vazov, P. Slaveykov, Tserkovski, Elin Pelin, Raztsvetnikov, Raynov. Not free: Ran Bosilek (2029), Karaliychev (2043), Dora Gabe (2054), Leda Mileva (2084). Death years are from Wikidata.
- chitanka.info has no blanket licence; Wikisource is per work. No open primer found.
- Original short texts avoid clearance and can control letters and syllables. A Bulgarian readability index exists ([Kazakov et al. 2025](https://aclanthology.org/2025.lowresnlp-1.18/)).

## Requirements

**Must**
1. R1. Recordings, transcripts and scores stay on the laptop; no engine sends child audio out without an ADR.
2. R2. Engines behind one interface; one recording can run through all; each declares where audio goes.
3. R3. Baseline Whisper runs without the target text as prompt; prompting is a separate labelled variant.
4. R4. At least one engine without a word-level language model (CTC), to compare mistake recall.
5. R5. Aligner handles repeats, self-corrections, syllable fragments, skips, skipped lines, early stop.
6. R6. Word states: correct, misread (with what was heard), skipped, plus "unsure" for near matches.
7. R7. Log keeps, per word and engine, the automatic marking and the parent's marking separately.
8. R8. Report per engine: mistake recall, mistake precision, false flags per 100 correct words, with the sample.
9. R9. Original audio kept untouched; engines read one derived 16 kHz mono WAV.
10. R10. "Delete all recordings" removes audio, transcripts, marks and exports.
11. R11. Core (normalise, align, score) has no UI, network or engine imports.
12. R12. Adult-recorded fixtures with deliberate mistakes exist before any engine is judged.

**Should**
- R13. Per-attempt timing so a 2-minute read does not wait many minutes (measure first).
- R14. Sensitivity setting for the unsure threshold.
- R15. Sample texts are original, graded by word length and syllable structure.

**Later**
- R16. Live highlighting through CTC tracking.
- R17. Legal review before any commercial step.

## Proposed stack (for decision, not settled)

- **Server:** Python 3.12 with uv (both installed), FastAPI, SQLite, ffmpeg.
- **Engines:** faster-whisper (int8) first; then a Bulgarian CTC model; then Parakeet v3 through ONNX if it runs.
- **Core:** pure Python package (`normalise`, `align`, `score`), table-driven tests with pytest.
- **Client:** one plain HTML/JS page (MediaRecorder upload, results, corrections). No framework.
- **Access:** `adb reverse` first, mkcert second.

## Short plan (brief step 1)

0. **Speed spike:** one adult recording; time Whisper small, medium and turbo on this laptop. Decides the model.
1. **Core, test-first:** normalise, align, score against invented text cases.
2. **First loop:** record, upload, Whisper, coloured results, over `adb reverse`.
3. **Log and corrections:** SQLite, attempts table, manual marking, per-engine report, CSV, delete-all.
4. **More engines:** CTC model, then Parakeet or a prompted-Whisper variant; "run all".
5. **Untethered:** mkcert on the phone.
6. **Testing checklist** with go / no-go numbers proposed for the owner.

## Open questions for the owner

1. Where do the engines run: this laptop only, or is a stronger machine on the home network available?
2. May any cloud engine receive recordings, or adult fixtures only?
3. Core language: Python (simplest now) or TypeScript (reusable inside a later mobile app)?
4. Which phone and browser will the children use (Android Chrome assumed)?
5. Is an "unsure" word state acceptable next to green, orange and red?
6. Original texts instead of classic authors?

### Owner decisions, 2026-11-18

- Q1: this laptop, and measure speed first (it is a prototype).
- Q2: cloud engines may receive adult fixtures only; children's recordings stay local.
- Q3: Python core.
- Q4: open. The owner described two uses: the phone beside the child while the parents are in another room, or
  a browser open on the computer listening to the child. Suggestion given: one web page serves both. First loop
  in the laptop's own browser (`localhost` is a secure context: no cable, no certificate); accuracy tests on
  the phone beside the child, because the product targets phone microphones, reached untethered through a
  local certificate. **Decided: laptop browser only for the prototype.** The phone is added only if the
  laptop test passes. Consequence: plan step 5 (mkcert) is deferred, and laptop-microphone results do not
  prove phone-microphone accuracy.
- Q5 and Q6: defaults stated to the owner (an "unsure" state; original texts), no objection recorded yet.

## Confidence and gaps

- **High:** secure-context rule; copyright term; Whisper model sizes; no Bulgarian Vosk model; brief's cloud engines need payment or a billing account.
- **Medium:** Whisper hides misreadings (consistent across three papers, but Dutch, Basque and English); household exemption fit.
- **Low / unverified:** every CPU speed figure; cloud free-tier terms and card requirements; the exact Gao 2024 precision and recall; Chrome Android trust of a user-installed CA; Parakeet on CPU; Bulgarian Web Speech support; AI Act classification; author death years (Wikidata).
- **Unknown until measured:** everything about Bulgarian children aged 6 to 8.
