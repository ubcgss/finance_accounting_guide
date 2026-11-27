---
title: External Fund Transfer Fees
layout: default
parent: Tools
nav_order: 2
permalink: /tools/external-fund-transfer-fees/
---

# External Fund Transfer Fee Calculator

Use this calculator to prepare an internal fee calculation record for **one
batch of payments** administered for a participating organization. It calculates
the annual fee when due, the batch fee, the percentage processing fee, the
multi-transfer fee for batches of more than 10 payments, and the resulting
**net transfer value**.

[Open the External Fund Transfer Fee Calculator]({{ site.baseurl }}/assets/external-fund-transfer-fee-calculator/){: .btn .btn-primary }

{: .note }
> The calculator runs entirely in your browser. It does not transmit the
> organization or payment information. Use **Download calculation record (PDF)**
> to save the itemized result locally and attach it to the batch's supporting
> records.

---

## Fee Basis

The calculator uses the **February 2026** baseline rates in the
[House-Finance Policy, Appendix III, section 3](https://gss.ubc.ca/by-laws-code-policies/):

| Fee | February 2026 baseline rate |
|-----|-----------------------------|
| Annual flat fee | $40 once per GSS fiscal year, when due |
| Batch transfer fee | $20 for each payment batch |
| Transfer processing fee | 0.33% of the batch's total transfer value |
| Multi-transfer fee | $2 for every individual payment when a batch has more than 10 payments |

Each fee component is rounded to cents before the total administration fee (`F`)
and **net transfer value** (`X - F`, i.e. `Transfer value` minus `Total administration fee`)
are calculated.

Under **House-Finance Policy, Appendix III and Appendix IV**, the fixed dollar
fees ($40, $20, and $2) adjust annually on **June 1** using the 12-month
percentage change (April of the previous year to March of the current year) in
the [Statistics Canada Consumer Price Index (CPI) for Vancouver, All-items (Table 18-10-0004-01)](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401),
subject to a **0% deflationary floor**. The 0.33% transfer processing rate is
unadjusted by CPI because it already scales with nominal transfer value. The
calculator's **CPI adjustment (%)** field defaults to `0.00` (February 2026
baseline); enter the applicable cumulative CPI percentage once an annual
adjustment takes effect. The current policy is marked for review in April 2027.

---

## Using the Calculation Record

1. Enter the participating organization, calculation date, total transfer value (`X`),
   number of individual payments, the CPI adjustment percentage (`0.00` for the
   February 2026 baseline), and whether the annual fee is due.
2. Select **Calculate fees** and review **Administration fee (`F`)** and
   **Net transfer value (`X - F`)**.
3. Select **Download calculation record (PDF)** and attach the PDF with the
   batch's Zoho submission and supporting payment documentation.

---

## Accounting and Bookkeeping Procedure

Because the GSS holds and transfers these funds on behalf of participating
organizations as an intermediary, the gross inflow (`X`) is **not** GSS
revenue. Only the total administration fee (`F`) is recognized as GSS income;
the remaining balance is tracked as a liability until disbursed.

### Relevant Zoho Books Accounts

| Account code | Account name | Purpose |
|---|---|---|
| `1100` | Scotiabank Chequing – Operating (4214) | Operating bank account receiving gross transfers (`X`) and funding direct disbursements |
| `1130` | Plooto Clearing Account | Clearing account when disbursements are initiated via Plooto |
| `2230` | Student Group Fees Payable | Liability account holding funds on behalf of participating organizations (`X`) |
| `4800` | External Organization Fees – Administration Recovery | Operating income account for the total administration fee (`F`) |
| `6584` | Plooto Transaction Fees | Operating expense for GSS's own Plooto processing fees (separate from `4800`) |

### Standard Two-Step Journal Entries

Hold the full amount in `2230` when cash arrives, then recognize `4800` when the
disbursement batch is processed (so the entry uses the finalized batch and
multi-transfer counts and keeps revenue recognition aligned with service
delivery):

1. **Receive funds (`X`):**
   - **Debit** `1100 - Scotiabank Chequing – Operating (4214)`: **`X`**
   - **Credit** `2230 - Student Group Fees Payable`: **`X`**

2. **Process and disburse the batch (`F` = Total administration fee; `X - F` = Net transfer value):**
   - **Debit** `2230 - Student Group Fees Payable`: **`X`** *(or the batch gross if drawing down a multi-batch balance)*
   - **Credit** `4800 - External Organization Fees – Administration Recovery`: **`F`**
   - **Credit** `1100 - Scotiabank Chequing – Operating (4214)` *(or `1130 - Plooto Clearing Account` if paid via Plooto)*: **`X - F`**

{: .note }
> If an organization draws down its balance across multiple batches in the same
> fiscal year, run Step 2 for each batch (`$40` annual fee checked on the first
> batch only), leaving any remaining balance in `2230`. Splitting `4800` at Step 1
> on initial receipt is appropriate only if all batch and transfer counts are
> already final when the funds arrive.

### Controls and Reconciliation

- **Tag every `2230` entry by organization** (Contact/Vendor in Zoho Books) so
  the payable balance reconciles cleanly per organization at month-end and
  year-end.
- **Check GST with the Accountant** before posting or invoicing an organization
  for `4800` to confirm whether GST applies to the administration recovery.

---

## Maintaining the Tool

The calculator page is `assets/external-fund-transfer-fee-calculator/index.html`
and its shared fee module is `assets/external-fund-transfer-fee-calculator/fee-calculator.mjs`
in this repository. Automated tests live in `tools/external-fund-transfer-fee-calculator/tests/`
and use Node's built-in test runner (`node --test`).
