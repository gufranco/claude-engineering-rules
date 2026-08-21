# Hardware Fidelity

Standards for modelling real silicon: a processor, a coprocessor, a mapper, a sound
chip, a console. Written out of the SNES coprocessor projects, and meant to be
followed by every project in that family rather than re-derived each time.

The subject of these rules is a part that physically exists. That is what makes
them different from ordinary software standards: there is a right answer, it was
decided in a fab decades ago, and it is not a matter of design taste. The whole
job is finding out what it is and refusing to guess.

## The authority ladder

Every factual question about a part is answered by the highest available rung, and
a lower rung never overrules a higher one.

| Rung | Source | Answers |
|---|---|---|
| 1 | Manufacturer documentation: datasheet, user manual, data book, errata | Anything the manufacturer printed. Widths, memory sizes, stack depth, clocks per instruction, reset behaviour, pin function, timing figures |
| 2 | The part itself: a measurement off real silicon, or the behaviour of the part's own program run on a model of its documented architecture | Behaviour the documentation does not specify, where the artefact is in hand |
| 3 | A recording taken from an existing independent implementation, pinned to a commit, made before the local implementation existed | Instruction-level behaviour nobody documented: exact flag rules, undefined encodings, the result of every field combination |
| 4 | Nothing else | Nothing |

**An emulator, an FPGA core, a wiki, a forum post and a decompilation are all rung
3 at best, and rung 4 for any fact the manufacturer printed.** They are useful and
they are not authorities. Widely used does not mean correct: an emulator that has
shipped for twenty years with a wrong stack depth has shipped a wrong stack depth
twenty years running, because no game happened to depend on it.

When rung 1 and rung 3 disagree, rung 1 wins and the recording is retaken. Record
that this happened, loudly, in the commit and in the file, because a corpus that
changed is a claim that changed.

## Find the document

Before modelling anything, look for the manufacturer's document. It usually
exists, scanned, on a components archive, a museum site, or bitsavers. A part
number plus "datasheet" or "data book" finds it more often than not.

Read it rather than searching within it. A search engine's summary of a datasheet
is a rung-4 source about a rung-1 document, and it conflates parts: a summary
that quotes a 250 ns instruction cycle for a family whose later member runs at
122 ns has silently handed over the wrong part. Scanned pages are images, so read
the pages.

Read all of it, page by page, rather than enough of it. The facts worth having are
the ones an implementation is most likely to have wrong because no software depends
on them, and they are never where a search would look: stack depth, pointer widths,
what reset does, what is not connected, and the table of differences between one
revision and the next. A datasheet read in full has repeatedly produced a defect
per reading; the same datasheet searched produced none.

### When the document contradicts itself

It will. A vector table that prints one mode's addresses under the other mode's
heading, a timing chart that names different addresses from the caveats table in
the same document, a cycle count that its own enhancements table disagrees with.

The passage closest to the silicon wins. Cycle tables, pin descriptions and
tables of differences between revisions have each been right where the summary
table and the prose were wrong. Prose is written last and reviewed least.

Do not resolve the contradiction quietly. Record both readings, which one the
model follows, and what would settle it. A reader who finds the printed table and
the code disagreeing needs to know somebody noticed.

## Pin the document as a checkable artifact

Prose citation rots and cannot be tested. Put the figures in a data file that
ships with the project, one entry per fact, each carrying:

- the value,
- **the verbatim sentence or table row it came from**,
- the document's publisher, title, kind, date, and the date it was read,
- corroboration from elsewhere in the document, when there is any,
- an explicit `notStated` note for anything the document does not say, where the
  model has to infer.

Then write a test that the model's own constants match that file. The document
stops being a memory and becomes a gate.

```
conformance/hardware.json     what the manufacturer says the part is
conformance/corpus.json       what the part does where the document is silent
conformance/pinned.json       which implementation the corpus was recorded from
```

**Mark an unverified part unverified.** When no document has been found, say so in
the file: what is asserted, by whom, what the project uses, why, what would settle
it. A part quietly given an emulator's number is indistinguishable from a part
given a manufacturer's number, and that is the failure this file exists to stop.

## Distinguish the inference from the fact

A document gives a width; the consequence of exceeding that width is often
unstated. Model the consequence, and label it as an inference from the width
rather than as something the document prints. A reader must be able to tell which
of the two they are relying on without going back to the page.

## Measure the artefact when you hold it

The strongest evidence short of the manufacturer is the part's own program. When
the firmware or the cartridge is in hand, a question about what the hardware needs
can often be answered by running it and counting, rather than argued about.

Establishing that no shipped program in a family ever pushes past the fourth stack
slot is worth more than any opinion about what the fifth push does, and it turns a
risky correction into a safe one. Make the measurement repeatable and keep it in
the project, so the claim is re-derivable rather than a sentence in a commit
message.

## Cycle accuracy

The phrase means nothing until three things are stated.

1. **Clocks per instruction, from the document.** Where every instruction takes
   the same number of cycles, an instruction-stepped model is already
   cycle-stepped and the only missing thing is the citation and a counter. Where
   instructions differ, a per-instruction cycle table is required and the model
   has to carry it.
2. **The clock rate, and whose it is.** The chip's rated maximum is a property of
   the chip; the oscillator on a particular board is a property of that board.
   They are different numbers and must not be conflated.
3. **What is not deterministic.** Two independent oscillators have no fixed phase
   relationship, so the number of cycles one part executes between two accesses by
   another is not a fixed quantity on real hardware either. A model that reports a
   single number there is reporting a floor or an average, and must say which.

Expose a cycle count that a caller can read. A cycle claim nobody can observe is
not a claim.

**A cycle count is not cycle accuracy.** A model can spend the right number of
cycles doing the wrong thing, and no count will show it. On a part that drives a
bus every cycle, what makes the claim checkable is the sequence: the address, the
value, read against write, in order, and on a part with output pins their state
too. Compare that, not its length.

The difference is not academic. Holding one processor family to its recorded bus
found a documented dummy read at the wrong address on every taken branch, a
read-modify-write that wrote once where the part writes twice, a spare cycle that
crossed a bank boundary the program counter cannot cross, and a stack push that
folded where the part steps through. Every one of those passed a state comparison
and would have passed a count.

Where a cycle carries no valid address, record that rather than inventing one. A
part that lowers its address lines is telling a device nothing is being asked of
it, and a model that drives a plausible address there has invented a bus cycle.

## A gate names what it covers and refuses the rest

A conformance runner asked about a part it has never been held to has three
options, and two of them are lies. Reporting agreement is a lie about the part.
Skipping in silence is a lie about the run, because the summary line then counts a
comparison that never happened.

The third is to refuse: name the parts the runner has been held to, refuse anything
else, and say what is missing. Make the list a constant so adding a part is a
deliberate edit rather than a side effect.

The same applies inside a run. Cases the comparison cannot settle are counted apart
and named in the output, never folded into the agreements and never dropped. A part
that halts drives its bus for as long as the recording happens to run, which is a
property of the recording; an internal cycle with no address to compute carries
whatever the recorder put there, which is a property of the recorder. Both are
excluded and both are reported, so a reader can see the size of what was not
checked.

## Never start clean

Registers, memory, flags and stacks hold what the previous power cycle left. A
model that starts at zero passes its tests and diverges on real hardware, and it
hides exactly the class of bug that only appears there. Fill every store from a
seed, make the seed reproducible, and never fix a failing test by clearing state.

## The program is the behaviour

Where a part's function is a program masked into it, run the program. Never write
a table of what each command does. Such a table is a second answer that will drift
from the first, it cannot be checked against anything, and it is usually wrong at
the edges, which is where a real cartridge sends the part.

A corollary: never invent inputs. What a program is asked is written down in the
software that asks it. Read that out, and drive the part with it.

## Evidence discipline

- **Exhaust rather than sample where enumeration is possible.** Every field of
  every instruction form. Every command byte. A sampled sweep reports the ground
  it happened to touch as though it were the space.
- **Two implementations of deliberately different shape**, one table-driven and
  one branching, both held to a third-party recording. Implementations sharing a
  shape share a mistake.
- **Run beyond the fixed corpus.** A recording has a size; derive cases from an
  index instead, so any case is reachable and repeatable, and run without bound.
- **Say what each piece of evidence is worth.** Agreement between two
  implementations by one author is not evidence about hardware. State the ceiling.
- **Never let a test matrix pass as a requirement.** What was tried and what is
  required are two claims, and the second is derived from the code, not from what
  happened to be run.
- **Report per-part strength, not an average.** One part driven by twenty-nine
  cartridges and another by one are not one number.

## Artifacts the project cannot ship

A ROM, a firmware image, a BIOS, a disc image: needed, not distributable, not
regenerable. Full treatment in [`artifact-identity.md`](../rules/artifact-identity.md);
the fidelity-specific parts:

- SHA-256 decides. Size, CRC32, MD5 and SHA-1 are published beside it for
  cross-checking against public databases, and decide nothing.
- Every digest records its provenance: which database, which version, or that it
  was computed from a local copy on a date. A digest without provenance attests to
  one machine.
- Known bad dumps are declared separately, so a failure can say the dump is
  corrupt rather than merely wrong.
- Diagnose, then offer repair: a header to strip, an archive member to extract, a
  byte order to swap. Never a download, never a link, never a hint.
- Verify the exact bytes that will be consumed, before consuming them. Confirming
  a file and then reopening it is a time-of-check gap.
- Only retail dumps. A ROM hack is not a reference: it is somebody's edit, and a
  protocol read out of it is not a protocol any hardware ever spoke.

## Gates

The same gates as any other project, plus the ones this domain needs.

| Gate | Requirement |
|---|---|
| Coverage | 100% statement and branch, enforced by config rather than aspired to |
| Machine independence | Coverage that depends on what a machine holds is not coverage. Run the suite with every artifact directory pointed somewhere empty, and check it still passes |
| Types | Strict, plus every optional error class the checker offers |
| Oldest runtime | Run on the oldest version supported, not only the newest. Language semantics differ, and the newest is the most forgiving |
| Exhaustive conformance | The full sweep runs on every push, not nightly |
| Unbounded conformance | On a schedule, starting somewhere different each run |
| Re-validation | Weekly, against unpinned tools and the newest runtime, since a part that stopped changing sits on an ecosystem that did not |
| Artifact-dependent checks | Report as skipped, never as passed. Exit with a distinct code and have CI treat it as a notice |

## Forbidden patterns

| Pattern | Reason |
|---|---|
| Taking a figure from an emulator that the manufacturer printed | Rung 4 overruling rung 1 |
| A datasheet figure quoted in prose with nothing checking it | Rots, and cannot fail |
| Adopting a secondary value for an unverified part without marking it unverified | Makes a guess indistinguishable from a fact |
| Claiming cycle accuracy without a clocks-per-instruction citation | The claim has no content |
| Conflating a chip's rated clock with a board's oscillator | Two different numbers |
| Describing what a command does when the part's own program decides | A second answer that will drift |
| Inventing an input sequence to drive a part with | Asks a question no hardware was ever asked |
| Starting memory or registers at zero | Hides the class of bug that only appears on hardware |
| A test that reaches a default which opens a real artefact | Passes where the file is, fails where it is not, and gives no local hint |
| One headline number over parts with very different evidence | Reads as uniform when it is not |
| Committing, vendoring, encoding or generating a non-distributable artefact | Redistribution, whatever it is wearing |

## Project conventions for this family

| Thing | Rule |
|---|---|
| Language | Python only, for the SNES family |
| Package manager for tooling | pnpm, never npm |
| Comments | None in source. Docstrings carry the reasoning, and say why rather than what |
| Test layout | `<module>.test.py` beside the module it covers |
| Test structure | Arrange, blank line, one act, blank line, assert. No section labels |
| Artifacts on disk | Inside the project, gitignored, with the README stating they are not shared and why |
| Digests in the README | Published, so a user can confirm their own copy |
| Releases | semantic-release, tags only. Consumed as a git submodule rather than from a package index |
| Agent instructions | `AGENTS.md` at the repository root, with each tool's own entry point pointing at it rather than repeating it |

## Cross-References

- [`../rules/artifact-identity.md`](../rules/artifact-identity.md): the full artifact-identity discipline this narrows.
- [`../rules/verification.md`](../rules/verification.md): what counts as evidence, and the tested-set-is-not-the-required-set rule.
- [`../rules/found-fix.md`](../rules/found-fix.md): a defect surfaced by any check is in scope now.
- [`user-supplied-artifacts.md`](user-supplied-artifacts.md): manifest schema and canonicalization.
- [`../rules/normative-keywords.md`](../rules/normative-keywords.md): the obligation vocabulary used above.

## Worked example

The two reference implementations of this standard:

- `nec-upd7725-python`: the processor. `conformance/hardware.json` pins the NEC
  datasheet fact by fact with quotes; `corpus.json` holds recordings from an
  independent implementation; `differential.py` runs the two local
  implementations against each other without bound.
- `snes-dsp-python`: the parts that processor becomes, each running the microcode
  a user supplies, driven by exchanges read out of thirty-six real cartridges.

Both were held to this file, and both had defects that only the datasheet found.
