# How to Write Requirements Documents for SpecTater

This guide explains how to structure and write effective requirements documents that the AI can accurately evaluate against submission documents (like Certificates of Insurance).

## Overview

A well-written requirements document allows SpecTater to:
- Clearly identify required criteria
- Objectively evaluate submitted documents
- Provide consistent, accurate pass/fail determinations
- Generate meaningful explanations for compliance gaps

## Key Principles

### 1. Be Specific and Measurable
✅ **Good**: "Certificate must show General Liability coverage with a minimum limit of $2,000,000 per occurrence"
❌ **Bad**: "Need insurance coverage"

The AI needs concrete values and criteria to compare against. Vague requirements lead to inconsistent evaluations.

### 2. Use Clear Language
✅ **Good**: "Certificate holder name and address must match the entity name and primary business address provided in the application"
❌ **Bad**: "Holder info should be correct"

Explicit language helps the AI understand what constitutes compliance.

### 3. Include Conditions and Exceptions
✅ **Good**: "Workers' Compensation coverage required for all employees. Exception: Independent contractors with valid 1099 tax status are exempt"
❌ **Bad**: "Need workers' comp"

Context helps the AI apply requirements correctly in edge cases.

### 4. One Requirement = One Criterion
Break complex requirements into separate items. This makes evaluation clearer:

✅ **Good**:
- Requirement 1: Certificate must include Certificate Holder name
- Requirement 2: Certificate must include Certificate Holder address
- Requirement 3: Certificate Holder name must match entity name from application

❌ **Bad**:
- Requirement 1: Certificate holder information must be complete and correct

## Document Structure

### Header Section
Include context at the top to orient the AI:

```
# [Organization] Insurance Requirements Policy

**Effective Date**: [Date]
**Policy Version**: [Version number]
**Applicable To**: [Who must comply - contractors, vendors, partners, etc.]

## Overview
Brief description of what this policy covers and why it exists.
Example: "All contractors engaged by [Organization] must maintain insurance coverage as specified below to protect against liability exposure."
```

### Definitions Section (Optional but Recommended)
Define any specialized terms or acronyms:

```
## Definitions

- **Certificate of Insurance (COI)**: Standard ACORD form 25-S(06/14) documenting active insurance coverage
- **Additional Insured**: Party added to an insurance policy to receive coverage
- **Per Occurrence Limit**: Maximum amount insurer pays per single incident
- **General Aggregate Limit**: Maximum amount insurer pays for all claims in policy period
- **OSHA**: Occupational Safety and Health Administration (federal workplace safety standards)
```

### Requirements Section
The main content. Use a numbered list format:

```
## Insurance Requirements

### 1. Certificate of Insurance Information

1.1 Certificate Holder Name and Address
   - **Requirement**: The Certificate Holder name must match the legal entity name provided in the contract/application
   - **Requirement**: Certificate Holder address must be the primary business address
   - **Why**: Ensures the certificate is issued for the correct entity

1.2 Insurance Company Information
   - **Requirement**: Insurance company name must be clearly identified on the certificate
   - **Requirement**: Insurance company rating must be A- VII or better (per AM Best rating scale)
   - **Why**: Verifies insurer solvency and reliability

### 2. General Liability Coverage

2.1 Coverage Type
   - **Requirement**: Certificate must include General Liability (Commercial General Liability / CGL) coverage
   - **Why**: Protects against bodily injury and property damage claims

2.2 Coverage Limits
   - **Requirement**: General Liability minimum limit must be $[amount] per occurrence
   - **Requirement**: General Liability General Aggregate limit must be $[amount] per policy year
   - **Example**: "Per occurrence: $2,000,000 | General Aggregate: $2,000,000"

2.3 Damage to Rented Premises
   - **Requirement**: General Liability must include Damage to Rented Premises endorsement
   - **Requirement**: Damage to Rented Premises limit must be at least $[amount]
   - **Why**: Ensures [Organization] is protected if work damage occurs to leased spaces

### 3. Additional Insured Status

3.1 Additional Insured Endorsement
   - **Requirement**: Certificate must include [Organization] named as Additional Insured
   - **Requirement**: Additional Insured coverage must apply to General Liability
   - **Requirement**: Endorsement must be primary and non-contributory
   - **Why**: Ensures [Organization] receives direct coverage protection

### 4. Umbrella/Excess Liability

4.1 Umbrella Coverage (if applicable)
   - **Requirement**: Umbrella/Excess Liability minimum limit must be $[amount]
   - **Requirement**: Umbrella must follow form over General Liability
   - **Why**: Provides additional liability protection above base coverage

### 5. Liquor Liability (if applicable)

5.1 Liquor Liability Coverage
   - **Requirement**: Certificate must include Liquor Liability coverage
   - **Requirement**: Liquor Liability limit must be minimum $[amount] per occurrence
   - **Condition**: Required if contractor serves, sells, or provides alcohol at any event on [Organization] premises
   - **Exception**: Not required for contractors with no alcohol-related services

### 6. Commercial Auto Liability (if applicable)

6.1 Vehicle Coverage
   - **Requirement**: Commercial Auto Liability coverage required if any work involves operation of motor vehicles
   - **Requirement**: Auto Liability minimum limit must be $[amount] combined single limit (or $[X] bodily injury/$[Y] property damage)
   - **Requirement**: Coverage must apply to vehicles used for [Organization] contract work
   - **Exception**: Not required if no vehicles involved in contract

### 7. Workers' Compensation Insurance

7.1 Workers' Comp Coverage
   - **Requirement**: Workers' Compensation insurance required for all employees
   - **Requirement**: Coverage must meet [State] statutory minimum limits
   - **Requirement**: Certificate must show statutory limits or specific dollar amounts if higher
   - **Exception**: Not required for independent contractors with valid 1099 tax status
   - **Exception**: Not required for contractors with zero employees

7.2 Coverage Proof
   - **Requirement**: If applicable, certificate must clearly state "Statutory Limits" or display actual dollar amounts
   - **Why**: Verifies compliance with state law requirements

### 8. Coverage Validity and Endorsements

8.1 Effective Dates
   - **Requirement**: All coverage must be effective and active (not expired)
   - **Requirement**: Policy effective date must be on or before [start date of contract]
   - **Requirement**: Policy expiration date must extend through [end date of contract] or have automatic renewal notation

8.2 Waiver of Subrogation
   - **Requirement**: Policy must include Waiver of Subrogation in favor of [Organization]
   - **Why**: Prevents insurer from suing [Organization] if claim arises from contractor's work

```

## Writing Requirements - Practical Examples

### Example 1: Certificate Holder Information
```
**REQUIREMENT**: Certificate Holder name matches the legal entity name from the contract

**What to look for**:
- Certificate Holder: ACME Contracting LLC
- Contract Entity: ACME Contracting LLC
✅ PASS: Names match

- Certificate Holder: ACME Contracting, Inc.
- Contract Entity: ACME Contracting LLC
❌ FAIL: Different legal entity type (Inc. vs. LLC)
```

### Example 2: General Liability Limits
```
**REQUIREMENT**: General Liability per occurrence limit must be at least $2,000,000

**What to look for in certificate**:
- Line item: "General Liability - Per Occurrence: $2,000,000"
✅ PASS: Meets or exceeds requirement

- Line item: "General Liability - Per Occurrence: $1,000,000"
❌ FAIL: Below required minimum

- Line item: "General Liability - Per Occurrence: $5,000,000"
✅ PASS: Exceeds requirement
```

### Example 3: Additional Insured Status
```
**REQUIREMENT**: [Organization] must be named as Additional Insured on General Liability

**What to look for**:
- Additional Insured (shown): [Organization], and its officers, employees, and agents
✅ PASS: Organization is named

- Additional Insured (shown): [blank or only other entities]
❌ FAIL: Organization not listed as Additional Insured
```

### Example 4: Conditional Requirement
```
**REQUIREMENT**: Workers' Compensation coverage required for all employees; exempt if contractor has no employees

**What to look for**:
- Certificate shows: "Workers' Compensation - [State] Statutory Limits"
✅ PASS: WC coverage in place

- Certificate shows: "Workers' Compensation: N/A or blank" AND Contractor info shows "0 employees"
✅ PASS: No employees, exemption applies

- Certificate shows: "Workers' Compensation: N/A or blank" AND Contractor info shows "5 employees"
❌ FAIL: Employees but no WC coverage
```

### Example 5: Insurance Company Rating
```
**REQUIREMENT**: Insurance company must have AM Best rating of A- VII or better

**What to look for**:
- Insurance Company: Acme Insurance Corp (AM Best Rating: A)
✅ PASS: A rating exceeds minimum A- VII

- Insurance Company: Acme Insurance Corp (AM Best Rating: B+)
❌ FAIL: B+ rating is below A- VII minimum
```

## Common Requirement Categories for Insurance

Here's a template covering typical insurance requirements:

### Certificate Holder / Entity Information
- Name (must match contract entity)
- Address (must match registered business address)
- Business type or identification

### Insurance Company Details
- Company name
- AM Best rating (A- VII or better typical minimum)
- License/authorization to do business in state

### General Liability Coverage
- Per Occurrence limit (e.g., $2,000,000)
- General Aggregate limit (e.g., $2,000,000)
- Damage to Rented Premises
- Additional Insured status

### Umbrella/Excess Liability (if needed)
- Coverage limit (e.g., $1,000,000)
- Follows form designation
- Additional Insured status

### Specialized Coverages (as applicable)
- **Liquor Liability**: If serving/selling alcohol
- **Auto Liability**: If using vehicles
- **Professional Liability**: If providing professional services
- **Errors & Omissions**: If managing/administering programs

### Workers' Compensation
- State statutory minimum (or specify amounts)
- Employee coverage requirements
- Exceptions for independent contractors

### Additional Endorsements
- Waiver of Subrogation
- Primary and Non-Contributory endorsement
- Certificate of Insurance issuer contact information

## Format Recommendations

### Use Clear Headers and Hierarchy
```
# Section Title (H1)
## Subsection (H2)
### Specific Requirement (H3)
- Bullet point details
```

### Use Tables for Complex Requirements
```
| Coverage Type | Minimum Limit | Notes |
|---|---|---|
| General Liability - Per Occurrence | $2,000,000 | Primary coverage |
| General Liability - General Aggregate | $2,000,000 | Annual limit |
| Umbrella Liability | $1,000,000 | Follows form |
```

### Highlight Conditions with Keywords
Use clear indicators for conditional logic:
- **"Required if..."**: Applies only in certain situations
- **"Exception..."**: When requirement doesn't apply
- **"Example..."**: Concrete case demonstrating compliance
- **"Why..."**: Explains the business purpose

## Tips for Effective Requirements Documents

1. **Review with Subject Matter Experts**: Have insurance professionals or procurement specialists review before deployment

2. **Test with Real Documents**: Run the system in debug mode against actual certificates to ensure requirements are evaluable

3. **Avoid Ambiguous Language**:
   - ❌ "Reasonable limits"
   - ✅ "$2,000,000 per occurrence minimum"

4. **Include Dollar Amounts**: Don't make the AI guess what's "adequate"
   - ❌ "Appropriate coverage"
   - ✅ "$2,000,000 combined single limit"

5. **Document Exceptions**: Be explicit about when requirements don't apply
   - ❌ "Workers' comp if needed"
   - ✅ "Workers' Comp required for all employees. Exception: Independent contractors (1099 status)"

6. **Standardize Date Formats**: Be consistent with how dates are written
   - ✅ Use "MM/DD/YYYY" consistently throughout
   - ✅ State: "Policy must be active through [contract end date]"

7. **Keep Requirements Focused**: 5-50 requirements is optimal
   - Too few (<5): Minimal value from automation
   - Too many (>100): AI accuracy decreases due to complexity

8. **Version Your Requirements**: Track changes to requirements over time
   ```
   Version 1.0 - Initial policy [Date]
   Version 1.1 - Added Liquor Liability requirement [Date]
   ```

## Integration with SpecTater

When uploading requirements to SpecTater:

1. **Save as Markdown (.md) file**
   - File name: `osu-requirements.md` or similar
   - Use standard Markdown formatting

2. **Or save as PDF**
   - Use consistent formatting
   - SpecTater will extract text automatically

3. **Or save as Plain Text (.txt)**
   - Use clear headers and bullet points
   - One requirement per line/paragraph when possible

4. **Test with Sample Certificate**
   - Run SpecTater against known-good certificate
   - Verify results are accurate
   - Adjust requirements if needed

5. **Use Static Requirements Option** (for production)
   - Set `REQUIREMENTS='osu-requirements.md'` in `.env`
   - Policy file auto-loads without user upload
   - Users only upload certificates to evaluate

## Troubleshooting Unclear Requirements

If SpecTater results are inconsistent or wrong:

1. **Check Specificity**: Is the requirement specific enough?
   - Add exact dollar amounts
   - Add exact company names or identifiers
   - Add date formats

2. **Check Clarity**: Is language unambiguous?
   - Avoid words like "reasonable," "adequate," "substantial"
   - Use objective criteria only

3. **Check Completeness**: Are you missing context?
   - Add examples of what PASS looks like
   - Add examples of what FAIL looks like
   - Add "Why" explanation for business context

4. **Enable Debug Mode**: Set `FLASK_DEBUG=True` in `.env`
   - Shows full JSON response from AI
   - Shows which requirements passed/failed
   - Helps identify requirement clarity issues

## Example: Complete Insurance Requirements Document

See `osu-requirements-template.md` (in the repository) for a complete, ready-to-customize insurance requirements document with all sections filled in.

---

**Questions?** Contact your SpecTater administrator or refer to the main README.md for system information.
