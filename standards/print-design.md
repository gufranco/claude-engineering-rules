# Print Design

## Scope

Loaded on demand whenever a project produces something a printer will put on
paper: a PDF, a card, a label, a ticket, a certificate, a poster, a sheet meant
to be cut up. Triggers in [`../rules/index.yml`](../rules/index.yml).

Screen output is forgiving. Paper is not: it has one size, one ink set, no
reflow, no zoom, and the person reading it cannot change the contrast. Every
rule here exists because a mistake in it is only discovered after the page is
printed, which is the most expensive moment to discover anything.

## The Five Obligations

Every printed artifact satisfies all five. They are ordered by how expensive the
failure is.

1. **It survives a grey printer.** Commercial and office printers run black and
   white far more often than anyone plans for. Nothing may be carried by colour
   alone.
2. **It survives colour blindness.** Roughly one man in twelve does not see red
   and green apart. This is the same obligation as the first, one step weaker,
   and the same fix satisfies both.
3. **It survives the trim.** A cut lands a millimetre or two off. Artwork that
   ends exactly at the trim line produces a white sliver; content that sits at
   the trim line gets cut away.
4. **It survives being scaled.** Every print dialog offers "fit to page" and
   most default to it. A scaled page looks correct and is wrong, which is the
   worst failure mode there is.
5. **It survives the reader.** Type sizes, contrast and line length chosen for a
   screen are usually wrong on paper, and a child, an older reader, or a reader
   in bad light is the case to design for.

## Never Carry Meaning In Colour Alone

The rule is absolute and it satisfies obligations 1 and 2 at once: **every
distinction a reader must make is available in at least two channels**, one of
which is not colour.

| Distinction | Colour | Second channel |
|---|---|---|
| Category, kind, type | A colour per category | A name, and a pictogram |
| A value going up or down | Green and red | An arrow's direction, a sign, a word |
| A row that needs attention | A tinted row | An icon, a rule, bold type |
| One series against another in a chart | Line colour | Dash pattern, marker shape, a direct label |
| Two variants of one thing | Two tints | A word, and a different tone of grey |

The test is mechanical: convert the artifact to greyscale. If anything becomes
ambiguous, it was carried by colour alone. Automate that test; do not rely on
remembering to look.

## Measure The Palette, Do Not Choose It By Eye

A palette that looks distinct on a calibrated monitor routinely collapses in
grey or under a colour vision deficiency. Hold the palette to numbers and put
the numbers in a test.

| Check | Threshold | Source |
|---|---|---|
| Text against its background, in colour **and** in greyscale | 4.5:1, or 3:1 at 18 pt and above | WCAG 2.2, contrast minimum |
| A pictogram or a rule against its background, both ways | 3:1 | WCAG 2.2, non-text contrast |
| Two categories that must be told apart, under normal vision and under protanopia, deuteranopia and tritanopia | 20 CIE 1976 units | The distance at which two colours read as different colours rather than two shades of one |
| Two categories printed in grey | 1.15:1 between their tones | A tonal step a reader can see |
| Two variants that share a pictogram, in grey | 1.5:1 | The tone has to carry what the shape does not |

Greyscale legibility follows from the first row for free: WCAG contrast depends
only on relative luminance, so a colour that passes against white in colour also
passes once the page is grey.

The simulation to use is the linear dichromacy approximation of Brettel, Viénot
and Mollon. Implement the arithmetic once, in the project, and hold the palette
to it in tests. Never cite an online "colour blindness checker" screenshot as
evidence; produce the number.

A palette under these constraints is usually found by search rather than by
taste. Anchor each category to a hue that means something, then optimise
lightness and saturation inside that hue until the thresholds pass.

## Bleed, Safe Area, Gutter, Marks

These four numbers are what a print shop will ask for, and a file that has them
needs no conversation.

| Measure | Value | What goes wrong without it |
|---|---|---|
| Bleed | 3 mm past the trim on every edge, for any artwork that reaches the edge | A white sliver on one side of a cut |
| Safe area | 4 mm inside the trim; nothing a reader needs goes closer | Text trimmed off |
| Gutter between pieces on a shared sheet | Twice the bleed, so each piece is cut on its own line | A sliver of the neighbour on every card |
| Crop marks | Corner ticks only, starting at the bleed edge, never lines crossing the artwork | A printed line on the finished piece |

Two shapes, both worth producing:

- **The gang-up sheet**, many pieces per page with gutters and corner marks, for
  a home printer and a guillotine. Choose the bleed to fit the gutter the page
  can afford, and say so.
- **The shop file**, one piece per page, page size equal to the piece plus 3 mm
  of bleed on each side, no marks, no rulers. This is what most printers'
  own instructions ask for, and it removes every ambiguity about what gets cut.

Reserve a band at the head and foot of a gang-up sheet for marks and notes, and
lay the grid out inside what is left. A grid centred on the full page puts the
marks on the artwork.

## Defend Against Scaling

A page printed at 96 percent is the failure nobody catches, because every
proportion still looks right. Two defences, and use both:

- **State the true size on the page.** Print a ruler with numbered divisions,
  and name the measurement of some element the reader can check with any ruler
  they have. Put both outside the trim so they leave with the offcut.
- **Say what to do.** "Print at 100 percent, turn off fit to page" in the same
  place, in every language the artifact uses.

Provide the arithmetic that turns a measurement into a correction, so a reader
who measures 96 mm on a 100 mm ruler is told to add 4 percent rather than left
to work it out.

## Type And Legibility On Paper

- **Set a floor of 8 pt for body text, 6 pt for incidental labels.** Below that,
  a home printer's dot gain closes counters and the text greys out.
- **Wrap, never clip.** Text that overflows is broken onto another line. Text
  that still does not fit is shortened with a visible mark, so a reader can see
  that something was cut rather than reading a different word.
- **Size a number to its box.** A field that can hold five digits is laid out
  for five digits, with the type shrinking to fit rather than running over.
- **Two scripts, two fonts.** Latin text and CJK text are set in faces that have
  the glyphs. Choose the face per string, not per document.
- **Embed every font.** A referenced font is substituted on someone else's
  system, silently. If a font cannot be embedded, deliver high-resolution page
  images instead and say why.
- **Convert text to outlines only when a shop asks**, and keep a text version,
  because outlined text cannot be searched, corrected or re-flowed.

## Resolution, Colour Space And Black

| Setting | Value | Why |
|---|---|---|
| Raster images | 300 dpi at final size, 600 dpi for line art and barcodes | Below 300 the halftone shows |
| Vector artwork | Preferred for anything geometric | Scales to any size with no rounding |
| Colour space | CMYK for a commercial press, RGB for home printing | An RGB file sent to a press is converted by someone else, and the colours shift |
| Rich black for large areas | C30 M30 Y0 K100 | 100 percent K alone prints as a washed dark grey |
| Small text and thin rules | 100 percent K only | Rich black needs four plates in register, and small text shows the misregistration |

State which colour space the output is in rather than leaving it to be
discovered. If a project ships RGB and a press is a possibility, say so and
offer the conversion rather than silently handing over the wrong file.

## Machine-Readable Marks

A barcode, a QR code or a data matrix on paper is a measurement, not a picture.

- **Draw it as vectors at an explicit module width.** A rasterised symbol scaled
  to fit a layout rounds its modules unevenly and stops scanning, and no test on
  the encoded digits catches it.
- **Honour the symbology's own geometry.** For EAN-13: 0.330 mm module at
  nominal, 22.85 mm bar height, quiet zones of 11 modules left and 7 right.
  Truncating the bar height is the most common and most damaging shortcut, and
  the height is the whole of the tolerance a person has when swiping by hand.
- **Verify the ink, not the string.** Rasterise the rendered page and decode the
  symbol back. A test on the digits proves nothing about what a scanner sees.
- **Verify it in greyscale too**, since that is how it will often be printed.
- **Never put anything inside the quiet zones.** Not a caption, not a border,
  not a neighbour's bleed.

## Verification

A printed artifact is not verified by reading the source. Produce the artifact
and measure it.

| Claim | Evidence |
|---|---|
| It reads in black and white | The page rendered, converted to greyscale, and checked or decoded |
| The palette is distinguishable | The contrast and difference numbers, from a test, not a screenshot |
| The barcode scans | The rendered page rasterised and decoded |
| Text is not clipped | The rendered page, with the longest real content, not a sample |
| It is the right size | A measurement off the rendered page in millimetres |
| The trim is safe | The bleed and safe area measured from the rendered page |

Keep the longest, most awkward real content in the test set: the longest name,
the longest description, the largest number, the script with the widest glyphs.
A layout verified with short sample text is not verified.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| A category, state or series distinguished only by colour | Fails in grey and fails for a colour-blind reader |
| A palette chosen by eye and never measured | Collapses in grey or under a deficiency, invisibly |
| Artwork ending exactly at the trim line | A white sliver after the cut |
| Content closer than 4 mm to the trim | Gets cut off |
| Pieces butted together with no gutter on a shared sheet | Every cut leaves a sliver of the neighbour |
| Crop marks drawn as lines across the page | They print on the finished piece |
| A grid centred on the page with marks in the margins | The marks land on the artwork |
| A page with no statement of its true printed size | A scaled print is undetectable |
| A barcode rasterised and scaled to fit | Uneven modules, and it stops scanning |
| A barcode whose bars were shortened to fit a layout | Removes the reader's whole alignment tolerance |
| A referenced, non-embedded font in a file sent to a shop | Silent substitution |
| Claiming a print works from reading the source | Nothing in the list above is visible in source |
| Body text below 8 pt, or labels below 6 pt | Closes up under dot gain |
| Text clipped rather than wrapped | The reader cannot tell something is missing |

## Cross-References

- [`../rules/accessibility-defaults.md`](../rules/accessibility-defaults.md):
  the contrast thresholds this standard applies to paper.
- [`../rules/frontend-render-gate.md`](../rules/frontend-render-gate.md): the
  same obligation for screens, that a rendered artifact is the only evidence.
- [`../rules/verification.md`](../rules/verification.md): evidence over
  assertion.
- [`accessibility-testing.md`](accessibility-testing.md): the testing
  infrastructure the colour checks belong in.

## Provenance

Promoted 2026-09-22, `single-incident`, under the fails-without-an-error-signal
condition: every failure in this standard is invisible until the artifact is
printed, and several are invisible afterwards too. Origin: a card generator
whose palette failed WCAG contrast on six of ten categories, where two
categories printed as the same grey and two collapsed to a CIE difference of 1.9
under deuteranopia, whose barcodes were drawn at 64 percent of the specified bar
height, and whose sheet butted cards together with no bleed, no gutter and crop
marks drawn across the page. Every one of those passed a source review and a
full test suite.
