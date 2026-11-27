export const FEE_RATES = Object.freeze({
  annualFlatFee: 40,
  batchTransferFee: 20,
  transferProcessingRate: 0.0033,
  multiTransferFee: 2,
  multiTransferThreshold: 10,
  policySource: "House-Finance Policy, Appendix III, section 3 (February 2026)",
  policyBaselineDate: "February 2026",
  policyReviewDate: "April 2027",
  policyUrl: "https://gss.ubc.ca/by-laws-code-policies/",
  statCanCpiUrl: "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401"
});

export function roundToCents(value) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function requirePositiveFinite(value, label) {
  if (!Number.isFinite(value) || value <= 0) {
    throw new RangeError(`${label} must be a positive number.`);
  }
}

function requirePaymentCount(value) {
  if (!Number.isSafeInteger(value) || value < 1) {
    throw new RangeError("Individual payment count must be a whole number of at least 1.");
  }
}

export function calculateFees({ transferValue, paymentCount, annualFeeDue, cpiRate = 0 }) {
  requirePositiveFinite(transferValue, "Transfer value");
  requirePaymentCount(paymentCount);
  if (!Number.isFinite(cpiRate)) {
    throw new RangeError("CPI adjustment must be a valid number.");
  }

  // Appendix IV s. 8 applies a 0% deflationary floor; 0.33% scales with nominal transfer dollars.
  const effectiveCpiRate = Math.max(0, cpiRate);
  const annualFlatFeeRate = roundToCents(FEE_RATES.annualFlatFee * (1 + effectiveCpiRate));
  const batchTransferFeeRate = roundToCents(FEE_RATES.batchTransferFee * (1 + effectiveCpiRate));
  const multiTransferFeeRate = roundToCents(FEE_RATES.multiTransferFee * (1 + effectiveCpiRate));

  const annualFlatFee = annualFeeDue ? annualFlatFeeRate : 0;
  const batchTransferFee = batchTransferFeeRate;
  const transferProcessingFee = roundToCents(
    transferValue * FEE_RATES.transferProcessingRate
  );
  const multiTransferFee = paymentCount > FEE_RATES.multiTransferThreshold
    ? roundToCents(paymentCount * multiTransferFeeRate)
    : 0;
  const totalAdministrationFee = roundToCents(
    annualFlatFee + batchTransferFee + transferProcessingFee + multiTransferFee
  );
  const netTransferValue = roundToCents(transferValue - totalAdministrationFee);

  return {
    effectiveCpiRate,
    appliedRates: {
      annualFlatFee: annualFlatFeeRate,
      batchTransferFee: batchTransferFeeRate,
      transferProcessingRate: FEE_RATES.transferProcessingRate,
      multiTransferFee: multiTransferFeeRate
    },
    annualFlatFee,
    batchTransferFee,
    transferProcessingFee,
    multiTransferFee,
    totalAdministrationFee,
    netTransferValue
  };
}

export function formatCurrency(value) {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD"
  }).format(value);
}
