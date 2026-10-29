# Compliance Defaults

Two policy locks bind every frontend task and override any laxer project convention:

1. **Strictest applicable rule wins.** When two valid compliance rules conflict, apply the stricter one.
2. **Existing rules count as in force.** A published standard, regulation, or law applies even before its effective date and outside the project's current jurisdictions.

Always loaded for UI work: [accessibility](../standards/accessibility-defaults.md), [privacy](../standards/privacy-defaults.md), [cookies](../standards/cookie-discipline.md), [cybersecurity](../standards/cybersecurity-defaults.md), [consumer](../standards/consumer-defaults.md).

Loaded on keyword match: [children](../standards/children-privacy-defaults.md), [AI](../standards/ai-compliance-defaults.md), [anti-spam](../standards/anti-spam-defaults.md), [sectoral](../standards/sectoral-compliance.md), [topical](../standards/topical-compliance.md).

Full rule, locked targets, and rationale: [`standards/compliance-defaults.md`](../standards/compliance-defaults.md). Read it before any UI task that touches a compliance domain or a locked target.
