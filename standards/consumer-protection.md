# Consumer Protection and E-commerce

## Disclaimer

This standard summarizes the obligations of EU Consumer Rights Directive 2011/83/EU + Omnibus Directive 2019/2161, EU Unfair Commercial Practices Directive 2005/29/EC, EU Digital Services Act 2022/2065 Art. 25, UK Consumer Rights Act 2015 + DMCC Act 2024, US FTC Act Section 5, US FTC Endorsement Guides + Final Rule 2024, FTC Click-to-Cancel Rule (2024), California Automatic Renewal Law BPC 17600, Brazil Código de Defesa do Consumidor (Lei 8.078/1990) + Decreto 7.962/2013, Argentina Ley 24.240, Mexico LFPC. It is a technical default, not legal advice.

## Pre-contractual Information Display

Required before purchase confirmation. Display order (top to bottom):

1. Product / service name and description
2. Total price including taxes, fees, and shipping (no hidden charges)
3. Seller legal name + registered address + contact + complaint channel (in EU: also VAT number)
4. Delivery time, return policy, withdrawal right notice
5. Payment methods accepted
6. Terms of service summary + link to full terms

Brazil Decreto 7.962 adds: CNPJ/CPF visible, max 5-day response time to complaints, contract terms summary in plain Portuguese.

## Price Transparency

```tsx
// Bad: hidden fees
<Product>
  <Price>$ 100</Price>
  <small>+ taxes + shipping at checkout</small>
</Product>

// Good: total visible upfront
<Product>
  <Price>$ 124.50</Price>
  <small>Includes $ 14.50 tax and $ 10.00 shipping</small>
</Product>
```

Total price on the first display, with optional breakdown below. Currency clearly stated. No "starting from" without showing the actual final amount before checkout.

## Withdrawal Period

| Jurisdiction | Window | Notes |
|--------------|--------|-------|
| EU CRD + Omnibus | 14 days | No reason required, full refund within 14 days of cancellation |
| UK Consumer Rights Act | 14 days | Same as EU |
| Brazil CDC Art. 49 | 7 days | Distance contracts only |
| US FTC Cooling-Off | 3 business days | Door-to-door and similar (not most online) |
| California ARL | Pro-rated refund for auto-renewals | Per BPC 17600 |

**Locked default**: 14 days, no reason required, full refund within 14 days of cancellation. Strictest-wins.

## Withdrawal UI Flow

```tsx
function WithdrawalRequest({ orderId, purchaseDate }: Props) {
  const daysSincePurchase = differenceInDays(new Date(), purchaseDate);
  const withinWindow = daysSincePurchase <= 14;

  if (!withinWindow) {
    return <p>The 14-day withdrawal period has passed for this order. You may still request a refund under our return policy.</p>;
  }

  return (
    <form>
      <h2>Cancel order {orderId}</h2>
      <p>You may cancel without giving a reason. Refund processed within 14 days.</p>
      <button type="submit">Confirm cancellation</button>
    </form>
  );
}
```

No required reason field. No retention nudge before submission. One-click confirmation.

## Click-to-Cancel (FTC 2024)

Cancellation must require no more clicks, screens, or steps than subscription. If the subscription flow is one form with one button, cancellation is the same. If subscription is online, cancellation cannot require a phone call.

```tsx
// Subscription flow: click "Subscribe" → confirmation
// Cancellation flow: must be equivalent
function ManageSubscription() {
  return (
    <button onClick={cancelSubscription}>
      Cancel subscription
    </button>
  );
}
```

## Auto-Renewal Disclosure

Per California ARL + similar state laws + EU practice:

1. Pre-purchase disclosure of auto-renewal terms (price, frequency, cancel mechanism)
2. Affirmative consent to auto-renewal (separate from purchase confirmation)
3. Reminder notice at least 3 days before renewal (some states: 7 days for annual)
4. Acknowledgment email immediately after renewal
5. Cancel anytime, pro-rated refund

```tsx
<ConsentCheckbox name="autorenew">
  Renew automatically every month at $ 9.99. You can cancel anytime.
  We will email you 3 days before each renewal.
</ConsentCheckbox>
```

Box starts unchecked. Cannot bundle with terms-of-service acceptance.

## Fake-Review Prohibition

Per FTC Final Rule (2024), EU Omnibus Directive, UK CMA + DMCC Act:

- No incentivized reviews unless the incentive is disclosed in the review
- No employee or insider reviews without explicit disclosure
- No "verified purchase" claim without actual purchase verification
- No review platform manipulation (bulk submissions, sock puppets, paid manipulation)
- No suppression of negative reviews (cannot delete, cannot hide, cannot block users from posting)

Display verified-purchase indicators. Surface review provenance ("Verified buyer" / "Influencer disclosure: this reviewer was given the product for free").

## Dark Pattern Bans

Per EU DSA Art. 25 + FTC + Brazil CDC + UK DMCC:

| Pattern | Banned because |
|---------|----------------|
| Countdown timer without genuine deadline | Fake scarcity |
| "Only 1 left!" when not true | Fake scarcity |
| Pre-selected upgrade or insurance | Defaults to higher spend |
| Confusing decline button ("No thanks, I prefer to pay more") | Confusing language |
| Subscribe trap (cannot cancel without phone) | Click-to-Cancel violation |
| Hidden costs revealed only at final step | Price transparency |
| Forced account creation for guest checkout | UX hostile + GDPR data minimization |
| Endless scroll without pagination on purchase decisions | Decision fatigue |
| Auto-converting "free trial" to paid without explicit confirmation | FTC + EU |

## Identity Disclosure

Required on every page (footer):

- Seller legal name
- Registered business address
- Contact email + form
- Complaint channel
- VAT number (EU), CNPJ/CPF (Brazil), tax ID (varies)
- Regulatory body link where applicable

## Refund Window

| Trigger | Window |
|---------|--------|
| Withdrawal within 14 days | Refund within 14 days of cancellation |
| Defective product | Refund + return shipping within 14 days |
| Service not as described | Full refund |
| Recurring charge after cancellation | Immediate refund of erroneous charge |

## Maintenance

Review this standard:

- When FTC publishes new dark-pattern, fake-review, or Click-to-Cancel guidance
- When EU Omnibus Directive 2019/2161 implementations are amended
- When UK Digital Markets, Competition and Consumers Act 2024 secondary rules land
- When Brazil ANATEL or Senacon updates e-commerce rules
- When California ARL is amended
- Yearly review on 1 January

## Related Standards

- [`../rules/consumer-defaults.md`](../rules/consumer-defaults.md)
- [`privacy-engineering.md`](privacy-engineering.md): personal data collected during purchase
- [`accessibility-testing.md`](accessibility-testing.md): checkout flow accessibility
- [`../rules/security.md`](../rules/security.md): PCI DSS for payment handling
- [`sectoral-compliance.md`](sectoral-compliance.md): financial sector specifics
