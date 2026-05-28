# Sectoral Compliance

## Disclaimer

This standard summarizes obligations across seven regulated sectors. It is a technical default, not legal advice. The sector-specific rules layer on top of the always-loaded compliance domains (accessibility, privacy, cookies, cybersecurity, consumer). When the project keyword matches a sector, this standard loads.

## Health (HIPAA + GDPR Art. 9 + LGPD Art. 5)

### Applies when

Any feature handles Protected Health Information (PHI): name + health condition, treatment, payment for health care, body measurements linked to identity, mental health records, genetic data, biometric used for identification, prescriptions, medical imaging, vital signs telemetry.

### Mandatory targets

- **HIPAA Security Rule technical safeguards**: access control (unique user identification, automatic logoff, encryption + decryption), audit controls, integrity controls, person-or-entity authentication, transmission security
- **End-to-end encryption** for PHI messaging
- **No analytics or marketing pixels** on pages displaying PHI (HHS guidance, FTC enforcement against meta pixel on health portals)
- **BAA (Business Associate Agreement)** signed with every vendor that handles PHI on the controller's behalf
- **Breach notification**: HIPAA 60 days for individuals + media (if 500+ in a state) + HHS portal
- **GDPR Art. 9**: explicit consent for health data (special category)
- **LGPD Art. 5(II)**: sensitive data requires specific consent + enhanced protection
- **Retention**: HIPAA records 6 years minimum from creation or last effective date
- **Patient access** to records (HIPAA Right of Access) within 30 days

### EU European Health Data Space (Regulation 2024/2228)

In force 2025. EHR vendor obligations: interoperability, primary use (patient care) and secondary use (research) data flows, patient opt-out for secondary use.

### Brazil specifics

- LGPD Art. 5(II) sensitive data
- CFM Resolução 2.314/2022 telemedicine
- Marco Civil applies to digital health platforms

## Financial (PCI DSS 4.0 + PSD2 + GLBA)

### Applies when

Any feature accepts, processes, transmits, or stores cardholder data; any feature provides payment services; any feature is offered by a financial institution under GLBA scope.

### Mandatory targets

- **PCI DSS 4.0 client-side script management** (Req. 6.4.3 + 11.6.1, mandatory 31 March 2025):
  - Inventory of every script on cardholder-data pages
  - Justification of business need for each script
  - Tamper detection mechanism (hash, SRI, or change-detection service)
  - Alerting on unauthorized script change
- **PSD2 SCA (Strong Customer Authentication)**: two of three factors (knowledge, possession, inherence) for online payments and account access from EU
- **PSD2 Transaction Risk Analysis** exemptions: documented per transaction
- **GLBA Safeguards Rule** (2023 update): written information security program, designated qualified individual, risk assessment, access controls, encryption, MFA, training, vendor management, incident response plan
- **Card data minimization**: collect at point of payment, tokenize immediately, never store full PAN unencrypted, never store CVV after authorization
- **3-D Secure 2 + Risk-Based Authentication** as default for card payments

### Brazil financial specifics

- **Resolução BCB 4.658/2018**: cybersecurity policy and incident reporting
- **Resolução BCB 4.893/2021**: Open Finance scope and obligations
- **PIX**: instant payment system; specific Banco Central rules

### UI patterns

```tsx
function CardForm() {
  return (
    <form>
      <input
        name="cardNumber"
        autoComplete="cc-number"
        inputMode="numeric"
        pattern="[0-9 ]{13,19}"
      />
      <input
        name="cardExpiry"
        autoComplete="cc-exp"
        inputMode="numeric"
      />
      <input
        name="cardCvc"
        autoComplete="cc-csc"
        inputMode="numeric"
        // Never persisted server-side
      />
    </form>
  );
}
```

Use a PCI-DSS-compliant tokenization service (Stripe Elements, Adyen Components, etc.). Never receive raw PAN in the application server.

## Biometric (Illinois BIPA + Texas CUBI + Washington MHMD)

### Applies when

Any feature collects, stores, uses, or transmits biometric identifiers: fingerprint, palm print, voiceprint, iris scan, retina scan, face geometry, DNA, gait analysis, behavioral biometrics that uniquely identify.

### Mandatory targets

- **Written consent before collection** (Illinois BIPA + Texas CUBI): not click-through; explicit written or electronic signature
- **Written retention and destruction schedule** made publicly available
- **Maximum retention**: 3 years from last interaction (BIPA standard, treated as locked default)
- **No sale, no profit from biometric** (BIPA + Washington MHMD)
- **No sharing without separate consent** for each recipient
- **GDPR Art. 9** sensitive data treatment
- **LGPD Art. 5(II)** sensitive data treatment
- **Right to erase** with verifiable deletion, including all derived templates and embeddings

### Illinois BIPA risk

Private right of action with statutory damages: USD 1,000 per negligent violation, USD 5,000 per intentional violation. Class-action common. Treat BIPA as the floor everywhere.

### UI pattern for biometric enrollment

```tsx
function BiometricEnrollment() {
  return (
    <article>
      <h2>Enable face recognition</h2>
      <p>We will create a mathematical representation of your face to verify your identity. This is treated as sensitive biometric information.</p>
      <ul>
        <li>We retain this template for up to 3 years after your last login.</li>
        <li>We never sell or share your biometric data.</li>
        <li>You can delete it any time in <a href="/settings/biometric">Settings</a>.</li>
      </ul>
      <a href="/policies/biometric-data" target="_blank">Read the full biometric data policy</a>
      <ConsentSignature name="biometricConsent" />
      <button type="submit">Enroll</button>
    </article>
  );
}
```

`ConsentSignature` records an electronic signature (timestamp + IP + agreement text version) per BIPA "written" requirement.

## Identity / KYC / AML (BSA + AMLD6 + eIDAS 2)

### Applies when

Any feature performs identity verification for financial onboarding, crypto, age-restricted services, gambling, regulated marketplaces.

### Mandatory targets

- **Use a regulated identity provider** (Onfido, Persona, Stripe Identity, Jumio); do not build raw ID checks in-house
- **Never store raw ID documents long-term**: encrypted vault, short retention (typically 5 years for AML records, varies by jurisdiction)
- **AMLD6 (EU)**: customer due diligence, ongoing monitoring, suspicious activity reporting
- **eIDAS 2 (Regulation 2024/1183)**: EU Digital Identity Wallet support where available
- **AML 2024 Regulation 2024/1624**: harmonized EU rules directly applicable in 2027
- **Brazil COAF Resolução 36/2021**: PEP screening, sanction lists, threshold reporting

### KYC UI flow

```tsx
function KYCFlow({ stage }: Props) {
  return match(stage)
    .with("intro", () => <KYCIntro />)
    .with("docupload", () => <DocumentUpload provider="onfido" />)
    .with("selfie", () => <SelfieCapture provider="onfido" />)
    .with("review", () => <Review />)
    .with("complete", () => <Complete />)
    .exhaustive();
}
```

Document and selfie data go directly to the provider, never to the application server. The application server receives only the verification result + reference token.

## Crypto / Digital Assets (MiCA + Brazil 14.478)

### Applies when

Any feature offers crypto-asset services in the EU or Brazil: custody, exchange, advice, brokerage, portfolio management, transfer.

### Mandatory targets

- **MiCA whitepaper** for token offerings
- **Operating authorization** as crypto-asset service provider (CASP) in EU
- **Reserve disclosure** for asset-referenced tokens and e-money tokens
- **Anti-market-abuse** monitoring
- **Custody segregation**: customer assets in segregated wallets
- **Brazil Lei 14.478/2022 Art. 12**: VASP licensing, suspicious transaction reporting
- **FATF Travel Rule**: transmitter info on transfers ≥ USD/EUR 1,000

## Tax (EU VAT + Wayfair + PIS/COFINS)

### Applies when

Any feature sells goods or services digitally across borders.

### Mandatory targets

- **EU VAT OSS / IOSS**: One Stop Shop (intra-EU) and Import OSS (low-value goods from outside EU). VAT charged based on customer's country
- **EU DAC7**: digital platforms reporting of seller income
- **US post-Wayfair (South Dakota v. Wayfair, 2018)**: sales tax obligations in 45+ states based on economic nexus (typically USD 100k revenue or 200 transactions per state)
- **Brazil PIS/COFINS + ISS for digital services**: complex multi-level tax stack
- **Convênio ICMS 106/2017** Brazil: digital goods ICMS at state level

### Display

Tax included in displayed price (EU) or shown before checkout (US, varies by state). Brazil: ISS and ICMS shown at checkout per Decreto 7.962.

## Whistleblower (EU 2019/1937 + Brazil 13.608 + SOX + Dodd-Frank)

### Applies when

The project is for an organization with > 50 employees in the EU, or for a public-sector body, or for any US-listed company.

### Mandatory targets

- **Internal reporting channel UI** with anonymous submission option
- **Acknowledgment of receipt within 7 days**
- **Feedback to reporter within 3 months** (EU Directive)
- **Confidentiality** of reporter identity
- **Anti-retaliation** monitoring and audit
- **Multiple submission methods**: written, oral, in-person

### UI pattern

```tsx
function WhistleblowerForm() {
  return (
    <form>
      <fieldset>
        <legend>Submit a concern</legend>
        <ConsentCheckbox name="anonymous">
          I want to submit anonymously. The system will generate a token that I can use to follow up without revealing my identity.
        </ConsentCheckbox>
        <textarea name="report" required />
        <input type="file" name="attachments" multiple />
        <button type="submit">Submit</button>
      </fieldset>
      <p>Your submission is protected by EU Whistleblower Directive 2019/1937 + Brazil Lei 13.608. Retaliation is prohibited.</p>
    </form>
  );
}
```

## Maintenance

Review this standard:

- When HHS issues HIPAA modifications (notably the 2024 NPRM still pending)
- When PCI DSS publishes version 4.1 or any new requirement
- When EBA publishes PSD3 / PSR drafts or any RTS amendments
- When ESMA publishes MiCA implementing rules
- When BACEN updates BCB Resolutions on cybersecurity or Open Finance
- When Illinois BIPA amendments are passed
- When AML 2024 Regulation 2024/1624 implementing acts arrive
- When Washington MHMD or any state biometric law is enacted
- Yearly review on 1 January

## Related Standards

- [`../rules/compliance-defaults.md`](../rules/compliance-defaults.md): umbrella rule + locked targets
- [`privacy-engineering.md`](privacy-engineering.md): sensitive data overlaps
- [`authentication.md`](authentication.md): MFA, KYC
- [`../rules/security.md`](../rules/security.md): security baseline for sectoral overlay
- [`cybersecurity-baseline.md`](cybersecurity-baseline.md): breach notification per HIPAA, GLBA, BCB
