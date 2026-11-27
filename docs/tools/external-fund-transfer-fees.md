---
title: External Fund Transfer Fees
layout: default
parent: Tools
nav_order: 2
permalink: /tools/external-fund-transfer-fees/
---

# External Fund Transfer Fee Calculator

Calculate the administration fee and net transfer value for one payment batch
administered for a participating organization, then download the PDF record to
attach in Zoho.

{% include external_fee_calculator.html %}

---

## Fee Basis

Rates follow the February 2026 baseline in
[House-Finance Policy, Appendix III, section 3](https://gss.ubc.ca/by-laws-code-policies/):

| Fee | Baseline rate |
|-----|---------------|
| Annual flat fee | $40 once per GSS fiscal year, when due |
| Batch transfer fee | $20 for each payment batch |
| Transfer processing fee | 0.33% of the batch's total transfer value |
| Multi-transfer fee | $2 for every individual payment when a batch has more than 10 payments |

Each fee component is rounded to cents before the total administration fee and
net transfer value (Transfer value minus Total administration fee) are
calculated.

Under House-Finance Policy (Appendix III and Appendix IV), the fixed dollar fees
($40, $20, and $2) adjust each June 1 using the 12-month percentage change
(April of the previous year to March of the current year) in the
[Vancouver Consumer Price Index (CPI)](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401),
subject to a 0% floor. Leave CPI adjustment (%) at `0.00` for the February 2026
baseline, or enter the active cumulative percentage after an annual adjustment.

---

## Recording in Zoho Books

Funds held for participating organizations are a liability, not GSS revenue. Only
the total administration fee is recorded as GSS income.

1. **When funds arrive:**
   - **Debit** `1100 - Scotiabank Chequing – Operating (4214)` for the transfer value
   - **Credit** `2230 - Student Group Fees Payable` for the transfer value *(tag the organization so balances reconcile cleanly)*
2. **When paying out the batch:**
   - **Debit** `2230 - Student Group Fees Payable` for the batch transfer value
   - **Credit** `4800 - External Organization Fees – Administration Recovery` for the total administration fee
   - **Credit** `1100 - Scotiabank Chequing – Operating (4214)` *(or `1130 - Plooto Clearing Account` if paid via Plooto)* for the net transfer value

If an organization draws down its balance across multiple batches in the same
fiscal year, only check the $40 annual fee on the first batch.
