import { FEE_RATES, calculateFees, formatCurrency } from "./fee-calculator.mjs";

function today() {
  const now = new Date();
  const offset = now.getTimezoneOffset();
  return new Date(now.getTime() - offset * 60_000).toISOString().slice(0, 10);
}

function formatCpiDescription(details, fees) {
  const pct = (fees.effectiveCpiRate * 100).toFixed(2);
  if (details.cpiRate < 0) return `${pct}% (0% floor applied to Feb 2026 baseline)`;
  if (fees.effectiveCpiRate === 0) return `${pct}% (Feb 2026 baseline)`;
  return `${pct}% (applied to fixed dollar fees)`;
}

function buildFeeLabels(fees) {
  const adjusted = fees.effectiveCpiRate > 0;
  return {
    annual: adjusted ? `Annual flat fee (${formatCurrency(fees.appliedRates.annualFlatFee)})` : "Annual flat fee",
    batch: adjusted ? `Batch transfer fee (${formatCurrency(fees.appliedRates.batchTransferFee)})` : "Batch transfer fee",
    multi: adjusted ? `Multi-transfer fee (${formatCurrency(fees.appliedRates.multiTransferFee)} per payment)` : "Multi-transfer fee"
  };
}

function safeFilename(value) {
  return value.replace(/[^a-z0-9]+/gi, "-").replace(/(^-|-$)/g, "").slice(0, 90) || "participating-organization";
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("The GSS logo could not be loaded for the PDF."));
    image.src = url;
  });
}

function drawSectionHeading(doc, title, y) {
  doc.setTextColor(0, 121, 122);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(11);
  doc.text(title, 54, y);
  doc.setDrawColor(0, 121, 122);
  doc.setLineWidth(1.0);
  doc.line(54, y + 6, 558, y + 6);
  return y + 23;
}

function renderTemplate() {
  return `
    <div class="layout">
      <section class="card" aria-labelledby="eft-details-heading">
        <h2 id="eft-details-heading">Batch details</h2>
        <form class="fields" data-eft-form novalidate>
          <label>Participating organization name
            <input name="organization" autocomplete="organization" required maxlength="150" placeholder="e.g., Example Graduate Society">
          </label>
          <label>Calculation date
            <input name="calculation-date" type="date" required>
          </label>
          <label>Transfer value (CAD)
            <input name="transfer-value" type="number" min="0" step="0.01" inputmode="decimal" required placeholder="0.00">
          </label>
          <label>Individual payments in this batch
            <input name="payment-count" type="number" min="1" step="1" inputmode="numeric" required placeholder="1">
            <span class="help">The $2 per-payment baseline fee applies to every payment only when the batch has more than 10 payments.</span>
          </label>
          <label>CPI adjustment (%)
            <input name="cpi-adjustment" type="number" step="0.01" inputmode="decimal" value="0.00" required>
            <span class="help">Under <a href="${FEE_RATES.policyUrl}" target="_blank" rel="noopener noreferrer">HFC Policy Appendix IV</a>, fixed dollar fees adjust each June 1 using the April–March 12-month % change in <a href="${FEE_RATES.statCanCpiUrl}" target="_blank" rel="noopener noreferrer">Vancouver Consumer Price Index (CPI)</a>.</span>
          </label>
          <label class="checkbox"><input name="annual-fee-due" type="checkbox"> <span>The organization’s annual fee is due with this batch.</span></label>
          <button type="submit">Calculate fees</button>
          <p class="error" data-eft-error role="alert" aria-live="polite"></p>
        </form>
      </section>

      <section class="card" data-eft-results aria-labelledby="eft-results-heading" hidden>
        <h2 id="eft-results-heading">Administration fee</h2>
        <dl>
          <div class="fee"><dt data-eft-label="annual">Annual flat fee</dt><dd data-eft-value="annual"></dd></div>
          <div class="fee"><dt data-eft-label="batch">Batch transfer fee</dt><dd data-eft-value="batch"></dd></div>
          <div class="fee"><dt>Transfer processing fee (0.33%)</dt><dd data-eft-value="processing"></dd></div>
          <div class="fee"><dt data-eft-label="multi">Multi-transfer fee</dt><dd data-eft-value="multi"></dd></div>
          <div class="fee total"><dt>Total administration fee</dt><dd data-eft-value="total"></dd></div>
        </dl>
        <h2 class="section-sub">Net transfer value</h2>
        <dl>
          <div class="fee"><dt>Gross transfer value</dt><dd data-eft-value="gross"></dd></div>
          <div class="fee"><dt>Less: Total administration fee</dt><dd data-eft-value="less"></dd></div>
          <div class="fee total"><dt>Net transfer value</dt><dd data-eft-value="net"></dd></div>
        </dl>
        <button class="secondary" data-eft-download type="button">Download calculation record (PDF)</button>
      </section>
    </div>
  `;
}

export function mountFeeCalculator(
  root,
  { logoUrl = new URL("./gss-logo-teal.jpg", import.meta.url).href } = {}
) {
  if (!root) {
    throw new Error("Calculator root element not found.");
  }

  root.classList.add("eft-calc");
  root.innerHTML = renderTemplate();

  const form = root.querySelector("[data-eft-form]");
  const results = root.querySelector("[data-eft-results]");
  const error = root.querySelector("[data-eft-error]");
  const downloadButton = root.querySelector("[data-eft-download]");

  const fields = {
    organization: form.querySelector('input[name="organization"]'),
    calculationDate: form.querySelector('input[name="calculation-date"]'),
    transferValue: form.querySelector('input[name="transfer-value"]'),
    paymentCount: form.querySelector('input[name="payment-count"]'),
    cpiAdjustment: form.querySelector('input[name="cpi-adjustment"]'),
    annualFeeDue: form.querySelector('input[name="annual-fee-due"]')
  };

  let latestCalculation;

  function readCalculation() {
    const organization = fields.organization.value.trim();
    const calculationDate = fields.calculationDate.value;
    const transferValue = fields.transferValue.value;
    const paymentCount = fields.paymentCount.value;
    const cpiAdjustment = fields.cpiAdjustment.value;
    if (!organization) throw new RangeError("Enter the participating organization name.");
    if (!calculationDate) throw new RangeError("Enter the calculation date.");
    if (!transferValue) throw new RangeError("Enter the transfer value.");
    if (!paymentCount) throw new RangeError("Enter the individual payment count.");
    if (cpiAdjustment === "") throw new RangeError("Enter the CPI adjustment percentage (0.00 if none).");
    const enteredCpiRate = Number(cpiAdjustment) / 100;
    return {
      organization,
      calculationDate,
      transferValue: Number(transferValue),
      paymentCount: Number(paymentCount),
      cpiRate: enteredCpiRate,
      annualFeeDue: fields.annualFeeDue.checked
    };
  }

  function renderFees(details, fees) {
    const labels = buildFeeLabels(fees);
    root.querySelector('[data-eft-label="annual"]').textContent = labels.annual;
    root.querySelector('[data-eft-label="batch"]').textContent = labels.batch;
    root.querySelector('[data-eft-label="multi"]').textContent = labels.multi;
    root.querySelector('[data-eft-value="annual"]').textContent = formatCurrency(fees.annualFlatFee);
    root.querySelector('[data-eft-value="batch"]').textContent = formatCurrency(fees.batchTransferFee);
    root.querySelector('[data-eft-value="processing"]').textContent = formatCurrency(fees.transferProcessingFee);
    root.querySelector('[data-eft-value="multi"]').textContent = formatCurrency(fees.multiTransferFee);
    root.querySelector('[data-eft-value="total"]').textContent = formatCurrency(fees.totalAdministrationFee);
    root.querySelector('[data-eft-value="gross"]').textContent = formatCurrency(details.transferValue);
    root.querySelector('[data-eft-value="less"]').textContent = formatCurrency(fees.totalAdministrationFee);
    root.querySelector('[data-eft-value="net"]').textContent = formatCurrency(fees.netTransferValue);
    results.hidden = false;
  }

  async function downloadPdf() {
    if (!latestCalculation) return;
    if (!window.jspdf || !window.jspdf.jsPDF) {
      error.textContent = "PDF library is not available.";
      return;
    }
    try {
      const { jsPDF } = window.jspdf;
      const logo = await loadImage(logoUrl);
      const doc = new jsPDF({ unit: "pt", format: "letter" });
      const { details, fees } = latestCalculation;
      const labels = buildFeeLabels(fees);
      const feeRows = [
        [labels.annual, formatCurrency(fees.annualFlatFee)],
        [labels.batch, formatCurrency(fees.batchTransferFee)],
        ["Transfer processing fee (0.33%)", formatCurrency(fees.transferProcessingFee)],
        [labels.multi, formatCurrency(fees.multiTransferFee)],
        ["Total administration fee", formatCurrency(fees.totalAdministrationFee)]
      ];
      const netRows = [
        ["Gross transfer value", formatCurrency(details.transferValue)],
        ["Less: Total administration fee", formatCurrency(fees.totalAdministrationFee)],
        ["Net transfer value", formatCurrency(fees.netTransferValue)]
      ];

      let y = 44;
      doc.addImage(logo, "JPEG", 54, y, 144, 57);
      y += 84;
      doc.setTextColor(25, 36, 38);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(18);
      doc.text("External Fund Transfer Fee Calculation", 54, y);
      y += 28;

      y = drawSectionHeading(doc, "A. Batch details", y);
      doc.setTextColor(25, 36, 38);
      doc.setFontSize(10.5);
      [
        ["Participating organization", details.organization],
        ["Calculation date", details.calculationDate],
        ["Transfer value", formatCurrency(details.transferValue)],
        ["Individual payments", String(details.paymentCount)],
        ["Annual fee due", details.annualFeeDue ? "Yes" : "No"],
        ["CPI adjustment", formatCpiDescription(details, fees)]
      ].forEach(([label, value]) => {
        doc.setFont("helvetica", "bold");
        doc.text(`${label}:`, 54, y);
        doc.setFont("helvetica", "normal");
        doc.text(value, 210, y);
        y += 18;
      });

      y += 12;
      y = drawSectionHeading(doc, "B. Administration fee", y);
      doc.setTextColor(25, 36, 38);
      doc.setFontSize(10.5);
      feeRows.forEach(([label, value], index) => {
        doc.setFont("helvetica", index === feeRows.length - 1 ? "bold" : "normal");
        doc.text(label, 54, y);
        doc.text(value, 558, y, { align: "right" });
        y += 19;
      });

      y += 12;
      y = drawSectionHeading(doc, "C. Net transfer value", y);
      doc.setTextColor(25, 36, 38);
      doc.setFontSize(10.5);
      netRows.forEach(([label, value], index) => {
        doc.setFont("helvetica", index === netRows.length - 1 ? "bold" : "normal");
        doc.text(label, 54, y);
        doc.text(value, 558, y, { align: "right" });
        y += 19;
      });

      y += 14;
      doc.setTextColor(25, 36, 38);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(10.5);
      doc.text("Policy and estimate note", 54, y);
      y += 15;
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9.2);
      const note = `Based on ${FEE_RATES.policySource}, with annual June 1 CPI adjustments. This is an internal calculation for one payment batch, not an invoice, approval, tax calculation, or substitute for any required written agreement.`;
      const noteLines = doc.splitTextToSize(note, 504);
      doc.text(noteLines, 54, y);
      y += noteLines.length * 12 + 4;

      const policyPrefix = "GSS By-Laws, Code & Policies:";
      doc.text(policyPrefix, 54, y);
      const policyLinkX = 54 + doc.getTextWidth(policyPrefix) + 4;
      doc.setTextColor(0, 121, 122);
      doc.textWithLink(FEE_RATES.policyUrl, policyLinkX, y, { url: FEE_RATES.policyUrl });
      y += 13;

      doc.setTextColor(25, 36, 38);
      const cpiPrefix = "Vancouver Consumer Price Index (CPI):";
      doc.text(cpiPrefix, 54, y);
      const cpiLinkX = 54 + doc.getTextWidth(cpiPrefix) + 4;
      doc.setTextColor(0, 121, 122);
      doc.textWithLink(FEE_RATES.statCanCpiUrl, cpiLinkX, y, { url: FEE_RATES.statCanCpiUrl });

      doc.setDrawColor(203, 215, 217);
      doc.setLineWidth(0.5);
      doc.line(54, 718, 558, 718);
      doc.setTextColor(82, 96, 102);
      doc.setFontSize(8.5);
      doc.text("Graduate Student Society UBC Vancouver", 54, 734);
      doc.text("225-6371 Crescent Road, Vancouver, BC  V6T 1Z2  |  gss.ubc.ca", 54, 747);
      doc.save(`External Fund Transfer Fee Calculation - ${safeFilename(details.organization)} - ${details.calculationDate}.pdf`);
    } catch (exception) {
      error.textContent = exception.message;
    }
  }

  fields.calculationDate.value = today();
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    try {
      const details = readCalculation();
      const fees = calculateFees(details);
      latestCalculation = { details, fees };
      renderFees(details, fees);
      error.textContent = "";
    } catch (exception) {
      results.hidden = true;
      error.textContent = exception.message;
    }
  });
  downloadButton.addEventListener("click", downloadPdf);
}
