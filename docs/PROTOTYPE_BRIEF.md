# Bulgarian Reading Tutor — Product Vision & Prototype Brief

## Read this first

This document has two parts:

1. **The endgame**: what the full product will eventually be. This is CONTEXT ONLY, so you make prototype decisions that won't block the real product later.
2. **The prototype**: what we are building NOW. Build only this.

Do NOT build anything from Part 1 unless it is explicitly listed in Part 2.

---

## Part 1 — The endgame (context only, do not build)

### The problem
In Bulgaria, children in 1st and 2nd grade (ages 6–8) learn to read. Practice at home matters a lot, but most parents work and can't sit with the child every day. Every summer, teachers also hand out a list of books the children must read before the next school year, and parents have no real way to know whether their child actually read them.

### The product
A mobile app (Android first, then iOS) where a child reads aloud in Bulgarian and the app:
- **Listens** to the child reading and follows along word by word.
- **Highlights** each word as it is read, like a karaoke cursor.
- **Gently flags** misread or skipped words, and lets the child tap a word to hear it pronounced correctly.
- **Encourages**: stars, streaks, simple rewards. Never harsh, never shaming.

### Key features of the full product
1. **Reading practice**: short graded texts for 1st and 2nd grade, from syllables up to short stories.
2. **Summer reading list tracker**: the parent enters the books from the teacher's list (or picks them from a catalog). The child reads them aloud page by page from the physical book, and the app logs time and progress per book.
3. **Parent daily report**: a push notification or Viber/email message, e.g. "Maria read 20 minutes today, 3 pages of 'Book title', 94% accuracy." Plus a weekly summary with progress over time.
4. **Progress tracking**: words per minute, accuracy, and problem sounds or letters over weeks and months.
5. **Profiles**: one parent account with several child profiles.
6. **Diaspora mode**: Bulgarian families abroad who want their kids to keep reading Bulgarian.
7. **Later, maybe**: a teacher dashboard where a teacher sees the class's summer reading progress.

### Business model (for context)
- Freemium: limited free practice, paid monthly or yearly subscription for parents.
- Seasonal peaks: September (school start) and June (summer reading list).
- Every year there is a new wave of 1st graders, so a steady stream of new customers.

### Non-negotiables for the full product
- **Children's data is sensitive (GDPR, extra protection for minors).** Explicit, clear parental consent. Audio is processed for scoring and not kept longer than needed. Data stays in the EU. Parents can delete everything with one tap.
- **Bulgarian first**: the whole UI is in Bulgarian, kid-friendly, big buttons, minimal text for the child.
- Works on cheap Android phones and with mediocre microphones in noisy homes.

---

## Part 2 — The prototype (BUILD THIS NOW)

### The one question the prototype must answer
**Can speech recognition reliably follow a Bulgarian child (age 6–8) reading aloud, and correctly detect their mistakes?**

If the answer is no, the whole product idea is off. So everything in the prototype serves this single test. No polish, no accounts, no payments.

### Scope
1. **A simple mobile-friendly web app** that runs on my phone's browser, so I can test with my kids right away. (The real app will be Android/iOS later; keep the core logic separate from the UI so it can be reused.)
2. **Sample texts**: 4–5 short Bulgarian texts in Cyrillic at 1st- and 2nd-grade level, from very easy (short words, simple syllables) to harder (a short paragraph). Make it easy for me to add my own text by pasting it in.
3. **Record**: one big "Start reading" button. Record from the microphone until the child presses "Done".
4. **Transcribe in Bulgarian**: compare 2–3 speech-to-text engines (for example OpenAI Whisper, Google Speech-to-Text, Azure Speech). Make switching engines a simple setting, and allow running the same recording through all engines to compare.
5. **Align and score**: match the transcript to the original text word by word and mark each word:
   - green = read correctly
   - orange = misread (show what the child actually said)
   - red = skipped
   Be tolerant of how young kids read: slow, syllable by syllable, repeating a word, self-correcting. A self-corrected word should count as correct.
6. **Results screen**: colored text, total reading time, words per minute, accuracy %.
7. **Testing log**: save every attempt (text, audio, transcript per engine, scores) so I can compare engines afterwards. A simple table view of all attempts, plus export to CSV.
8. **Manual correction**: on the results screen, let me (the parent) mark a word as actually correct or wrong. This tells us how accurate each engine really is. Show an "engine accuracy vs. my judgment" number per engine.

### Optional, only if the core works well
- **Live word highlighting** while the child reads (streaming recognition). Note how hard it is and what latency we get, because this matters a lot for the full product.

### Explicitly OUT of scope for the prototype
- User accounts, child profiles, login
- Payments or subscriptions
- Summer reading list tracker
- Parent reports and notifications
- Native Android/iOS app
- Visual design polish, animations, rewards

### Privacy, even in the prototype
- Recordings of my children stay **local only** (on the device or my local machine). Nothing public, no public URLs.
- If a cloud speech API is used, use an EU region where possible and do not enable any setting that lets the provider keep or train on the audio.
- A visible "Delete all recordings" button.
- API keys go in a local env file, never in the frontend code or the repo.

### What I want from you, step by step
1. Propose a tech stack and a short plan before writing code. Keep it simple.
2. Build the minimal record → transcribe → score loop with ONE engine first, so I can test quickly.
3. Then add the other engines and the comparison log.
4. At the end, give me a short testing checklist: how many recordings, which kinds of texts, and what accuracy numbers would mean "good enough to build the real app".
