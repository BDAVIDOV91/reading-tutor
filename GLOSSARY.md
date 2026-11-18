# Reading tutor

A child aged 6 to 8 reads a Bulgarian text aloud; the prototype transcribes, aligns and marks each word, so the
owner can judge whether speech recognition can follow the child and detect mistakes.

## Reading

**Text**:
The passage the child is asked to read, at one graded level. A changed text is a new version, never pooled with
the old one.
_Avoid_: story, passage (when the graded unit is meant)

**Attempt**:
One reading of one text by one speaker, with its recording.
_Avoid_: session, take, recording (the audio is part of the attempt)

**Engine run**:
One speech engine's transcription of one attempt, with its settings.
_Avoid_: result, transcription job

**Self-correction**:
A word read wrongly and then read again; the last attempt at the word counts.

**Repeat**:
A word or phrase read again with nothing wrong; not an error.

## Word marks

**Correct**:
A text word read as written, after normalisation (including a successful self-correction).

**Misread**:
A text word read as something else; the heard text is kept.
_Avoid_: substitution, error (too broad)

**Skipped**:
A text word passed over while reading continued after it.
_Avoid_: omitted, missed

**Unsure**:
A near match on a long word, left for the parent to settle; a measuring aid in the prototype, not a product state.
_Avoid_: partial, almost

**Not attempted**:
A text word after the last word the child reached; it counts neither for nor against.
_Avoid_: skipped (a different mark)

**Engine mark**:
The mark the app gave a word in one engine run; never changed afterwards.

**Parent mark**:
The parent's judgement of a word in an attempt, shared by all engines.
_Avoid_: correction, ground truth

## Measures

**Reviewed attempt**:
An attempt whose every word the parent has judged, by marking it or by confirming it as shown. Only reviewed
attempts count toward engine accuracy.

**Mistake recall**:
The share of the parent's misread and skipped words that the app also flagged.

**False flag**:
A word the parent marked correct that the app flagged.

**Variant C / variant F**:
The same figure with unsure counted as correct (C) or as flagged (F).

**WCPM**:
Words read correctly per minute.
_Avoid_: fluency (too broad)

**Raw WPM**:
Words attempted per minute, right or wrong.

## Verification

**Test-verified**:
An automated test passed, including a headless browser with a fake microphone.

**Laptop-verified**:
Seen working in the laptop browser with the laptop microphone.

**Device-verified**:
Seen working on the phone with a real microphone. Never claimed from a laptop result.
