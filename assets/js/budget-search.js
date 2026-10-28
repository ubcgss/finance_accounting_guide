// Search box for the Budget Categories page. Data comes from _data/budget_lines.yml,
// which the page include writes to window.BUDGET_LINES.
(function () {
  var data = window.BUDGET_LINES;
  var input = document.getElementById("budget-search-input");
  var results = document.getElementById("budget-search-results");
  if (!data || !input || !results) return;

  var ZOHO_REPORT_URL = "https://expense.zoho.com/app/903421237#/approvals/all/";
  var MAX_RESULTS = 6;

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Score a line against the query words: keywords and examples weigh more than the usage text.
  function score(line, words) {
    var name = (line.code + " " + line.name).toLowerCase();
    var keywords = (line.keywords || []).join(" ").toLowerCase();
    var examples = (line.examples || []).map(function (e) { return e.text; }).join(" ").toLowerCase();
    var usage = (line.usage || "").toLowerCase();
    var total = 0;
    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      var hit = 0;
      if (keywords.indexOf(w) !== -1) hit = Math.max(hit, 4);
      if (name.indexOf(w) !== -1) hit = Math.max(hit, 3);
      if (examples.indexOf(w) !== -1) hit = Math.max(hit, 3);
      if (usage.indexOf(w) !== -1) hit = Math.max(hit, 1);
      if (hit === 0) return 0; // every word must match somewhere
      total += hit;
    }
    return line.finance_only ? total / 2 : total;
  }

  function render(line) {
    var html = '<div class="budget-result">';
    html += '<div class="line">' + escapeHtml(line.code + " - " + line.name) + "</div>";
    html += '<div class="cat">Budget Category for the report title: <code>' +
      escapeHtml(line.budget_category) + "</code></div>";
    if (line.finance_only) {
      html += '<div class="finance-only">Finance only: the Financial Officer posts to this line. ' +
        "Ask before using it.</div>";
    }
    html += "<div>" + escapeHtml(line.usage) + "</div>";
    if (line.examples && line.examples.length) {
      html += "<ul>";
      line.examples.forEach(function (e) {
        html += "<li>" + escapeHtml(e.text);
        if (e.report_id) {
          html += ' (<a href="' + ZOHO_REPORT_URL + encodeURIComponent(e.report_id) +
            '" target="_blank" rel="noopener">' + escapeHtml(e.report_number || "report") + "</a>)";
        }
        html += "</li>";
      });
      html += "</ul>";
    }
    return html + "</div>";
  }

  input.addEventListener("input", function () {
    var words = input.value.toLowerCase().split(/\s+/).filter(function (w) { return w.length > 1; });
    if (!words.length) { results.innerHTML = ""; return; }

    var matches = data.lines
      .map(function (line) { return { line: line, score: score(line, words) }; })
      .filter(function (m) { return m.score > 0; })
      .sort(function (a, b) { return b.score - a.score || a.line.code.localeCompare(b.line.code); })
      .slice(0, MAX_RESULTS);

    if (!matches.length) {
      results.innerHTML = "<p>No match. Ask the Financial Officer before using an " +
        "&quot;Other Expenses&quot; line.</p>";
      return;
    }
    results.innerHTML = matches.map(function (m) { return render(m.line); }).join("") +
      '<p class="fs-2">Example report links open in Zoho for approvers only.</p>';
  });
})();
