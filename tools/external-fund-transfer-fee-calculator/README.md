# External Fund Transfer Fee Calculator — Developer Notes

## Architecture

The calculator UI, fee logic, and PDF record generator live in shared modules
under `assets/external-fund-transfer-fee-calculator/` so both the standalone
page and the embedded guide page use the same implementation without
duplicating markup, styles, or calculation logic:

- `assets/external-fund-transfer-fee-calculator/fee-calculator.mjs` — Pure fee
  rates (`FEE_RATES`), CPI deflationary floor, rounding, validation, and
  currency formatting.
- `assets/external-fund-transfer-fee-calculator/calculator-widget.mjs` — Shared
  UI renderer, form controller, and jsPDF calculation record exporter
  (`mountFeeCalculator(root, { logoUrl })`).
- `assets/external-fund-transfer-fee-calculator/calculator-widget.css` — Scoped
  `.eft-calc` styles isolated from Just the Docs theme CSS.
- `assets/external-fund-transfer-fee-calculator/index.html` — Standalone
  calculator page mounting `mountFeeCalculator`.
- `assets/external-fund-transfer-fee-calculator/vendor/jspdf.umd.min.js` &
  `gss-logo-teal.jpg` — Bundled jsPDF library and GSS logo asset.
- `_includes/external_fee_calculator.html` — Jekyll include embedding the
  shared widget in `docs/tools/external-fund-transfer-fees.md`.

Note: `_config.yml` already excludes `tools/` from the published Jekyll site.

## Running Tests

Automated unit tests for the fee calculation logic use Node's built-in test
runner:

```sh
node --test tools/external-fund-transfer-fee-calculator/tests/fee-calculator.test.mjs
```
