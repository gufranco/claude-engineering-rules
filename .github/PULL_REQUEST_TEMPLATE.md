## Summary

<!-- What changes and why, in two to four sentences. A reviewer who reads only
this should understand the change and what it asks of them. -->

## Type

<!-- The commit type decides the released version. Check exactly one. -->

- [ ] `feat`: new rule, standard, skill, hook, or agent (minor release)
- [ ] `fix`: corrects wrong behavior (patch release)
- [ ] `perf`: same behavior, faster (patch release)
- [ ] `refactor`: restructuring, no behavior change (patch release)
- [ ] `docs`, `test`, `build`, `ci`, or `chore`: no release
- [ ] Breaking change: reverses prior guidance, removes a bypass, or blocks
      something previously allowed

## Reasoning

<!-- Source carries no comments in this repository, so the reasoning a comment
would have held goes here. What alternatives were rejected, and why. -->

## Evidence

<!-- Paste real output. "Should pass" is not evidence. -->

```
make test-all
```

## Checklist

- [ ] `make test-all` passes locally, output pasted above
- [ ] Coverage on changed files is at or above 95%
- [ ] New rule or standard is registered in [`rules/index.yml`](../rules/index.yml)
- [ ] New hook has tests for the block case, the allow case, and the bypass
- [ ] New hook is wired in [`settings.json`](../settings.json) and documented in [`README.md`](../README.md)
- [ ] Counts in [`README.md`](../README.md) updated if a rule, standard, skill, hook, or agent was added
- [ ] Every file mention in changed Markdown is a link
- [ ] No source comments added, except tool directives
- [ ] No AI attribution and no workflow process language anywhere in the diff
- [ ] [`CHANGELOG.md`](../CHANGELOG.md) entry added if the change is substantial

## Related

<!-- Closes #123 -->
