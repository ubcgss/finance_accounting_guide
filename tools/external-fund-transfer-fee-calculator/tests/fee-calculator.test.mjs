import assert from "node:assert/strict";
import test from "node:test";

import { calculateFees } from "../../../assets/external-fund-transfer-fee-calculator/fee-calculator.mjs";

test("includes the annual fee only when it is due", () => {
  const withoutAnnual = calculateFees({ transferValue: 100, paymentCount: 1, annualFeeDue: false });
  const withAnnual = calculateFees({ transferValue: 100, paymentCount: 1, annualFeeDue: true });

  assert.equal(withoutAnnual.effectiveCpiRate, 0);
  assert.equal(withoutAnnual.annualFlatFee, 0);
  assert.equal(withAnnual.annualFlatFee, 40);
  assert.equal(withAnnual.totalAdministrationFee - withoutAnnual.totalAdministrationFee, 40);
  assert.equal(withoutAnnual.netTransferValue, 79.67);
  assert.equal(withAnnual.netTransferValue, 39.67);
});

test("does not charge the multi-transfer fee for 1 or 10 payments", () => {
  for (const paymentCount of [1, 10]) {
    const fees = calculateFees({ transferValue: 100, paymentCount, annualFeeDue: false });
    assert.equal(fees.multiTransferFee, 0);
    assert.equal(fees.totalAdministrationFee, 20.33);
    assert.equal(fees.netTransferValue, 79.67);
  }
});

test("charges every payment when a batch has more than 10 payments", () => {
  const fees = calculateFees({ transferValue: 100, paymentCount: 11, annualFeeDue: false });
  assert.equal(fees.multiTransferFee, 22);
  assert.equal(fees.totalAdministrationFee, 42.33);
  assert.equal(fees.netTransferValue, 57.67);
});

test("rounds each fee component to cents before adding the total", () => {
  const fees = calculateFees({ transferValue: 10.015, paymentCount: 1, annualFeeDue: false });
  assert.equal(fees.transferProcessingFee, 0.03);
  assert.equal(fees.totalAdministrationFee, 20.03);
  assert.equal(fees.netTransferValue, -10.01);
});

test("applies CPI adjustment to fixed dollar fees while keeping 0.33% unadjusted", () => {
  const fees = calculateFees({
    transferValue: 10000,
    paymentCount: 11,
    annualFeeDue: true,
    cpiRate: 0.022
  });

  assert.equal(fees.effectiveCpiRate, 0.022);
  assert.deepEqual(fees.appliedRates, {
    annualFlatFee: 40.88,
    batchTransferFee: 20.44,
    transferProcessingRate: 0.0033,
    multiTransferFee: 2.04
  });
  assert.equal(fees.annualFlatFee, 40.88);
  assert.equal(fees.batchTransferFee, 20.44);
  assert.equal(fees.transferProcessingFee, 33);
  assert.equal(fees.multiTransferFee, 22.44);
  assert.equal(fees.totalAdministrationFee, 116.76);
  assert.equal(fees.netTransferValue, 9883.24);
});

test("applies a 0% deflationary floor to negative CPI inputs", () => {
  const baseline = calculateFees({ transferValue: 1000, paymentCount: 12, annualFeeDue: true, cpiRate: 0 });
  const deflated = calculateFees({ transferValue: 1000, paymentCount: 12, annualFeeDue: true, cpiRate: -0.015 });

  assert.equal(deflated.effectiveCpiRate, 0);
  assert.deepEqual(deflated, baseline);
});

test("rejects invalid transfer values, payment counts, and CPI rates", () => {
  assert.throws(() => calculateFees({ transferValue: -1, paymentCount: 1, annualFeeDue: false }), RangeError);
  assert.throws(() => calculateFees({ transferValue: 0, paymentCount: 1, annualFeeDue: false }), RangeError);
  assert.throws(() => calculateFees({ transferValue: Number.NaN, paymentCount: 1, annualFeeDue: false }), RangeError);
  assert.throws(() => calculateFees({ transferValue: 1, paymentCount: 0, annualFeeDue: false }), RangeError);
  assert.throws(() => calculateFees({ transferValue: 1, paymentCount: 1.5, annualFeeDue: false }), RangeError);
  assert.throws(() => calculateFees({ transferValue: 100, paymentCount: 1, annualFeeDue: false, cpiRate: Number.NaN }), RangeError);
  assert.throws(() => calculateFees({ transferValue: 100, paymentCount: 1, annualFeeDue: false, cpiRate: Number.POSITIVE_INFINITY }), RangeError);
});
