# Consumer and E-commerce Defaults

## Scope

Every frontend task that sells, subscribes, distributes goods or services, or solicits user contracts. Loaded by default per [`compliance-defaults.md`](compliance-defaults.md). Strictness target: EU Consumer Rights + Omnibus, with Brazil CDC overlay where the project serves Brazilian users.

## Mandatory Targets

| Target | Rule |
|--------|------|
| Withdrawal period | 14 days minimum for distance-sale contracts, no questions asked |
| Pre-contractual information | Display before purchase: total price (incl. taxes + delivery + fees), product description, seller identity + address, complaint channel, withdrawal right notice |
| Price transparency | Total price including taxes and fees shown on the first display, not buried at checkout |
| Subscription auto-renewal disclosure | Pre-renewal notice; cancel-anytime; pro-rated refund |
| Click-to-Cancel | Cancellation requires the same number of clicks as subscription |
| Fake-review prohibition | No incentivized reviews without disclosure; verified-purchase indicators required; no review-platform manipulation |
| Dark pattern prohibition | No countdown timers without genuine deadline; no pre-selected upgrades; no confusing decline buttons |
| Brazilian e-commerce (Decreto 7.962) | Visible CNPJ/CPF, address, contact form, max 5-day response, 7-day withdrawal (longer than EU's 14 wins via strictest-wins) |
| Refund window | Refund within 14 days of cancellation/withdrawal |
| Receipt and confirmation | Email confirmation on every order including contract terms, total paid, complaint channel |
| Identity disclosure | Seller's legal name + contact + complaint channel visible from every page (typically in footer) |

## Forbidden Patterns

| Pattern | Reason |
|---------|--------|
| Total price only at the final checkout step | EU CRD Art. 5 fails |
| "Free trial" auto-converting to paid without explicit confirmation | EU + FTC dark patterns |
| Hidden fees (shipping, tax, processing) revealed after click | EU Omnibus + FTC fail |
| Cancel-by-phone-only when sign-up is online | FTC Click-to-Cancel fails |
| Confusing decline buttons (small, grey, "No thanks I prefer to pay more") | EU + FTC |
| Pre-selected add-ons (insurance, extended warranty) | EU Omnibus + FTC |
| Fake scarcity ("only 1 left!" when not true) | EU Unfair Commercial Practices |
| Fake reviews or incentivized reviews without disclosure | FTC + EU Omnibus + Brazil Senacon |
| Withdrawal request requiring a reason | EU CRD: no reason required |
| Cancellation taking >14 days to process refund | EU CRD + Brazil CDC |

## Cross-References

- [`compliance-defaults.md`](compliance-defaults.md): umbrella rule
- [`../standards/consumer-protection.md`](../standards/consumer-protection.md): full implementation guide with code patterns
- [`privacy-defaults.md`](privacy-defaults.md): personal data collected during purchase
- [`accessibility-defaults.md`](accessibility-defaults.md): checkout flow accessibility
