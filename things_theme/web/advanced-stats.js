/* Kome advanced statistics.
 *
 * This is deliberately dependency-free. Charts are SVG/HTML generated in the
 * existing Onigiri WebView, period changes use the established ba:* bridge,
 * and every icon is an inline Lucide/Lucide Lab glyph using currentColor.
 */
(function () {
  "use strict";

  function mount() {
    var root = document.querySelector("[data-ba-advanced-stats]");
    if (!root || root.__baMounted) return;
    root.__baMounted = true;

  var state = {
    data: window.__baAdvancedStatsData || null,
    period: window.__baAdvancedStatsPeriod || "30d",
    loading: false,
    revealed: false,
  };
  var revealObserver = null;

  /* Lucide's 24px stroke grammar. `grid` is Lucide Lab's Grid Lines Offset;
     the remaining semantic glyphs come from the core Lucide set. */
  var ICONS = {
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    zap: '<path d="M4 14a1 1 0 0 1-.78-1.63l9-11a.5.5 0 0 1 .87.45l-1.18 6.6A1 1 0 0 0 12.9 10H20a1 1 0 0 1 .78 1.63l-9 11a.5.5 0 0 1-.87-.45l1.18-6.6A1 1 0 0 0 11.1 14z"/>',
    calendar: '<path d="M8 2v4M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/>',
    trend: '<path d="m3 17 6-6 4 4 8-8"/><path d="M14 7h7v7"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    cards: '<rect width="15" height="15" x="3" y="3" rx="2"/><path d="M8 21h11a2 2 0 0 0 2-2V8"/><path d="M7 8h7M7 12h4"/>',
    timer: '<path d="M10 2h4M12 14l3-3"/><circle cx="12" cy="14" r="8"/>',
    sunrise: '<path d="M12 2v8M4.93 10.93l1.41 1.41M2 18h2M20 18h2M17.66 12.34l1.41-1.41"/><path d="M4 22h16M8 18a4 4 0 0 1 8 0"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.42"/>',
    sunset: '<path d="M12 10V2M4.93 10.93l1.41 1.41M2 18h2M20 18h2M17.66 12.34l1.41-1.41"/><path d="M22 22H2M16 18a4 4 0 0 0-8 0"/>',
    moon: '<path d="M20.98 13.02A8.5 8.5 0 0 1 10.98 3a8.5 8.5 0 1 0 10 10.02z"/>',
    book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
    tag: '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
    brain: '<path d="M9.5 4A2.5 2.5 0 0 0 7 6.5v.4a3 3 0 0 0-2 4.6 3 3 0 0 0 1 5.8V18a2 2 0 0 0 3.5 1.3V4zM14.5 4A2.5 2.5 0 0 1 17 6.5v.4a3 3 0 0 1 2 4.6 3 3 0 0 1-1 5.8V18a2 2 0 0 1-3.5 1.3V4z"/><path d="M6.5 10.5h3M14.5 13.5h3M7.5 16.5h2M14.5 8h2"/>',
    rotate: '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>',
    rocket: '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.87 12.87 0 0 1 22 2c0 2.72-.78 7.5-6.05 11a22.35 22.35 0 0 1-3.95 2zM9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/><circle cx="16" cy="8" r="1"/>',
    grid: '<path d="M7 3v18"/><path d="M13 3v18"/><path d="M3 11h18"/><path d="M3 17h18"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  };

  function icon(name, className) {
    return '<svg class="ba-as-icon ' + (className || "") + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" data-icon-set="' + (name === "grid" ? "lucide-lab" : "lucide") + '">' + (ICONS[name] || ICONS.activity) + '</svg>';
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function number(value, digits) {
    var n = Number(value || 0);
    if (!isFinite(n)) n = 0;
    return n.toLocaleString((window.ONIGIRI_LOCALIZATION || {}).locale || "en", {
      maximumFractionDigits: digits == null ? 1 : digits,
    });
  }

  function clamp(value, low, high) {
    return Math.max(low, Math.min(high, Number(value || 0)));
  }

  function pathFor(values, width, height, pad) {
    values = (values || []).map(Number).filter(isFinite);
    if (!values.length) return "";
    var min = Math.min.apply(Math, values);
    var max = Math.max.apply(Math, values);
    var span = max - min || 1;
    return values.map(function (value, index) {
      var x = pad + ((width - pad * 2) * index / Math.max(1, values.length - 1));
      var y = height - pad - ((height - pad * 2) * (value - min) / span);
      return (index ? "L" : window.onigiriText("M")) + x.toFixed(1) + " " + y.toFixed(1);
    }).join(" ");
  }

  function spark(values, className, label) {
    var d = pathFor(values, 320, 96, 6);
    if (!d) return window.onigiriTemplate('<div class="ba-as-empty-chart">No activity in this period</div>');
    return '<svg class="ba-as-spark ' + (className || "") + '" viewBox="0 0 320 96" preserveAspectRatio="none" role="img" aria-label="' + esc(label || window.onigiriText("Trend")) + '">' +
      '<path class="ba-as-gridline" d="M6 24H314M6 48H314M6 72H314"/>' +
      '<path class="ba-as-spark-line" d="' + d + '"/>' +
      '</svg>';
  }

  function periods() {
    var options = [
      [window.onigiriText("today"), window.onigiriText("Today")], ["7d", "7D"], ["30d", "30D"],
      ["90d", "90D"], ["12m", "1Y"], ["all", window.onigiriText("All")],
    ];
    return window.onigiriTemplate('<div class="ba-as-periods" role="group" aria-label="Statistics range">') +
      options.map(function (item) {
        var isActive = state.period === item[0];
        return '<button type="button" class="ba-as-period' + (isActive ? " is-active" : "") + '" data-ba-as-period="' + item[0] + '" aria-pressed="' + isActive + '">' + item[1] + '</button>';
      }).join("") + '</div>';
  }

  function metricCard(name, iconName, value, detail, tone) {
    return '<article class="ba-as-card ba-as-score ba-as-tone-' + tone + '">' +
      '<div class="ba-as-card-kicker">' + icon(iconName) + '<span>' + esc(name) + '</span></div>' +
      '<div class="ba-as-score-value">' + number(value) + '<small>/100</small></div>' +
      '<p>' + esc(detail) + '</p>' +
      '<div class="ba-as-meter" aria-hidden="true"><i style="width:' + clamp(value, 0, 100) + '%"></i></div>' +
      '</article>';
  }

  function renderScores(data) {
    var scores = data.scores || {};
    var activity = data.activity || {};
    return '<div class="ba-as-score-grid">' +
      metricCard(window.onigiriText("Retention"), "target", (scores.retention || {}).value, window.onigiriText("Mature cards remembered"), "accent") +
      metricCard(window.onigiriText("Consistency"), "activity", (scores.consistency || {}).value, number(activity.daysActive, 0) + window.onigiriText(" active days"), "green") +
      metricCard(window.onigiriText("Efficiency"), "zap", (scores.efficiency || {}).value, window.onigiriText("Accuracy balanced with pace"), "gold") +
      '</div>';
  }

  function renderActivity(data) {
    var activity = data.activity || {};
    var mature = data.matureCardStats || {};
    var lapse = data.lapseAnalysis || {};
    var velocity = data.learningVelocity || {};
    var items = [
      ["calendar", window.onigiriText("Current streak"), number(activity.currentStreak, 0), window.onigiriText("days")],
      ["trend", window.onigiriText("Longest streak"), number(activity.longestStreak, 0), window.onigiriText("days")],
      ["brain", window.onigiriText("Mature cards"), number(mature.totalMature, 0), window.onigiriText("cards")],
      ["rotate", window.onigiriText("Lapses"), number(lapse.totalLapses, 0), number(lapse.lapseRate) + "% " + window.onigiriText("rate")],
      ["rocket", window.onigiriText("Learning velocity"), number(velocity.newCardsPerDay), window.onigiriText("new / day")],
    ];
    return window.onigiriTemplate('<section class="ba-as-card ba-as-summary"><div class="ba-as-section-head"><div><span class="ba-as-eyebrow">Activity</span><h3>Study pulse</h3></div></div><div class="ba-as-summary-grid">') +
      items.map(function (item) {
        return '<div class="ba-as-summary-item">' + icon(item[0]) + '<span>' + esc(item[1]) + '</span><strong>' + esc(item[2]) + '</strong><small>' + esc(item[3]) + '</small></div>';
      }).join("") + '</div></section>';
  }

  function renderMetrics(data) {
    var metrics = data.metricsOverTime || {};
    var lines = [
      [window.onigiriText("Retention"), metrics.retention || [], "ba-as-line-accent"],
      [window.onigiriText("Consistency"), metrics.consistency || [], "ba-as-line-green"],
      [window.onigiriText("Efficiency"), metrics.efficiency || [], "ba-as-line-gold"],
    ];
    return window.onigiriTemplate('<section class="ba-as-card ba-as-wide"><div class="ba-as-section-head"><div><span class="ba-as-eyebrow">Trajectory</span><h3>Key metrics over time</h3></div><div class="ba-as-legend">') +
      lines.map(function (line) { return '<span class="' + line[2] + '"><i></i>' + line[0] + '</span>'; }).join("") +
      '</div></div><div class="ba-as-multi-chart">' +
      lines.map(function (line) { return spark(line[1], line[2], line[0] + " · " + window.onigiriText("Trend")); }).join("") +
      '</div></section>';
  }

  function renderUsage(data) {
    var trends = data.usageTrends || {};
    var items = [
      ["timer", window.onigiriText("Duration"), trends.duration || {}, window.onigiriText("min / active day"), "accent"],
      [window.onigiriText("cards"), window.onigiriText("Cards reviewed"), trends.cardsReviewed || {}, window.onigiriText("cards / active day"), "green"],
      ["clock", window.onigiriText("Answer pace"), trends.secondsPerCard || {}, window.onigiriText("seconds / card"), "gold"],
    ];
    return window.onigiriTemplate('<section class="ba-as-block"><div class="ba-as-section-head"><div><span class="ba-as-eyebrow">Volume</span><h3>Usage trends</h3></div></div><div class="ba-as-usage-grid">') +
      items.map(function (item) {
        return '<article class="ba-as-card ba-as-usage ba-as-tone-' + item[4] + '"><div class="ba-as-card-kicker">' + icon(item[0]) + '<span>' + item[1] + '</span></div><strong>' + number(item[2].avg) + '</strong><small>' + item[3] + '</small>' + spark(item[2].data || [], "", item[1] + " · " + window.onigiriText("Trend")) + '</article>';
      }).join("") + '</div></section>';
  }

  function renderTimeOfDay(data) {
    var iconNames = { Morning: "sunrise", Afternoon: "sun", Evening: "sunset", Night: "moon" };
    return window.onigiriTemplate('<section class="ba-as-block"><div class="ba-as-section-head"><div><span class="ba-as-eyebrow">Timing</span><h3>Performance by time of day</h3></div></div><div class="ba-as-time-grid">') +
      (data.timeOfDay || []).map(function (item) {
        return '<article class="ba-as-card ba-as-time">' + icon(iconNames[item.period] || "clock") + '<div><strong>' + esc(window.onigiriText(item.period)) + '</strong><small>' + esc(({"6 AM - 12 PM": "06:00–12:00", "12 PM - 6 PM": "12:00–18:00", "6 PM - 12 AM": "18:00–00:00", "12 AM - 6 AM": "00:00–06:00"})[item.range] || item.range) + '</small></div><b>' + number(item.pct, 0) + window.onigiriTemplate('%</b><div class="ba-as-time-metrics"><span>Retention <strong>') + number(item.retention) + window.onigiriTemplate('%</strong></span><span>Efficiency <strong>') + number(item.efficiency) + '</strong></span></div></article>';
      }).join("") + '</div></section>';
  }

  function performanceTable(title, iconName, rows, isTag) {
    var tableRows = Array.isArray(rows) ? rows : [];
    var id = isTag ? "tags" : "topics";
    var filterLabel = esc(window.onigiriText(isTag ? "Filter tags" : "Filter topics"));
    return '<section class="ba-as-card ba-as-table-card" data-ba-as-table="' + id + window.onigiriTemplate('"><div class="ba-as-section-head"><div><span class="ba-as-eyebrow">Breakdown</span><h3>') + icon(iconName) + esc(title) + '</h3></div><label class="ba-as-search">' + icon("search") + '<input type="search" data-ba-as-search="' + id + '" placeholder="' + filterLabel + '" aria-label="' + filterLabel + window.onigiriTemplate('"></label></div><div class="ba-as-table-scroll"><table><thead><tr><th>Name</th>') + (isTag ? window.onigiriTemplate('<th>Reviews</th>') : '') + window.onigiriTemplate('<th>Retention</th><th>Efficiency</th></tr></thead><tbody>') +
      tableRows.map(function (row) {
        var name = row.name || row.category || row.tag || row.fullTag || window.onigiriText("Untitled");
        return '<tr data-ba-as-name="' + esc(String(name).toLowerCase()) + '"><td title="' + esc(row.fullName || row.fullCategory || row.fullTag || name) + '">' + esc(name) + '</td>' + (isTag ? '<td>' + number(row.reviews || row.reviewCount, 0) + '</td>' : '') + '<td><span class="ba-as-cell-meter"><i style="width:' + clamp(row.retention, 0, 100) + '%"></i></span>' + number(row.retention) + '%</td><td>' + number(row.efficiency) + '</td></tr>';
      }).join("") + '</tbody></table></div></section>';
  }

  function renderSession(data) {
    var session = data.sessionAnalysis || {};
    var dist = session.distribution || [];
    var max = Math.max.apply(Math, dist.map(function (item) { return Number(item.pct || 0); }).concat([1]));
    return window.onigiriTemplate('<section class="ba-as-card"><div class="ba-as-section-head"><div><span class="ba-as-eyebrow">Rhythm</span><h3>') + icon("timer") + window.onigiriTemplate('Session analysis</h3></div></div><div class="ba-as-mini-stats"><span><strong>') + number(session.avgSessionLength, 0) + window.onigiriTemplate('</strong>avg min</span><span><strong>') + number(session.medianSessionLength, 0) + window.onigiriTemplate('</strong>median min</span><span><strong>') + number(session.sessionsPerDay) + window.onigiriTemplate('</strong>sessions / day</span></div><div class="ba-as-horizontal-bars">') +
      dist.map(function (item) { return '<div><span>' + esc(({"6 AM - 12 PM": "06:00–12:00", "12 PM - 6 PM": "12:00–18:00", "6 PM - 12 AM": "18:00–00:00", "12 AM - 6 AM": "00:00–06:00"})[item.range] || item.range) + '</span><i><b style="width:' + (Number(item.pct || 0) / max * 100) + '%"></b></i><strong>' + number(item.pct, 0) + '%</strong></div>'; }).join("") + '</div></section>';
  }

  function renderRetention(data) {
    var interval = data.retentionByInterval || {};
    var labels = interval.labels || [];
    var values = interval.retention || [];
    return window.onigiriTemplate('<section class="ba-as-card"><div class="ba-as-section-head"><div><span class="ba-as-eyebrow">Memory</span><h3>') + icon("brain") + window.onigiriTemplate('Retention by interval</h3></div></div><div class="ba-as-interval-chart">') +
      labels.map(function (label, index) { var value = values[index] || 0; return '<div><strong>' + number(value) + '%</strong><i><b style="height:' + clamp(value, 0, 100) + '%"></b></i><span>' + esc(label) + '</span></div>'; }).join("") +
      (labels.length ? "" : window.onigiriTemplate('<div class="ba-as-empty-chart">No mature reviews in this period</div>')) + '</div></section>';
  }

  function renderWeeklyHeatmap(data) {
    var heat = data.weeklyHeatmap || {};
    var rows = heat.data || [];
    var peak = Math.max.apply(Math, rows.reduce(function (all, row) { return all.concat(row || []); }, []).concat([1]));
    return window.onigiriTemplate('<section class="ba-as-card ba-as-weekly"><div class="ba-as-section-head"><div><span class="ba-as-eyebrow">Schedule</span><h3>') + icon("grid") + window.onigiriTemplate('Weekly study heatmap</h3></div></div><div class="ba-as-week-grid"><div class="ba-as-hours"><span></span><span>00</span><span>06</span><span>12</span><span>18</span><span>23</span></div>') +
      rows.map(function (row, day) {
        return '<div class="ba-as-week-row"><span>' + esc(window.onigiriText((heat.days || [])[day] || "")) + '</span>' + (row || []).map(function (value, hour) { var level = value ? Math.max(1, Math.ceil(Number(value) / peak * 4)) : 0; return '<i class="is-l' + level + '" title="' + esc(window.onigiriText((heat.days || [])[day] || "") + " " + String(hour).padStart(2, "0") + ":00 · " + number(value, 0) + window.onigiriTemplate(" " + window.onigiriText("reviews"))) + '"></i>'; }).join("") + '</div>';
      }).join("") + '</div></section>';
  }

  function renderCollapsed() {
    root.classList.add("is-collapsed");
    root.classList.remove("has-reveal-motion", "is-loading");
    root.innerHTML = window.onigiriTemplate('<button type="button" class="ba-as-reveal-button" data-ba-as-reveal>See Kome insights</button>');
    root.querySelector("[data-ba-as-reveal]").addEventListener("click", function (event) {
      var button = event.currentTarget;
      if (state.loading) return;
      state.loading = true;
      root.classList.add("is-loading");
      button.textContent = window.onigiriText("Loading Kome insights");
      try { pycmd("ba:advanced-stats-reveal"); }
      catch (error) { window.__baAdvancedStatsError(String(error)); }
    });
  }

  /* One observer handles every card. Opacity and translate are compositor-only,
     and each node is unobserved as soon as it arrives. */
  function prepareScrollReveals() {
    if (revealObserver) revealObserver.disconnect();
    root.classList.remove("has-reveal-motion");
    var reduced = window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced || !window.IntersectionObserver) return;

    var cards = root.querySelectorAll(".ba-as-card");
    if (!cards.length) return;
    root.classList.add("has-reveal-motion");
    Array.prototype.forEach.call(cards, function (card) {
      card.setAttribute("data-ba-as-scroll-reveal", "");
    });
    revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        revealObserver.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -7% 0px", threshold: 0.06 });
    Array.prototype.forEach.call(cards, function (card) {
      revealObserver.observe(card);
    });
  }

  function render() {
    if (!state.revealed) {
      renderCollapsed();
      return;
    }
    root.classList.remove("is-collapsed");
    root.classList.toggle("is-loading", state.loading);
    var data = state.data || {};
    var error = root.getAttribute("data-error");
    if (error) {
      root.classList.remove("has-reveal-motion");
      root.innerHTML = '<div class="ba-as-card ba-as-error">' + icon("info") + window.onigiriTemplate('<div><strong>Advanced statistics could not load</strong><span>') + esc(error) + '</span></div></div>';
      return;
    }
    root.innerHTML = window.onigiriTemplate('<header class="ba-as-header"><h2 class="ba-as-title">Things Insights</h2>') + periods() + '</header>' +
      renderScores(data) + renderActivity(data) + renderMetrics(data) +
      renderTimeOfDay(data) + renderUsage(data) +
      '<div class="ba-as-two">' + renderSession(data) + renderRetention(data) + '</div>' +
      renderWeeklyHeatmap(data) +
      '<div class="ba-as-two ba-as-tables">' + performanceTable(window.onigiriText("Performance by topic"), "book", data.topics, false) + performanceTable(window.onigiriText("Performance by tag"), "tag", data.tagPerformance, true) + '</div>';
    bind();
    prepareScrollReveals();
  }

  function bind() {
    Array.prototype.forEach.call(root.querySelectorAll("[data-ba-as-period]"), function (button) {
      button.addEventListener("click", function () {
        var period = button.getAttribute("data-ba-as-period");
        if (!period || period === state.period || state.loading) return;
        state.loading = true;
        root.classList.add("is-loading");
        try { pycmd("ba:advanced-stats-period:" + period); }
        catch (error) { window.__baAdvancedStatsError(String(error)); }
      });
    });
    Array.prototype.forEach.call(root.querySelectorAll("[data-ba-as-search]"), function (input) {
      input.addEventListener("input", function () {
        var table = root.querySelector('[data-ba-as-table="' + input.getAttribute("data-ba-as-search") + '"]');
        var needle = input.value.trim().toLowerCase();
        if (!table) return;
        Array.prototype.forEach.call(table.querySelectorAll("tbody tr"), function (row) {
          row.hidden = needle && (row.getAttribute("data-ba-as-name") || "").indexOf(needle) < 0;
        });
      });
    });
  }

  window.__baSetAdvancedStats = function (data, period) {
    state.data = data || {};
    state.period = period || state.period;
    state.loading = false;
    state.revealed = true;
    root.removeAttribute("data-error");
    render();
  };

  window.__baAdvancedStatsError = function (message) {
    state.loading = false;
    state.revealed = true;
    root.setAttribute("data-error", message || window.onigiriText("Unknown error"));
    render();
  };

    render();
  }

  /* Anki places registered web_content.js assets in the document head. The
     stats mount lives later in DeckBrowserContent.stats, so querying it at
     module evaluation time races the body parser and leaves an empty node.
     Mount at the same lifecycle boundary as Kome's deck-list scripts. */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
