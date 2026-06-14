const palette = {
  demand: "#20324a",
  netLoad: "#db6b3d",
  residualAfterNuclear: "#7267d9",
  COL: "#4f5962",
  NG: "#bd744c",
  NUC: "#7267d9",
  OIL: "#a89d86",
  OTH: "#7b8b87",
  SUN: "#e7b947",
  WAT: "#4d8f9f",
  WND: "#75a884",
};

const $ = (selector) => document.querySelector(selector);
const number = (value) => Math.round(value).toLocaleString("en-US");

async function request(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error((await response.json()).detail || "Request failed");
  return response.json();
}

function svgFrame(width, height, yMax, content) {
  const left = 56, right = 16, top = 16, bottom = 34;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const x = (hour) => left + (plotWidth * hour) / 23;
  const y = (value) => top + plotHeight * (1 - value / yMax);
  const lines = [];
  for (let value = 0; value <= yMax; value += 5000) {
    lines.push(`<line x1="${left}" y1="${y(value)}" x2="${width - right}" y2="${y(value)}" stroke="#e5e9e5"/>`);
    lines.push(`<text x="${left - 8}" y="${y(value) + 4}" text-anchor="end" fill="#839093" font-size="11">${value / 1000}k</text>`);
  }
  for (let hour = 0; hour < 24; hour += 3) {
    lines.push(`<text x="${x(hour)}" y="${height - 10}" text-anchor="middle" fill="#839093" font-size="11">${String(hour).padStart(2, "0")}:00</text>`);
  }
  return { markup: `<svg viewBox="0 0 ${width} ${height}" role="img">${lines.join("")}${content({ x, y, plotHeight, top })}</svg>`, x, y };
}

function line(points, x, y, color) {
  return `<polyline points="${points.map((point) => `${x(point.hour)},${y(point.value)}`).join(" ")}" fill="none" stroke="${color}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>`;
}

function renderDuckCurve(profile) {
  const yMax = Math.ceil(Math.max(...profile.map((row) => row.demand)) / 5000) * 5000;
  $("#duck-chart").innerHTML = svgFrame(1140, 360, yMax, ({ x, y }) => [
    line(profile.map((row) => ({ hour: row.hour, value: row.demand })), x, y, palette.demand),
    line(profile.map((row) => ({ hour: row.hour, value: row.netLoad })), x, y, palette.netLoad),
    line(profile.map((row) => ({ hour: row.hour, value: row.residualAfterNuclear })), x, y, palette.residualAfterNuclear),
  ].join("")).markup;
}

function renderMix(profiles) {
  const positiveProfiles = profiles.map((profile) => ({ ...profile, values: profile.values.map((value) => Math.max(0, value)) }));
  const totals = Array.from({ length: 24 }, (_, hour) => positiveProfiles.reduce((sum, profile) => sum + profile.values[hour], 0));
  const yMax = Math.ceil(Math.max(...totals) / 5000) * 5000;
  $("#mix-chart").innerHTML = svgFrame(720, 290, yMax, ({ x, y }) => {
    const running = Array(24).fill(0);
    return positiveProfiles.map((profile) => {
      const lower = [...running];
      profile.values.forEach((value, hour) => running[hour] += value);
      const upper = running.map((value, hour) => `${x(hour)},${y(value)}`);
      const bottom = lower.map((value, hour) => `${x(23 - hour)},${y(lower[23 - hour])}`);
      return `<polygon points="${[...upper, ...bottom].join(" ")}" fill="${palette[profile.fuelType] || "#9da9a8"}" opacity=".86"/>`;
    }).join("");
  }).markup;
  $("#mix-legend").innerHTML = positiveProfiles.map((profile) => `<span><i style="background:${palette[profile.fuelType] || "#9da9a8"}"></i>${profile.fuelName}</span>`).join("");
}

function renderOutages(days) {
  const max = Math.max(...days.map((day) => day.outageMw), 1);
  $("#outage-chart").innerHTML = `<svg viewBox="0 0 560 290" role="img">${days.map((day, index) => {
    const width = 500 / days.length, height = 215 * day.outageMw / max;
    return `<rect x="${42 + index * width}" y="${240 - height}" width="${Math.max(2, width - 2)}" height="${height}" rx="2" fill="#7267d9" opacity=".72"/>`;
  }).join("")}<line x1="42" y1="240" x2="542" y2="240" stroke="#cbd3d1"/><text x="42" y="268" fill="#839093" font-size="11">Selected date range</text></svg>`;
}

function renderSummary(summary) {
  const metrics = [
    ["Peak demand", `${number(summary.peakDemandMwh)} MWh`],
    ["Minimum net load", `${number(summary.minimumNetLoadMwh)} MWh`],
    ["Steepest hourly ramp", `${number(summary.steepestHourlyRampMwh)} MWh`],
    ["Average nuclear", `${number(summary.averageNuclearMwh)} MWh`],
  ];
  $("#summary").innerHTML = metrics.map(([label, value]) => `<article class="metric"><span>${label}</span><strong>${value}</strong></article>`).join("");
}

async function loadAuthorities() {
  const authorities = await request("/api/authorities");
  $("#respondent").innerHTML = authorities.map((authority) => `<option value="${authority.respondent}">${authority.respondent}</option>`).join("");
}

async function loadDashboard() {
  const params = new URLSearchParams({ respondent: $("#respondent").value, start: $("#start").value, end: $("#end").value });
  const data = await request(`/api/dashboard?${params}`);
  renderSummary(data.summary);
  renderDuckCurve(data.duckCurveProfile);
  renderMix(data.generationMixProfile);
  renderOutages(data.outageContext.days);
  $("#freshness").textContent = new Date(data.freshness).toLocaleString();
  $("#coverage").textContent = `${data.coverage.hourlyRows.toLocaleString()} hourly observations`;
  $("#max-outage").textContent = `${number(data.outageContext.maximumOutageMw)} MW max outage`;
}

$("#controls").addEventListener("submit", async (event) => {
  event.preventDefault();
  try { await loadDashboard(); } catch (error) { $("#summary").innerHTML = `<p class="error">${error.message}</p>`; }
});

(async () => {
  try { await loadAuthorities(); await loadDashboard(); }
  catch (error) { $("#summary").innerHTML = `<p class="error">${error.message}</p>`; }
})();

