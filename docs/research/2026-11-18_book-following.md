# Book following: say the title, get the text, follow the child's place

Date: 2026-11-18. Status: **first pass, search summaries only.** A hook blocked the page-fetch tool for both
research agents, so no primary source was opened and nothing here is `[fetched]`. The agents' fetch tool has
since been fixed; a rerun must open the sources listed under "To verify" before any build decision.
Legal points are research, not legal advice.

**Owner decision 2026-11-18: parked until the prototype passes.** This is brief Part 1 (out of scope); a build
needs a positive prototype answer and the owner amending the brief.

## The idea (owner, 2026-11-18)

A parent or child says the book's title aloud. The app obtains the full text, finds where the child is, and
follows the reading word by word. No pasting by hand.

## Answer first

1. **Following a place in a whole book is feasible** and needs no web: index the text, shortlist positions by
   word sequences, confirm with fuzzy alignment. No published figure for how many words are needed to lock on.
2. **Getting the text automatically from the web is the weak part.** No title from a typical grade 1 or 2 list
   was confirmed as available in full on any free source, and most of those authors are still under copyright.
3. **For a commercial app, fetching books by title is not launchable** without rightsholder licences. A
   provider that takes an active part in copying cannot rely on the user's private-copy exception.
4. **The route that fits both stages is the page photo:** the parent photographs a page of a book the family
   owns, text is read from the photo on the device, nothing is stored on a server. It always matches the
   printed edition. Its accuracy on illustrated children's pages is unmeasured, and its legal footing for the
   provider is an open point for a lawyer.
5. **No existing app was found that fetches arbitrary books from a spoken title.** Reading apps use their own
   catalogue, publisher licences, or text supplied by the user.

## Law

| Point | Finding | Source (search summary) |
|---|---|---|
| Private copy from an unlicensed source | Outside the private-copying exception (CJEU ACI Adam, C-435/12). "Unlawful source" was not defined, so sites of unclear status stay uncertain. | [Kluwer](https://legalblogs.wolterskluwer.com/copyright-blog/no-more-downloading-from-unlawful-sources/) |
| Copy made by a service for the user | A provider actively involved in the copying cannot use the user's exception (VCAST C-265/16; Strato C-433/20). A passive tool might, and only from a lawful source. | [Kluwer](https://legalblogs.wolterskluwer.com/copyright-blog/up-in-the-cloud-some-reflections-on-the-cjeu-judgment-in-vcast/), [Dechert](https://www.dechert.com/knowledge/onpoint/2022/4/cjeu-rules-on-private-copying-exception-to-storage-in-the-cloud.html) |
| Storing or displaying text in a commercial app | Needs a licence. | reasoning from the above |
| Using the text only internally for alignment | Still a reproduction (the agent's reasoning, no source). | UNVERIFIED |
| Text-and-data-mining exception | Bulgaria transposed the DSM Directive on 1 Dec 2023. Weak fit: alignment is arguably not "analysis", lawful access is required, publishers can opt out. | [Kluwer](https://legalblogs.wolterskluwer.com/copyright-blog/the-last-in-line-bulgaria-implements-the-cdsm-directive/) |
| Bulgarian article for a personal copy of a literary work, and whether it allows electronic copies | Not established. | UNVERIFIED |
| chitanka.info | Servers seized in June 2010 after publisher complaints, returned days later; the ECtHR ruled in 2020 that the seizure violated rights (about the seizure, not the books). High risk for a product. | [TorrentFreak](https://torrentfreak.com/damaging-to-culture-online-library-smashed-by-police-100630/), [Capital](https://www.capital.bg/politika_i_ikonomika/pravo/2020/03/27/4047194_chitanka_osudi_gdbop_v_strasburg/) |
| Licensing practice and prices in Bulgaria | Nothing public found. | UNVERIFIED |

## Sources of text

| Source | What was found | Usable for |
|---|---|---|
| Bulgarian Wikisource | Standard MediaWiki API; needs a proper User-Agent. Holdings and per-work licences not checked. | Public-domain titles, per work |
| chitanka.info | Reported OPDS catalogue and a torrent archive; rules, robots and API not opened. | Public-domain titles only, home use |
| Project Gutenberg | A few Bulgarian titles, none for children. | no |
| Europeana / National Library | Old printed titles; full text for newspapers only. | no |
| E-book stores, Storytel | No API or DRM details found. | no |
| Google Books, Open Library | Metadata; full text only for public-domain volumes; none found for Bulgarian children's titles. | Title lookup only |

Coverage test: none of Ran Bosilek, Karaliychev, Gabe, Mileva, Raztsvetnikov, Lindgren, Collodi or folk tales
was confirmed in full on any source (search failure, not proof of absence).

## Supporting pieces

- **Spoken title to book:** fuzzy match against a small local list of titles; no web API needed. An ISBN
  barcode scan returns metadata only.
- **Edition mismatch:** no study found. Expect abridged school editions, old spelling, different translators.
  Detect by comparing the first words read with the text and by showing the first sentence to the parent.
- **Text from a photo:**
  - Tesseract and EasyOCR reportedly handle printed Bulgarian reasonably
    ([Halachev, Koychev 2026](https://jclib.dcl.bas.bg/wp-content/uploads/2026/08/JCLIB_2026_06_HalachevKoychev-ONLINE.pdf)).
  - Illustrations and decorative type are a known weak spot; no children's-book test found.
  - Google ML Kit text recognition appears not to cover Cyrillic (inferred from its language list, not opened).
  - Speed on this laptop is unmeasured.
- **Prior art:**
  - Microsoft Reading Coach takes pasted or uploaded text
    ([support page](https://support.microsoft.com/en-us/education/learning-accelerators/content-sources-supported-by-reading-coach)).
  - Amira, Epic and Google Read Along use their own or licensed libraries.

## Options

| Stage | Option | Main risk |
|---|---|---|
| Prototype | Local folder of texts (pasted or public domain) plus automatic place-finding | Does not remove the one-time step of getting the text |
| Prototype | Page photo read with Tesseract on the laptop | Accuracy on illustrated pages unmeasured |
| Product | Page photo read on the device | Accuracy; provider's legal position unsettled |
| Product | Licensed publisher catalogue | Cost and negotiation, no price known |
| Either | Automatic fetch from chitanka or stores | Legal footing weak for home use, not launchable as a product |

## To verify in a rerun

ЗАПСП articles on personal copies and text-and-data mining ([lex.bg](https://www.lex.bg/laws/ldoc/2133094401));
the three CJEU judgments on curia.europa.eu; chitanka's rules, FAQ and robots file; Wikisource holdings for
concrete titles; ML Kit and Apple Vision language lists. Measure: Tesseract on photos of a real Bulgarian
picture book; words needed to lock on to a position.

## Open points for a lawyer

1. Does Bulgarian law allow an electronic personal copy (photo, text recognition) of an owned book?
2. Does an app that reads text from the user's own photo on the device make the provider a reproducer?
3. What is the licence route and cost for modern children's texts, including illustrations and translations?
