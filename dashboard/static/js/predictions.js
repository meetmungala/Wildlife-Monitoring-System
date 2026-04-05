// predictions.js — AI Behavior Predictions page

const BEHAVIOR_COLOURS = {
  hunting:   { bg: "rgba(248,81,73,0.7)",   border: "#f85149" },
  migrating: { bg: "rgba(30,144,255,0.7)",  border: "#1e90ff" },
  grazing:   { bg: "rgba(63,185,80,0.7)",   border: "#3fb950" },
  resting:   { bg: "rgba(155,89,182,0.7)",  border: "#9b59b6" },
  other:     { bg: "rgba(139,148,158,0.5)", border: "#8b949e" },
};

function behaviorColour(behavior, key) {
  return (BEHAVIOR_COLOURS[behavior] || BEHAVIOR_COLOURS.other)[key];
}

async function fetchJSON(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ------------------------------------------------------------------ //
// Trajectory + predicted-path scatter chart
// ------------------------------------------------------------------ //
let trajectoryChart = null;

function renderTrajectoryChart(observed, predicted) {
  if (typeof Chart === "undefined") return;
  const ctx = document.getElementById("trajectoryChart").getContext("2d");
  if (trajectoryChart) trajectoryChart.destroy();

  trajectoryChart = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Observed",
          data: observed.map((p, i) => ({ x: p.x, y: p.y, t: i })),
          backgroundColor: "rgba(63,185,80,0.6)",
          borderColor: "#3fb950",
          pointRadius: 5,
          showLine: true,
          borderWidth: 1.5,
          tension: 0.3,
        },
        {
          label: "Predicted",
          data: predicted.map((p, i) => ({ x: p.x, y: p.y, t: i })),
          backgroundColor: "rgba(248,81,73,0.6)",
          borderColor: "#f85149",
          pointRadius: 4,
          showLine: true,
          borderDash: [5, 3],
          borderWidth: 1.5,
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#c9d1d9" } } },
      scales: {
        x: { ticks: { color: "#8b949e" }, grid: { color: "#30363d" }, title: { display: true, text: "X", color: "#8b949e" } },
        y: { ticks: { color: "#8b949e" }, grid: { color: "#30363d" }, title: { display: true, text: "Y", color: "#8b949e" } },
      },
    },
  });
}

// ------------------------------------------------------------------ //
// Behavior score breakdown polar / radar chart
// ------------------------------------------------------------------ //
let behaviorChart = null;

function renderBehaviorChart(scores) {
  if (typeof Chart === "undefined") return;
  const ctx = document.getElementById("behaviorChart").getContext("2d");
  if (behaviorChart) behaviorChart.destroy();

  const labels = Object.keys(scores);
  const data   = Object.values(scores);

  behaviorChart = new Chart(ctx, {
    type: "polarArea",
    data: {
      labels: labels.map(l => l.charAt(0).toUpperCase() + l.slice(1)),
      datasets: [{
        data,
        backgroundColor: labels.map(l => behaviorColour(l, "bg")),
        borderColor:     labels.map(l => behaviorColour(l, "border")),
        borderWidth: 1,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#c9d1d9" } } },
      scales: {
        r: { ticks: { color: "#8b949e", backdropColor: "transparent" }, grid: { color: "#30363d" } },
      },
    },
  });
}

// ------------------------------------------------------------------ //
// Run prediction
// ------------------------------------------------------------------ //
document.getElementById("btn-run-prediction").addEventListener("click", async () => {
  const animalId = document.getElementById("input-animal-id").value.trim();
  const species  = document.getElementById("input-species").value;
  const resultEl = document.getElementById("pred-result");

  if (!animalId) {
    resultEl.innerHTML = '<span style="color:var(--danger)">Please enter an Animal ID.</span>';
    resultEl.classList.remove("hidden", "error-state");
    return;
  }

  resultEl.innerHTML = "Running prediction…";
  resultEl.classList.remove("hidden", "error-state");

  try {
    const data = await fetchJSON("/api/predictions/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ animal_id: animalId, species }),
    });

    if (data.error) {
      resultEl.innerHTML = `<span style="color:var(--danger)">⚠ ${data.error}</span>`;
      resultEl.classList.add("error-state");
      return;
    }

    const bLabel = data.behavior || "other";
    resultEl.innerHTML = `
      <p>
        <strong>Behavior:</strong>
        <span class="pred-behavior-badge behavior-${bLabel}">${bLabel}</span>
        &nbsp; <strong>Confidence:</strong> ${(data.confidence * 100).toFixed(1)}%
        &nbsp; <strong>Alerts generated:</strong> ${data.alerts_generated}
      </p>
      <p style="color:var(--text-muted);font-size:0.8rem;margin-top:0.4rem">
        Prediction #${data.prediction_id} &nbsp;|&nbsp; ${data.predicted_positions.length} future positions forecast
      </p>`;
    resultEl.classList.remove("error-state");

    // Fetch recent observed trajectory for this animal to draw the chart
    try {
      const trajData = await fetchJSON(`/api/trajectories/${encodeURIComponent(animalId)}?limit=50`);
      renderTrajectoryChart(trajData.points, data.predicted_positions);
    } catch {
      try { renderTrajectoryChart([], data.predicted_positions); } catch { /* Chart.js unavailable */ }
    }

    // Build behavior score breakdown chart
    if (data.prediction_id) {
      try {
        const behaviors = ["hunting", "migrating", "grazing", "resting", "other"];
        const mainScore = data.confidence;
        const restScore = (1 - mainScore) / (behaviors.length - 1);
        const scores = {};
        behaviors.forEach(b => { scores[b] = b === bLabel ? mainScore : restScore; });
        renderBehaviorChart(scores);
      } catch { /* Chart.js unavailable */ }
    }

    // Refresh alerts and table regardless of chart availability
    loadPredictedAlerts();
    loadRecentPredictions();
  } catch (err) {
    resultEl.innerHTML = `<span style="color:var(--danger)">Error: ${err.message}</span>`;
    resultEl.classList.add("error-state");
  }
});

// ------------------------------------------------------------------ //
// Load recent predictions table
// ------------------------------------------------------------------ //
async function loadRecentPredictions() {
  const tbody = document.getElementById("predictions-body");
  try {
    const data = await fetchJSON("/api/predictions?limit=20");
    if (!data.predictions.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="loading">No predictions yet.</td></tr>';
      return;
    }
    tbody.innerHTML = data.predictions.map(p => `
      <tr>
        <td>${new Date(p.timestamp).toLocaleString()}</td>
        <td>${p.animal_id}</td>
        <td><span class="badge-species badge-${p.species}">${p.species.replace(/_/g, " ")}</span></td>
        <td><span class="pred-behavior-badge behavior-${p.behavior}">${p.behavior}</span></td>
        <td>${(p.confidence * 100).toFixed(1)}%</td>
      </tr>`).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading">Error: ${e.message}</td></tr>`;
  }
}

// ------------------------------------------------------------------ //
// Load predicted alerts
// ------------------------------------------------------------------ //
async function loadPredictedAlerts() {
  const listEl  = document.getElementById("predicted-alerts-list");
  const countEl = document.getElementById("alert-count");
  try {
    const data = await fetchJSON("/api/predicted-alerts?resolved=false&limit=20");
    const alerts = data.predicted_alerts;
    countEl.textContent = alerts.length;

    if (!alerts.length) {
      listEl.innerHTML = '<p class="loading">No active alerts.</p>';
      return;
    }

    listEl.innerHTML = alerts.map(a => `
      <div class="alert-item">
        <div>
          <span class="badge-species badge-${a.species}">${a.species.replace(/_/g, " ")}</span>
          <span class="pred-behavior-badge behavior-${a.behavior}" style="margin-left:0.4rem">${a.behavior}</span>
          &mdash; Animal <strong>${a.animal_id}</strong>
          (confidence ${(a.confidence * 100).toFixed(1)}%)
        </div>
        <div class="alert-time">${new Date(a.timestamp).toLocaleString()}</div>
        <div style="font-size:0.8rem;margin-top:0.3rem;color:var(--text-muted)">${a.message.replace(/\n/g, "<br>")}</div>
        <button class="btn btn-secondary" style="margin-top:0.4rem;font-size:0.75rem;padding:0.25rem 0.6rem"
                onclick="resolveAlert(${a.id}, this)">✔ Resolve</button>
      </div>`).join("");
  } catch (e) {
    listEl.innerHTML = `<p class="loading">Error loading alerts: ${e.message}</p>`;
  }
}

async function resolveAlert(id, btn) {
  btn.disabled = true;
  try {
    await fetchJSON(`/api/predicted-alerts/${id}/resolve`, { method: "PATCH" });
    loadPredictedAlerts();
  } catch (e) {
    btn.disabled = false;
    alert(`Failed to resolve: ${e.message}`);
  }
}

// ------------------------------------------------------------------ //
// Load alert rules
// ------------------------------------------------------------------ //
async function loadAlertRules() {
  const tbody = document.getElementById("rules-body");
  try {
    const data = await fetchJSON("/api/alert-rules");
    if (!data.alert_rules.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="loading">No rules configured.</td></tr>';
      return;
    }
    tbody.innerHTML = data.alert_rules.map(r => `
      <tr>
        <td>${r.name}</td>
        <td>${r.species || "<em>any</em>"}</td>
        <td>${r.behavior || "<em>any</em>"}</td>
        <td>${(r.min_confidence * 100).toFixed(0)}%</td>
        <td>${r.active ? '<span class="badge-alert-yes">✓ Active</span>' : '<span class="badge-alert-no">Off</span>'}</td>
      </tr>`).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading">Error: ${e.message}</td></tr>`;
  }
}

// ── Add rule form toggle ──
document.getElementById("btn-show-rule-form").addEventListener("click", () => {
  document.getElementById("rule-form").classList.remove("hidden");
});
document.getElementById("btn-cancel-rule").addEventListener("click", () => {
  document.getElementById("rule-form").classList.add("hidden");
});

document.getElementById("btn-save-rule").addEventListener("click", async () => {
  const name    = document.getElementById("rule-name").value.trim();
  const species = document.getElementById("rule-species").value.trim() || null;
  const behavior= document.getElementById("rule-behavior").value.trim() || null;
  const conf    = parseFloat(document.getElementById("rule-conf").value);
  if (!name) { alert("Rule name is required."); return; }
  try {
    await fetchJSON("/api/alert-rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, species, behavior, min_confidence: conf }),
    });
    document.getElementById("rule-form").classList.add("hidden");
    loadAlertRules();
  } catch (e) {
    alert(`Failed to save rule: ${e.message}`);
  }
});

// ------------------------------------------------------------------ //
// Bootstrap
// ------------------------------------------------------------------ //
(async () => {
  await Promise.allSettled([
    loadRecentPredictions(),
    loadPredictedAlerts(),
    loadAlertRules(),
  ]);
})();
