# Topical Compliance

## Disclaimer

This standard summarizes topical regulations that may apply depending on the platform's audience and content. It is a technical default, not legal advice. The topical rules layer on top of the always-loaded compliance domains.

## EU Digital Services Act (Regulation 2022/2065)

### Applies to

Online intermediaries serving EU users. Specific scopes:

- **All intermediary services**: terms of service, transparency
- **Hosting services**: notice-and-action
- **Online platforms**: contact point, internal complaint mechanism, dispute resolution, dark pattern bans (Art. 25)
- **Very Large Online Platforms (VLOPs, > 45M EU users)**: risk assessment, audit, recommender transparency, ad repository, researcher access

### Required UI

#### Notice-and-action (Art. 16)

```tsx
function ReportContent({ contentId }: Props) {
  return (
    <form>
      <h2>Report this content</h2>
      <select name="reason">
        <option value="illegal">Illegal content under EU or national law</option>
        <option value="terms">Violates the platform's terms</option>
        <option value="ip">Intellectual property infringement</option>
        <option value="other">Other</option>
      </select>
      <textarea name="details" required />
      <input type="text" name="reporterContact" placeholder="Email for follow-up (optional)" />
      <ConsentCheckbox name="goodFaith">
        I declare in good faith that the information is accurate and complete.
      </ConsentCheckbox>
      <button type="submit">Submit notice</button>
    </form>
  );
}
```

Acknowledgment of receipt within reasonable time. Decision and reasoning communicated to the reporter and the affected user.

#### Statement of Reasons (Art. 17)

Every content moderation decision (removal, demotion, suspension, demonetization) requires a statement of reasons sent to the affected user:

- The specific provision violated
- The factual basis
- The action taken
- Available redress paths
- Submitted to the EU Transparency Database

#### Internal Complaint Mechanism (Art. 20)

Free, accessible, easy-to-use mechanism to appeal moderation decisions within 6 months.

#### Recommender Transparency (Art. 27 + VLOP Art. 38)

Display the main parameters of any recommender system (sorted feed, suggested content, search ranking). Allow users to switch to a non-personalized variant.

```tsx
<SortControl>
  <Option value="recommended">Recommended for you</Option>
  <Option value="recent">Most recent</Option>
  <Option value="popular">Most popular</Option>
</SortControl>
```

#### Transparency Report (Art. 15)

Published at least annually:

- Content moderation orders received from EU authorities
- Notices received via Art. 16
- Decisions made (removal, demotion, ban, etc.)
- Use of automated content moderation
- Out-of-court dispute settlement
- Suspensions of users

#### Dark Pattern Bans (Art. 25)

Per DSA Art. 25: platform interface must not deceive, manipulate, or otherwise impair the user's ability to make free informed decisions. Cross-reference: [`consumer-protection.md`](consumer-protection.md) dark pattern section applies.

## Germany NetzDG (Network Enforcement Act)

### Applies to

Social networks with 2M+ registered users in Germany.

### Mandatory targets

- **24-hour removal SLA** for manifestly unlawful content
- **7-day removal SLA** for other unlawful content
- **Easily recognizable, directly accessible, and permanently available** reporting form
- **Quarterly transparency report**

NetzDG complaint form must be reachable in one click from any page, identified as a NetzDG complaint, and processable without account creation.

## Government Transparency: FOIA + LAI + EU Reg. 1049/2001

### Applies to

Public-sector bodies and contractors handling government information.

### Mandatory targets

| Source | Window | Scope |
|--------|--------|-------|
| US FOIA (5 USC 552) | 20 working days | Federal agencies + records |
| Brazil LAI (Lei 12.527/2011) | 20 days | Federal + state + municipal |
| EU Regulation 1049/2001 | 15 working days | EU institutions documents |
| UK FOIA 2000 | 20 working days | Public authorities |

**Locked default**: 15 working days. Strictest-wins.

### UI pattern for public-sector site

```tsx
function TransparencyRequest() {
  return (
    <form>
      <h2>Solicitação de Acesso à Informação / Information Request</h2>
      <fieldset>
        <legend>Your request</legend>
        <textarea name="request" required minLength={20} maxLength={5000} />
        <p>We will respond within 15 working days.</p>
      </fieldset>
      <fieldset>
        <legend>Receive the response</legend>
        <input name="email" type="email" required />
        <input name="postalAddress" />
      </fieldset>
      <fieldset>
        <legend>Identification (optional under most laws)</legend>
        <input name="name" />
        <p>Most laws permit anonymous requests.</p>
      </fieldset>
      <button type="submit">Submit request</button>
    </form>
  );
}
```

## Open Data

### Applies to

Public-sector bodies covered by EU Open Data Directive 2019/1024, US OPEN Government Data Act, Brazil Plano de Dados Abertos, etc.

### Mandatory targets

- **Machine-readable formats**: CSV, JSON, RDF preferred; PDF not sufficient
- **Open licenses**: Creative Commons CC0 or CC-BY for content; OGL or PDDL for data
- **Metadata standard**: DCAT-AP (EU), DCAT-US, dataset.json (US)
- **Direct download**: no scraping required, no API keys for public datasets, no rate limits below reasonable use
- **Update cadence**: documented and respected
- **High-value datasets** (EU Implementing Regulation 2023/138): geospatial, earth observation, meteorological, statistics, companies, mobility

### Dataset metadata template

```json
{
  "@context": "https://www.w3.org/ns/dcat",
  "@type": "Dataset",
  "title": "...",
  "description": "...",
  "publisher": "...",
  "license": "https://creativecommons.org/licenses/by/4.0/",
  "issued": "2026-01-01",
  "modified": "2026-05-27",
  "frequency": "monthly",
  "distribution": [
    { "format": "CSV", "downloadURL": "..." },
    { "format": "JSON", "downloadURL": "..." }
  ]
}
```

## Election Advertising (EU Reg. 2024/900)

### Applies to

Political advertising in EU member states. Phased application October 2025 to October 2026.

### Mandatory targets

- **Sponsor identification**: legal name + contact of the sponsor
- **Payment source disclosure**
- **Targeting criteria disclosure** for online ads
- **Public repository** of political ads with all metadata
- **No targeting based on sensitive personal data** unless explicit consent
- **No targeting of minors** with political ads

## Content Moderation Appeal

Per DSA + NetzDG + national laws:

- Notify affected user of the decision + reasoning
- Provide an internal appeal channel (free, accessible)
- Decision on appeal within 6 months (DSA Art. 20)
- Option to escalate to certified out-of-court dispute settlement body (DSA Art. 21)
- Statistics on appeals in the transparency report

## Geolocation as Sensitive

### Applies to

Per Washington My Health My Data Act + several US state laws + GDPR Art. 9 (when revealing health, racial origin, or religion):

- Precise geolocation (more granular than approximate region) treated as sensitive personal data
- Specific consent required for collection
- Truncate to city or region level when full precision is not needed
- Never transmit precise location to ad networks
- Document retention specific to geolocation (shorter than general personal data)

```typescript
function truncateLocation(lat: number, lon: number, precision: "city" | "region" | "country"): [number, number] {
  switch (precision) {
    case "city":    return [Math.round(lat * 100) / 100, Math.round(lon * 100) / 100];
    case "region":  return [Math.round(lat * 10) / 10, Math.round(lon * 10) / 10];
    case "country": return [Math.round(lat), Math.round(lon)];
  }
}
```

## Maintenance

Review this standard:

- When the EU Commission designates new VLOPs/VLOSEs under DSA
- When DSA implementing regulations are adopted
- When Germany updates NetzDG
- When EU Regulation 2024/900 political-ad phase milestones land (October 2025, October 2026)
- When Brazil LAI is amended or new STF rulings interpret it
- When EU Open Data Directive implementing regulations expand high-value datasets
- When Washington My Health My Data Act is amended
- When new US state geolocation-as-sensitive laws pass
- Yearly review on 1 January

## Related Standards

- [`../rules/compliance-defaults.md`](../rules/compliance-defaults.md)
- [`consumer-protection.md`](consumer-protection.md): DSA Art. 25 dark pattern cross-reference
- [`privacy-engineering.md`](privacy-engineering.md): sensitive data treatment for geolocation + political ads targeting
- [`ai-compliance.md`](ai-compliance.md): recommender system transparency cross-references AI Act
