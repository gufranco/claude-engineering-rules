# Children's Privacy Defaults

## Scope

Loaded on-demand when a frontend task targets, attracts, or may be accessed by users under 18. Triggered by keywords: child, children, kid, minor, under-18, under-16, under-13, COPPA, AADC, parental consent, age gate, educational content, gaming, family. Per [`compliance-defaults.md`](compliance-defaults.md).

## Mandatory Targets

| Target | Rule |
|--------|------|
| Default consent age | 18 for all profiling, behavioral advertising, third-party data sharing |
| Account creation age | 16 minimum (15 if any EU member state with lower age applies, e.g., Spain 14) |
| Verifiable parental consent | Required under 13 always; required under 16 in some EU member states |
| Default privacy settings | Highest privacy by default for under-18: no behavioral profiling, no targeted ads, geolocation off, sharing off, search off |
| Age estimation | Behavioral signals + UI cues preferred over ID upload (data minimization) |
| Age-appropriate UI | Reading level matched to estimated age; no dark patterns; clear language |
| No behavioral advertising under 18 | Per UK Children's Code, California AADC, GDPR Children's Code |
| No nudge techniques | Per UK Code: no nudges to lower privacy, share more, stay longer |
| No real-time location to other users | Per UK Code default for under-18 |
| No streak counts, no "active now" indicators | Engagement-pressure patterns banned under UK Code for under-18 |
| Parental controls | Age-appropriate dashboard for parents to view + manage child accounts |
| Transparency notice | Plain-language child-readable privacy explanation |

## Age Threshold Matrix

| Jurisdiction | Threshold for general processing | Threshold for behavioral profiling |
|--------------|----------------------------------|------------------------------------|
| US COPPA | 13 (parental consent required under) | Same |
| EU GDPR Art. 8 (default) | 16 | Same |
| EU member state lower (Spain 14, France 15, Germany 16) | per state | Same |
| UK Children's Code | 18 for high-privacy default | Same |
| California AADC | 18 for high-privacy default | Same |
| LGPD Art. 14 | 12 child (full parental consent) / 18 adolescent (best-interest test) | Higher (no behavioral ads under 18 by AADC alignment) |
| Brazil ECA | 18 (legal minor) | Same |

**Locked default**: treat the strictest applicable age. For profiling and behavioral advertising: 18. For account creation: 16. For verifiable parental consent: 13.

## Forbidden Patterns

| Pattern | Reason |
|---------|--------|
| Behavioral advertising to users under 18 | UK Code + California AADC fail |
| Default privacy "public" for under-18 | UK Code privacy by default fails |
| Streak counts, "active now", read receipts on by default for under-18 | UK Code nudge-techniques ban |
| Geolocation tracking on by default for under-18 | UK Code |
| Real-time location visibility to other users under-18 | UK Code |
| Direct messaging from strangers to under-18 by default | UK Code |
| Mandatory ID upload as age verification | Data minimization fails when behavioral estimation suffices |
| Sign-up flow without an age field for child-likely services | COPPA + AADC fail |
| Skipping verifiable parental consent under 13 | COPPA per-violation civil penalty |
| Reusing the same data for child users that you use for adults | Children's Code + AADC fail |

## Cross-References

- [`compliance-defaults.md`](compliance-defaults.md): umbrella rule
- [`privacy-defaults.md`](privacy-defaults.md): privacy obligations
- [`../standards/children-privacy.md`](../standards/children-privacy.md): full implementation guide including age gate UI patterns, COPPA verifiable parental consent flow, UK Code 15 standards detail
- [`accessibility-defaults.md`](accessibility-defaults.md): age-appropriate UI accessibility
