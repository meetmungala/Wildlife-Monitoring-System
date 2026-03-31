// dashboard.js — Analytics Dashboard

const SPECIES_COLOURS = {
  tiger:        { bg: "rgba(255,140,0,0.7)",  border: "#ff8c00" },
  elephant:     { bg: "rgba(30,144,255,0.7)", border: "#1e90ff" },
  rhinoceros:   { bg: "rgba(248,81,73,0.7)",  border: "#f85149" },
  snow_leopard: { bg: "rgba(155,89,182,0.7)", border: "#9b59b6" },
};

function getColour(species, key) {
  const s = species.toLowerCase().replace(/ /g, "_");
  return (SPECIES_COLOURS[s] || { bg: "rgba(63,185,80,0.7)", border: "#3fb950" })[key];
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function formatSpeciesBadge(species) {
  const key = species.toLowerCase().replace(/ /g, "_");
  return `<span class="badge-species badge-${key}">${species.replace(/_/g, " ")}</span>`;
}

async function loadSummary() {
  const data = await fetchJSON("/api/analytics/summary?days=7");

  document.getElementById("stat-total").textContent   = data.total_detections;
  document.getElementById("stat-alerts").textContent  = data.unresolved_alerts;
  document.getElementById("stat-species").textContent = data.species_counts.length;

  // Species bar chart
  const labels  = data.species_counts.map(d => d.species.replace(/_/g, " "));
  const counts  = data.species_counts.map(d => d.count);
  const bgColors = data.species_counts.map(d => getColour(d.species, "bg"));
  const borders  = data.species_counts.map(d => getColour(d.species, "border"));

  const speciesCtx = document.getElementById("speciesChart").getContext("2d");
  new Chart(speciesCtx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Detections",
        data: counts,
        backgroundColor: bgColors,
        borderColor: borders,
        borderWidth: 1,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#8b949e" }, grid: { color: "#30363d" } },
        y: { ticks: { color: "#8b949e" }, grid: { color: "#30363d" }, beginAtZero: true },
      },
    },
  });

  // Recent detections table
  const tbody = document.getElementById("recent-body");
  if (!data.recent_detections.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="loading">No detections yet.</td></tr>';
    return;
  }
  tbody.innerHTML = data.recent_detections.map(d => `
    <tr>
      <td>${new Date(d.timestamp).toLocaleString()}</td>
      <td>${formatSpeciesBadge(d.species)}</td>
      <td>${(d.confidence * 100).toFixed(1)}%</td>
      <td>${d.location || "—"}</td>
      <td>${d.alert_sent
        ? '<span class="badge-alert-yes">✓ Yes</span>'
        : '<span class="badge-alert-no">No</span>'}</td>
    </tr>`).join("");
}

async function loadTimeline() {
  const data = await fetchJSON("/api/analytics/timeline?days=7");

  // Collect unique dates and species
  const datesSet   = new Set();
  const speciesSet = new Set();
  data.timeline.forEach(r => { datesSet.add(r.date); speciesSet.add(r.species); });

  const dates   = [...datesSet].sort();
  const species = [...speciesSet];

  // Build per-species datasets
  const datasets = species.map(sp => {
    const countMap = {};
    data.timeline.filter(r => r.species === sp).forEach(r => { countMap[r.date] = r.count; });
    return {
      label: sp.replace(/_/g, " "),
      data: dates.map(d => countMap[d] || 0),
      borderColor: getColour(sp, "border"),
      backgroundColor: getColour(sp, "bg"),
      tension: 0.3,
      fill: false,
    };
  });

  const ctx = document.getElementById("timelineChart").getContext("2d");
  new Chart(ctx, {
    type: "line",
    data: { labels: dates, datasets },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#c9d1d9" } } },
      scales: {
        x: { ticks: { color: "#8b949e" }, grid: { color: "#30363d" } },
        y: { ticks: { color: "#8b949e" }, grid: { color: "#30363d" }, beginAtZero: true },
      },
    },
  });
}

(async () => {
  try { await loadSummary(); }  catch (e) { console.error("Summary load error:", e); }
  try { await loadTimeline(); } catch (e) { console.error("Timeline load error:", e); }
})();
