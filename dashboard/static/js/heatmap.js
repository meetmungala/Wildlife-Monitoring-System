// heatmap.js — Animal Movement Heatmap Visualization

const SPECIES_COLOURS = {
  tiger:        { color: "#ff8c00", alpha: 0.7 },
  elephant:     { color: "#1e90ff", alpha: 0.7 },
  rhinoceros:   { color: "#f85149", alpha: 0.7 },
  snow_leopard: { color: "#9b59b6", alpha: 0.7 },
};

function getSpeciesColor(species) {
  const s = species.toLowerCase().replace(/ /g, "_");
  return SPECIES_COLOURS[s] || { color: "#3fb950", alpha: 0.7 };
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function drawHeatmap(canvas, heatmapData, topAreas) {
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;

  // Clear canvas
  ctx.fillStyle = "#0d1117";
  ctx.fillRect(0, 0, width, height);

  if (!heatmapData || heatmapData.length === 0) {
    ctx.fillStyle = "#8b949e";
    ctx.font = "16px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("No movement data available", width / 2, height / 2);
    return;
  }

  // Find data bounds
  const xValues = heatmapData.map(d => d.x);
  const yValues = heatmapData.map(d => d.y);
  const minX = Math.min(...xValues);
  const maxX = Math.max(...xValues);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);

  const xRange = maxX - minX || 1;
  const yRange = maxY - minY || 1;

  // Create density grid
  const gridSize = 20;
  const gridWidth = Math.ceil(width / gridSize);
  const gridHeight = Math.ceil(height / gridSize);
  const densityGrid = Array(gridHeight).fill(0).map(() => Array(gridWidth).fill(0));

  // Populate density grid
  heatmapData.forEach(point => {
    const x = Math.floor(((point.x - minX) / xRange) * (gridWidth - 1));
    const y = Math.floor(((point.y - minY) / yRange) * (gridHeight - 1));
    if (x >= 0 && x < gridWidth && y >= 0 && y < gridHeight) {
      densityGrid[y][x]++;
    }
  });

  // Find max density for normalization
  const maxDensity = Math.max(...densityGrid.flat());

  // Draw heatmap with gradient
  for (let y = 0; y < gridHeight; y++) {
    for (let x = 0; x < gridWidth; x++) {
      const density = densityGrid[y][x];
      if (density > 0) {
        const intensity = density / maxDensity;

        // Color gradient from blue (low) to yellow to red (high)
        let r, g, b;
        if (intensity < 0.5) {
          // Blue to yellow
          const t = intensity * 2;
          r = Math.floor(t * 255);
          g = Math.floor(t * 255);
          b = Math.floor((1 - t) * 255);
        } else {
          // Yellow to red
          const t = (intensity - 0.5) * 2;
          r = 255;
          g = Math.floor((1 - t) * 255);
          b = 0;
        }

        const alpha = 0.4 + (intensity * 0.6);
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
        ctx.fillRect(x * gridSize, y * gridSize, gridSize, gridSize);
      }
    }
  }

  // Draw grid overlay
  ctx.strokeStyle = "rgba(139, 148, 158, 0.1)";
  ctx.lineWidth = 1;
  for (let x = 0; x <= width; x += gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 0; y <= height; y += gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  // Mark top active areas
  if (topAreas && topAreas.length > 0) {
    topAreas.slice(0, 5).forEach((area, index) => {
      const x = Math.floor(((area.x - minX) / xRange) * width);
      const y = Math.floor(((area.y - minY) / yRange) * height);

      // Draw marker
      ctx.fillStyle = "#f85149";
      ctx.beginPath();
      ctx.arc(x, y, 8, 0, 2 * Math.PI);
      ctx.fill();

      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Draw rank label
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(`#${index + 1}`, x, y + 4);
    });
  }
}

function formatSpeciesBadge(species) {
  const key = species.toLowerCase().replace(/ /g, "_");
  return `<span class="badge-species badge-${key}">${species.replace(/_/g, " ")}</span>`;
}

function classifyZone(count, speciesData) {
  if (count > 100) return "🔥 High Activity";
  if (count > 50) return "⚡ Medium Activity";
  return "📍 Low Activity";
}

async function loadHeatmapData() {
  const days = document.getElementById("period-select").value;
  const species = document.getElementById("species-filter").value;

  let url = `/api/analytics/heatmap?days=${days}`;
  if (species) {
    url += `&species=${encodeURIComponent(species)}`;
  }

  const data = await fetchJSON(url);

  // Update stats
  document.getElementById("stat-total-points").textContent = data.total_points.toLocaleString();
  document.getElementById("stat-species-count").textContent = data.species_stats.length;
  document.getElementById("stat-active-areas").textContent = data.top_active_areas.length;

  // Draw heatmap
  const canvas = document.getElementById("heatmap-canvas");
  drawHeatmap(canvas, data.heatmap_data, data.top_active_areas);

  // Populate active areas table
  const tbody = document.getElementById("active-areas-body");
  if (!data.top_active_areas.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="loading">No active areas detected.</td></tr>';
  } else {
    tbody.innerHTML = data.top_active_areas.map((area, idx) => {
      const dominantSpecies = Object.entries(area.species).sort((a, b) => b[1] - a[1])[0];
      return `
        <tr>
          <td><strong>#${idx + 1}</strong></td>
          <td>(${area.x}, ${area.y})</td>
          <td><strong>${area.count}</strong> movements</td>
          <td>${dominantSpecies ? formatSpeciesBadge(dominantSpecies[0]) : "—"}</td>
          <td>${classifyZone(area.count, area.species)}</td>
        </tr>`;
    }).join("");
  }

  // Display migration info
  const migrationInfo = document.getElementById("migration-info");
  if (data.species_stats.length === 0) {
    migrationInfo.innerHTML = '<p class="loading">No migration data available.</p>';
  } else {
    migrationInfo.innerHTML = `
      <div class="migration-stats">
        ${data.species_stats.map(stat => `
          <div class="migration-card">
            <div class="migration-species">${formatSpeciesBadge(stat.species)}</div>
            <div class="migration-data">
              <strong>${stat.animal_count}</strong> individual${stat.animal_count !== 1 ? 's' : ''} tracked
              <br>
              <strong>${stat.point_count.toLocaleString()}</strong> movement points recorded
            </div>
          </div>
        `).join("")}
      </div>
    `;
  }

  // Identify dangerous zones (high activity areas or specific behaviors)
  const dangerZonesList = document.getElementById("danger-zones-list");
  const potentialDangerZones = data.top_active_areas.filter(area => area.count > 80);

  if (potentialDangerZones.length === 0) {
    dangerZonesList.innerHTML = '<p style="color: #3fb950;">✓ No critical danger zones detected in this period.</p>';
  } else {
    dangerZonesList.innerHTML = `
      <div class="danger-zones-grid">
        ${potentialDangerZones.map(zone => `
          <div class="danger-zone-card">
            <div class="danger-icon">⚠️</div>
            <div class="danger-info">
              <strong>Zone at (${zone.x}, ${zone.y})</strong>
              <p>${zone.count} movements detected — requires monitoring</p>
              <small>Dominant: ${Object.keys(zone.species).join(", ")}</small>
            </div>
          </div>
        `).join("")}
      </div>
    `;
  }
}

async function loadSpeciesOptions() {
  try {
    const data = await fetchJSON("/api/analytics/heatmap?days=365");
    const speciesFilter = document.getElementById("species-filter");

    data.species_stats.forEach(stat => {
      const option = document.createElement("option");
      option.value = stat.species;
      option.textContent = stat.species.replace(/_/g, " ");
      speciesFilter.appendChild(option);
    });
  } catch (e) {
    console.error("Failed to load species options:", e);
  }
}

// Event listeners
document.getElementById("refresh-btn").addEventListener("click", loadHeatmapData);
document.getElementById("period-select").addEventListener("change", loadHeatmapData);
document.getElementById("species-filter").addEventListener("change", loadHeatmapData);

// Initial load
(async () => {
  try {
    await loadSpeciesOptions();
    await loadHeatmapData();
  } catch (e) {
    console.error("Heatmap load error:", e);
    document.getElementById("heatmap-stats").innerHTML =
      '<div class="error-message">Failed to load heatmap data. Please try again later.</div>';
  }
})();
