# compliance-pack

GDPR-grade privacy, WCAG 2.2 AA+ accessibility, ePrivacy cookies, cybersecurity, anti-spam, and AI compliance defaults bundled as a single installable plugin.

## Status

**Skeleton.** The manifest at [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) enumerates the files this plugin would distribute, but the files themselves still live in the top-level config tree. The flat layout works; the plugin extraction is a deferred follow-up.

## Policy

Two master rules govern every file in this bundle:

1. **Strictest applicable rule wins.** When two valid compliance rules conflict, the stricter applies.
2. **Existing rules are respected even when not yet mandatory.** A published standard or law is treated as if in force, regardless of effective date.

## What is included

See [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) for the full file list. Files live under [`rules/`](../../rules/), [`standards/`](../../standards/), [`hooks/`](../../hooks/), and [`agents/`](../../agents/) until the migration ships. Domains covered:

| Domain | Coverage |
|---|---|
| Accessibility | WCAG 2.2 AA mandatory, AAA where feasible; EN 301 549; mobile clauses |
| Privacy | GDPR + LGPD + CCPA family + PIPEDA + Quebec Law 25 |
| Cookies | ePrivacy opt-in default; reject-all parity; categorized consent |
| Cybersecurity | TLS 1.3, nonce-based CSP, NIST 800-63B passwords, MFA, breach notification timelines |
| Anti-spam | Opt-in everywhere; one-click unsubscribe; suppression list discipline |
| AI compliance | EU AI Act risk tiers, disclosure labels, deepfake watermarking, automated-decision rights |
| Children | UK Children's Code + California AADC + COPPA + GDPR Art. 8 + LGPD Art. 14 |
| Consumer | EU CRD 14-day withdrawal; Brazil CDC; FTC Click-to-Cancel; fake-review prohibition |

## Migration plan

When the flat-to-plugin migration ships:

1. Move the files listed in [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) into this directory under matching subpaths.
2. Update the top-level rule loader to discover via the plugin manifest.
3. Bump version to `1.0.0` and remove the `status: skeleton` marker from the manifest.

## Disclaimer

The compliance standards are technical defaults aligned with the laws referenced. They are not legal advice. A project owner consults counsel for jurisdiction-specific application.
