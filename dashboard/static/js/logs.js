// logs.js — Detection Logs Page

let currentPage = 1;
const PER_PAGE = 20;

function formatSpeciesBadge(species) {
  const key = species.toLowerCase().replace(/ /g, "_");
  return `<span class="badge-species badge-${key}">${species.replace(/_/g, " ")}</span>`;
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function loadAlerts() {
  const data = await fetchJSON("/api/alerts?resolved=false&limit=20");
  const panel = document.getElementById("alerts-list");
  const countBadge = document.getElementById("alert-count");

  countBadge.textContent = data.alerts.length;

  if (!data.alerts.length) {
    panel.innerHTML = "<p style='color:var(--text-muted);font-size:.875rem;'>No active alerts 🎉</p>";
    return;
  }

  panel.innerHTML = data.alerts.map(a => `
    <div class="alert-item">
      <strong>${a.species.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</strong>
      &mdash; ${a.message.split("\n")[0].replace("[ALERT] ", "")}
      <div class="alert-time">${new Date(a.timestamp).toLocaleString()}</div>
    </div>`).join("");
}

async function loadDetections(page = 1) {
  currentPage = page;
  const species = document.getElementById("filter-species").value;
  const days    = document.getElementById("filter-days").value;

  let url = `/api/detections?page=${page}&limit=${PER_PAGE}`;
  if (species) url += `&species=${encodeURIComponent(species)}`;
  if (days)    url += `&days=${days}`;

  const data = await fetchJSON(url);
  const tbody = document.getElementById("logs-body");

  if (!data.detections.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="loading">No detections found.</td></tr>';
    document.getElementById("pagination").innerHTML = "";
    return;
  }

  tbody.innerHTML = data.detections.map(d => `
    <tr>
      <td>${d.id}</td>
      <td>${new Date(d.timestamp).toLocaleString()}</td>
      <td>${formatSpeciesBadge(d.species)}</td>
      <td>${(d.confidence * 100).toFixed(1)}%</td>
      <td>${d.location || "—"}</td>
      <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${d.source || "—"}</td>
      <td>${d.alert_sent
        ? '<span class="badge-alert-yes">✓ Yes</span>'
        : '<span class="badge-alert-no">No</span>'}</td>
    </tr>`).join("");

  // Pagination
  const pagination = document.getElementById("pagination");
  pagination.innerHTML = "";
  for (let p = 1; p <= data.pages; p++) {
    const btn = document.createElement("button");
    btn.textContent = p;
    if (p === data.page) btn.classList.add("active");
    btn.addEventListener("click", () => loadDetections(p));
    pagination.appendChild(btn);
  }
}

document.getElementById("btn-filter").addEventListener("click", () => loadDetections(1));

(async () => {
  try { await loadAlerts();     } catch (e) { console.error("Alerts load error:", e); }
  try { await loadDetections(); } catch (e) { console.error("Detections load error:", e); }
})();
