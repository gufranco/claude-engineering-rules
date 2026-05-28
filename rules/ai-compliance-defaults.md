# AI Compliance Defaults

## Scope

Loaded on-demand when a frontend task uses any AI feature: LLM chatbot, recommender, ranking model, automated decision, generative content, deepfake detection, hiring tool, credit scoring, content moderation, biometric ID, predictive analytics. Triggered by keywords: ai, llm, chatbot, recommender, generative, gpt, claude, anthropic, openai, deepfake, automated decision, model output, ml model. Per [`compliance-defaults.md`](compliance-defaults.md).

## Mandatory Targets

| Target | Rule |
|--------|------|
| Risk classification | Every AI feature classified per EU AI Act: prohibited, high-risk (Annex III), limited-risk (transparency), minimal-risk |
| Prohibited uses (EU AI Act Art. 5) | Never deploy: social scoring by public authorities, real-time biometric ID in public spaces (limited exceptions), exploitation of vulnerabilities, manipulative subliminal techniques, emotion recognition in workplace/education, predictive policing based on profiling alone |
| High-risk obligations | Conformity assessment, technical documentation, human oversight, accuracy + robustness + cybersecurity, logging, post-market monitoring |
| Disclosure tag | Every model-produced user-facing output carries a visible AI disclosure label |
| Chatbot identification | Bot identifies its nature on first interaction; never deceives the user about being human |
| Deepfake watermark | Generated audio, video, or images bearing photorealistic likeness include a permanent watermark |
| Automated decision UI | GDPR Art. 22 + LGPD Art. 20 + Colorado AI Act: human review available, plain-language explanation, appeal mechanism |
| Bias audit | Annual for any automated decision system; NYC LL 144 standard; results published when affecting users |
| Transparency notice | Per-feature: purpose, data used, decision logic summary, human contact path |
| Training data transparency | California AB 2013: large GenAI providers disclose training data sources |
| GPAI provider compliance (EU AI Act Ch. V) | From 2 Aug 2025: codes of practice, technical documentation, copyright policy |
| Logging | Decision logs retained per regulatory requirement (high-risk: 6 months minimum) |

## EU AI Act Implementation Phases (Verified)

| Phase | Date | What applies |
|-------|------|-------------|
| Entry into force | 1 Aug 2024 | No requirements yet |
| Article 5 prohibitions + AI literacy | 2 Feb 2025 | Banned uses become enforceable |
| GPAI + governance + notified bodies | 2 Aug 2025 | General-purpose AI obligations begin |
| High-risk most obligations | 2 Aug 2026 | Annex III systems comply |
| Article 6(1) + post-market | 2 Aug 2027 | Final transitional provisions |

## Forbidden Patterns

| Pattern | Reason |
|---------|--------|
| Rendering model output without a disclosure label | EU AI Act Art. 52 + California SB 942 + Brazil PL 2338 |
| Chatbot pretending to be human | EU AI Act Art. 52 transparency obligation |
| Automated decision with legal/significant effect without human review path | GDPR Art. 22 + LGPD Art. 20 |
| Emotion recognition in employment or education | EU AI Act Art. 5 prohibition |
| Social scoring | EU AI Act Art. 5 prohibition |
| Real-time biometric ID in public space (commercial) | EU AI Act Art. 5 prohibition |
| Deploying high-risk AI in scope without conformity assessment | EU AI Act |
| Hiring algorithm without annual bias audit | NYC LL 144 + Colorado AI Act |
| Algorithm for consequential decisions without notice to affected users | Colorado AI Act |
| Training data scraped from non-public sources without lawful basis | GDPR + LGPD + AB 2013 |
| LLM output rendering with no `aria-live` region for streaming | Accessibility cross-rule |
| Generative image/video/audio output without permanent watermark when depicting a real person | Deepfake disclosure |

## Mechanical Enforcement

The hook [`../hooks/ai-disclosure-checks.py`](../hooks/ai-disclosure-checks.py) catches:
- Model output rendering (variables like `aiResponse`, `llmOutput`, `generated`) without a surrounding disclosure label
- Chatbot UI component instantiation without a nearby "AI" / "powered by AI" label

Bypass env: `AI_DISCLOSURE_DISABLE=1` (parent shell only).

## Cross-References

- [`compliance-defaults.md`](compliance-defaults.md): umbrella rule
- [`../standards/ai-compliance.md`](../standards/ai-compliance.md): full implementation guide with risk-tier matrix, transparency notice template, automated decision UI patterns, deepfake disclosure UX
- [`../standards/mcp-security.md`](../standards/mcp-security.md): MCP server security + OWASP LLM Top 10 (2025) developer-side
- [`privacy-defaults.md`](privacy-defaults.md): GDPR Art. 22 + LGPD Art. 20 automated decision rights
- [`accessibility-defaults.md`](accessibility-defaults.md): `aria-live` for streaming model output
