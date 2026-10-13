from __future__ import annotations

import re
from types import MappingProxyType

Detector = tuple[str, str, re.Pattern[str], str, int]

DETECTORS: tuple[Detector, ...] = (
    (
        "SLOP001",
        "negative parallelism / corrective reframe",
        re.compile(
            r"\bnot (?:just|only|merely|simply)\b[^.\n]{0,70}?\bbut\b"
            r"|\b(?:it|this|that)'?s not\b[^.\n]{0,60}?[,.]\s*(?:it|this|that)'?s\b"
            r"|\b(?:is|are|was|were|does|do)\s+not\b[^.\n]{0,70}?\bbut rather\b"
            r"|\bmore than (?:just|merely|simply)\b"
            r"|\bless about\b[^.\n]{0,50}\band more about\b"
            r"|\b(?:isn'?t|is not|aren'?t) (?:really )?about\b[^.\n]{0,50}\bit'?s about\b",
            re.IGNORECASE,
        ),
        'State the positive claim alone. Drop the "not X" half; the reader never held X.',
        1,
    ),
    (
        "SLOP002",
        "significance inflation",
        re.compile(
            r"\b(?:stands?|serves?) as a testament\b|\bis a testament to\b"
            r"|\bplays? an? (?:crucial|pivotal|vital|key|central|significant) role\b"
            r"|\b(?:underscore|underscores|highlight|highlights)\s+the\s+"
            r"(?:importance|significance|need)\b"
            r"|\brich tapestry\b|\btapestry of\b"
            r"|\b(?:ever-)?evolving landscape\b|\bchanging landscape\b"
            r"|\bin today'?s (?:fast-paced|digital|modern|ever-changing)\b"
            r"|\b(?:left|leaves|leaving) an indelible mark\b"
            r"|\bsetting the stage for\b|\bat the forefront of\b"
            r"|\bcannot be (?:overstated|understated)\b|\bspeaks volumes\b"
            r"|\bparadigm shift\b|\bgame[- ]changer\b"
            r"|\bmarks? a (?:significant|major|key) (?:shift|milestone|turning point)\b",
            re.IGNORECASE,
        ),
        "Delete the significance clause, or replace it with the measured consequence.",
        1,
    ),
    (
        "SLOP003",
        "participial evaluation tail",
        re.compile(
            r",\s+(?:highlighting|underscoring|emphasizing|showcasing|reflecting"
            r"|symbolizing|demonstrating|solidifying|cementing|reinforcing"
            r"|signaling|underlining|illustrating|exemplifying)\b",
            re.IGNORECASE,
        ),
        "The sentence ended at the comma. Promote a real consequence to its own "
        'sentence with the mechanism named. "ensuring", "enabling" and "allowing" '
        "are excluded, since they name causation rather than significance.",
        1,
    ),
    (
        "SLOP004",
        "evasive attribution",
        re.compile(
            r"\b(?:experts|observers|critics|analysts|researchers)\s+"
            r"(?:say|says|argue|argues|agree|note|notes|suggest|suggests|believe"
            r"|have (?:cited|noted|argued))\b"
            r"|\b(?:industry reports|studies|research)\s+"
            r"(?:show|shows|suggest|suggests|indicate|indicates)\b"
            r"|\bis (?:widely|generally) "
            r"(?:considered|regarded|recognized|believed|acknowledged)\b"
            r"|\bmany (?:believe|argue|consider)\b",
            re.IGNORECASE,
        ),
        "Name the source and link it, or drop the claim. An unnamed authority "
        "cannot be checked or disputed.",
        1,
    ),
    (
        "SLOP005",
        "hedged speculation / cutoff residue",
        re.compile(
            r"\b(?:not|un)\s?-?\s?(?:publicly\s+)?"
            r"(?:documented|available|disclosed|recorded)\b"
            r"[^.\n]{0,40}[,.]?\s*(?:it|they|the)\b[^.\n]{0,30}\blikely\b"
            r"|\bwhile (?:specific|exact|precise) (?:details|information|data)\b"
            r"[^.\n]{0,60}\b(?:are|is) (?:not|un)\b"
            r"|\bas of my (?:last|knowledge|training)\b"
            r"|\bmaintains? a low profile\b",
            re.IGNORECASE,
        ),
        "Say what is unknown and stop. Asserting both that a fact is unavailable "
        "and what it probably is fabricates the second half.",
        1,
    ),
    (
        "SLOP006",
        "marketing verb replacing is/has",
        re.compile(
            r"\b(?:serves|stands|functions|operates) as (?:a|an|the)\b"
            r"|\bboasts\b"
            r"|\baims to (?:provide|deliver|ensure|offer)\b"
            r"|\bstrives to\b|\bseeks to (?:provide|deliver|ensure)\b",
            re.IGNORECASE,
        ),
        'Use "is" or "has", or name the action directly.',
        1,
    ),
    (
        "SLOP007",
        "throat-clearing / false concession",
        re.compile(
            r"(?im)^\s*(?:Look|Here'?s the thing|Let'?s be clear|Let'?s be honest"
            r"|The truth is|Make no mistake|Let'?s (?:explore|dive|unpack)"
            r"|Buckle up)[,:]"
            r"|\bto be fair,|\bcredit where (?:credit is )?due\b|\bin all fairness\b"
            r"|\bit'?s worth (?:pointing out|mentioning|remembering)\b",
            re.IGNORECASE,
        ),
        "Start with the actual point. Address a counterargument that exists, or none.",
        1,
    ),
    (
        "SLOP008",
        "trailing recap",
        re.compile(
            r"(?im)^\s*(?:In short|In summary|In conclusion|To sum up|All in all"
            r"|At the end of the day|The bottom line|Bottom line)[,:]"
            r"|\bkey takeaways?\b",
            re.IGNORECASE,
        ),
        "End when the point lands. A required TL;DR goes at the top, per "
        'CLAUDE.md "Lead with a TL;DR", never as a closing restatement.',
        1,
    ),
    (
        "SLOP009",
        "AI vocabulary cluster",
        re.compile(
            r"\bdelv(?:e|ing) into\b|\bintricacies\b|\bmeticulous(?:ly)?\b"
            r"|\bmyriad\b|\bplethora\b|\bnavigat(?:e|ing) the complexit(?:y|ies)\b"
            r"|\bunlock(?:ing)? the (?:potential|power)\b|\bharness(?:ing)? the power\b"
            r"|\bpave(?:s|d)? the way\b|\bshed(?:s|ding)? light on\b"
            r"|\bvibrant\b|\bshowcases\b|\bexemplifies\b|\bbolster(?:s|ed|ing)?\b"
            r"|\bgarner(?:s|ed|ing)?\b|\binterplay\b|\bresonates? with\b"
            r"|\bvaluable insights\b|\bseamlessly\b|\beffortlessly\b"
            r"|\bunparalleled\b|\bholistic\b|\btransformative\b"
            r"|\ba (?:wide|diverse|broad) (?:range|array|variety) of\b"
            r"|\bwhen it comes to\b|\bat its core\b|\bnestled\b"
            r"|\bpivotal\b|\bintricate\b|\bfoster(?:s|ing)\b|\btestament\b"
            r"|\bcrucial(?:ly)?\b|(?m:^\s*Additionally,)",
            re.IGNORECASE,
        ),
        "Replace each with the specific claim. Density is the signal, so this "
        "detector requires two or more distinct hits before it fires.",
        2,
    ),
    (
        "SLOP010",
        "chat residue in an artifact",
        re.compile(
            r"\bI hope this (?:helps|message finds you)\b"
            r"|\blet me know if you'?d? (?:like|want)\b"
            r"|\bfeel free to (?:adjust|customize|modify|tweak)\b"
            r"|\bhere'?s a template\b"
            r"|\byou can (?:copy and paste|customize) (?:this|it)\b"
            r"|\bas an AI\b|\bI'?m unable to browse\b",
            re.IGNORECASE,
        ),
        "Delete. Text addressed to a person mid-conversation must not survive "
        "into an artifact.",
        1,
    ),
    (
        "SLOP011",
        "unfilled placeholder",
        re.compile(
            r"\[(?:insert|your|add|company|topic)\s[^\]\n]{1,30}\]"
            r"|\bLorem ipsum dolor\b"
            r"|\b\d{4}-XX-XX\b|\bYYYY-XX-XX\b|\b20XX\b"
            r"|\[TBD:[^\]\n]{0,40}\]",
            re.IGNORECASE,
        ),
        "Fill the placeholder or remove the line. Shipping the template is "
        "shipping unfinished text.",
        1,
    ),
    (
        "SLOP012",
        "typographic residue",
        re.compile("[‘’“”′″]"),
        "Use ASCII apostrophes and quotes. Curly marks in a source file are "
        "auto-substitution residue from a chat surface.",
        1,
    ),
    (
        "SLOP013",
        "bold-label bullet in a published comment",
        re.compile(r"(?m)^\s*[-*]\s+\*\*[^*\n]{1,60}\*\*"),
        "A reply is prose, never a form. Say it in a sentence.",
        1,
    ),
    (
        "SLOP014",
        "heading inside a published comment",
        re.compile(r"(?m)^\s*#{1,6}\s+\S"),
        "A comment with sections is a summary. Answer the point and stop.",
        1,
    ),
    (
        "SLOP015",
        "search narration",
        re.compile(
            r"\b(?:refused|returned|blocked|denied|answered)\b[^.\n]{0,25}"
            r"\b(?:HTTP\s*)?(?:401|403|404|429)\b"
            r"|\b(?:HTTP\s*)?(?:401|403|404|429)\b[^.\n]{0,40}"
            r"\b(?:refused|returned|blocked|denied)\b"
            r"|\bcould not be (?:verified|confirmed|located|found|reached|fetched)\b"
            r"|\b(?:I|we) (?:could not|couldn'?t|was unable to|were unable to) "
            r"(?:find|locate|confirm|verify|access|reach|fetch)\b"
            r"|\b(?:returned|yielded|turned up)\s+no\s+(?:results|hits|matches|records)\b"
            r"|\b(?:checked|verified|confirmed|searched|fetched)\s+on\s+\d{4}-\d{2}-\d{2}\b"
            r"|\bsearch(?:es)? (?:for|of|on)\b[^.\n]{0,60}"
            r"\b(?:found|returned|turned up) nothing\b",
            re.IGNORECASE,
        ),
        "Describe what exists. A reader of the finished project needs the fact, "
        "never which sites refused, what was not found, or when a check ran. "
        "State the fact, mark it unknown, or drop the line.",
        1,
    ),
)

CONTEXT_EXCLUSIONS = MappingProxyType(
    {
        "SLOP004": re.compile(
            r"[A-Z][A-Za-z.&-]{2,}\s+(?:studies|research|reports|analysts|researchers"
            r"|experts|observers|critics)\b"
        ),
    }
)
