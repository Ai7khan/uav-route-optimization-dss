const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
const W = 13.333, H = 7.5;

// --- palette (matches the product's command-center theme) ---
const BG = "0B1220", PANEL = "16223A", PANEL2 = "1E2C49";
const ACC = "4DA3FF", GREEN = "33D171", AMBER = "F5B942", RED = "FF5D5D";
const TEXT = "E8EEF7", MUTED = "90A4C4", LINE = "2A3A5C";
const HF = "Arial", BF = "Calibri";

const bg = (s) => s.background = { color: BG };
function card(s, x, y, w, h, fill = PANEL) {
  s.addShape(p.ShapeType.roundRect, { x, y, w, h, fill: { color: fill }, line: { color: LINE, width: 1 }, rectRadius: 0.09,
    shadow: { type: "outer", color: "000000", opacity: 0.35, blur: 8, offset: 3, angle: 90 } });
}
function eyebrow(s, t, x, y, color = ACC) {
  s.addText(t.toUpperCase(), { x, y, w: 6, h: 0.3, isTextBox: true, margin: 0, fontFace: HF, fontSize: 12, bold: true, color, charSpacing: 3 });
}
function dot(s, x, y, color, d = 0.16) {
  s.addShape(p.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color } });
}

// ============ SLIDE 1 — TITLE ============
(() => {
  const s = p.addSlide(); bg(s);
  // subtle grid accent squares top-right
  for (let i = 0; i < 6; i++) for (let j = 0; j < 3; j++)
    s.addShape(p.ShapeType.rect, { x: 10.6 + i * 0.46, y: 0.5 + j * 0.46, w: 0.34, h: 0.34,
      fill: { color: PANEL2 }, line: { color: LINE, width: 0.5 } });
  eyebrow(s, "Defense-Tech Hackathon · Problem 8", 0.9, 1.7, ACC);
  s.addText("UAV Route Optimization DSS", { x: 0.85, y: 2.1, w: 11.6, h: 1.5, isTextBox: true, margin: 0,
    fontFace: HF, fontSize: 52, bold: true, color: TEXT });
  s.addText([
    { text: "Real-time route planning under ", options: { color: MUTED } },
    { text: "changing weather", options: { color: ACC, bold: true } },
    { text: " and ", options: { color: MUTED } },
    { text: "air-defense activity", options: { color: RED, bold: true } },
  ], { x: 0.9, y: 3.5, w: 11, h: 0.6, isTextBox: true, margin: 0, fontFace: BF, fontSize: 22 });

  // three headline stat chips
  const chips = [
    ["10.9×", "lower replan latency", ACC],
    ["-39%", "weather forecast RMSE", GREEN],
    ["+22 pts", "AD-activity prediction", AMBER],
  ];
  chips.forEach((c, i) => {
    const x = 0.9 + i * 3.95;
    card(s, x, 4.5, 3.6, 1.5);
    s.addText(c[0], { x: x + 0.3, y: 4.7, w: 3, h: 0.7, isTextBox: true, margin: 0, fontFace: HF, fontSize: 34, bold: true, color: c[2] });
    s.addText(c[1], { x: x + 0.3, y: 5.42, w: 3.1, h: 0.4, isTextBox: true, margin: 0, fontFace: BF, fontSize: 13, color: MUTED });
  });
  s.addText("Working prototype · 21 passing tests · runs from one command", { x: 0.9, y: 6.5, w: 11, h: 0.4, isTextBox: true, margin: 0, fontFace: BF, fontSize: 13, italic: true, color: MUTED });
  s.addNotes("Decision support system that re-optimizes UAV routes in real time as weather and air-defense conditions change. All data simulated per the brief.");
})();

// ============ SLIDE 2 — THE PROBLEM ============
(() => {
  const s = p.addSlide(); bg(s);
  eyebrow(s, "The problem", 0.9, 0.6);
  s.addText("Static plans fail against a dynamic battlefield", { x: 0.85, y: 0.95, w: 11.6, h: 0.8, isTextBox: true, margin: 0, fontFace: HF, fontSize: 34, bold: true, color: TEXT });

  const rows = [
    ["Weather changes in flight", "Wind, low visibility and precipitation shift the safe corridor and burn fuel — but pre-set routes ignore it.", AMBER, "W"],
    ["Air defense switches on", "SAM/radar sites illuminate intermittently. A route that was safe at takeoff can fly straight into a live threat.", RED, "AD"],
    ["Plans are computed once", "Conventional planners fix a route on pre-set parameters and never re-optimize — raising detection and loss risk.", ACC, "1×"],
  ];
  rows.forEach((r, i) => {
    const y = 2.0 + i * 1.55;
    card(s, 0.9, y, 11.5, 1.35);
    s.addShape(p.ShapeType.ellipse, { x: 1.2, y: y + 0.34, w: 0.66, h: 0.66, fill: { color: r[2] } });
    s.addText(r[3], { x: 1.2, y: y + 0.34, w: 0.66, h: 0.66, isTextBox: true, margin: 0, align: "center", valign: "middle", fontFace: HF, fontSize: 15, bold: true, color: "0B1220" });
    s.addText(r[0], { x: 2.15, y: y + 0.22, w: 9.9, h: 0.45, isTextBox: true, margin: 0, fontFace: HF, fontSize: 19, bold: true, color: TEXT });
    s.addText(r[1], { x: 2.15, y: y + 0.66, w: 9.9, h: 0.6, isTextBox: true, margin: 0, fontFace: BF, fontSize: 14, color: MUTED });
  });
  s.addText("Goal: minimize detection risk while meeting time, fuel and altitude constraints — continuously.", { x: 0.9, y: 6.85, w: 11.5, h: 0.4, isTextBox: true, margin: 0, fontFace: BF, fontSize: 14, italic: true, color: ACC });
})();

// ============ SLIDE 3 — SOLUTION PIPELINE ============
(() => {
  const s = p.addSlide(); bg(s);
  eyebrow(s, "Our solution", 0.9, 0.6);
  s.addText("A five-stage real-time decision pipeline", { x: 0.85, y: 0.95, w: 11.8, h: 0.8, isTextBox: true, margin: 0, fontFace: HF, fontSize: 34, bold: true, color: TEXT });

  const stages = [
    ["Simulate", "Weather fields + air-defense sites + UAV telemetry", GREEN],
    ["Forecast", "Trained ML predicts weather & threats 6 min ahead", ACC],
    ["Score risk", "Detection probability + weather hazard cost field", AMBER],
    ["Optimize", "Adaptive A* / D* Lite, multi-objective weights", RED],
    ["Visualize", "Live operator dashboard, routes & risk", ACC],
  ];
  const cw = 2.18, gap = 0.2, x0 = 0.9, y = 2.2, ch = 2.6;
  stages.forEach((st, i) => {
    const x = x0 + i * (cw + gap);
    card(s, x, y, cw, ch, PANEL);
    s.addShape(p.ShapeType.ellipse, { x: x + cw / 2 - 0.33, y: y + 0.3, w: 0.66, h: 0.66, fill: { color: st[2] } });
    s.addText(String(i + 1), { x: x + cw / 2 - 0.33, y: y + 0.3, w: 0.66, h: 0.66, isTextBox: true, margin: 0, align: "center", valign: "middle", fontFace: HF, fontSize: 22, bold: true, color: "0B1220" });
    s.addText(st[0], { x: x + 0.1, y: y + 1.1, w: cw - 0.2, h: 0.4, isTextBox: true, margin: 0, align: "center", fontFace: HF, fontSize: 16, bold: true, color: TEXT });
    s.addText(st[1], { x: x + 0.15, y: y + 1.55, w: cw - 0.3, h: 0.95, isTextBox: true, margin: 0, align: "center", fontFace: BF, fontSize: 12, color: MUTED });
    if (i < stages.length - 1)
      s.addShape(p.ShapeType.line, { x: x + cw + 0.01, y: y + ch / 2, w: 0.18, h: 0, line: { color: ACC, width: 2, endArrowType: "triangle" } });
  });
  card(s, 0.9, 5.35, 11.5, 1.5, PANEL2);
  s.addText("Why it wins", { x: 1.2, y: 5.55, w: 4, h: 0.35, isTextBox: true, margin: 0, fontFace: HF, fontSize: 14, bold: true, color: ACC });
  s.addText([
    { text: "Most planners run A* once. Ours re-optimizes every tick — ", options: { color: TEXT } },
    { text: "incremental D* Lite repairs the plan in ~0 ms as conditions drift", options: { color: ACC, bold: true } },
    { text: ", and the ML forecast lets the UAV avoid a SAM ", options: { color: TEXT } },
    { text: "before it even activates.", options: { color: GREEN, bold: true } },
  ], { x: 1.2, y: 5.95, w: 11, h: 0.8, isTextBox: true, margin: 0, fontFace: BF, fontSize: 15 });
})();

// ============ SLIDE 4 — INNOVATION: ADAPTIVE REPLANNING ============
(() => {
  const s = p.addSlide(); bg(s);
  eyebrow(s, "Innovation · real-time re-planning", 0.9, 0.6);
  s.addText("Adaptive A* / D* Lite: replan for free", { x: 0.85, y: 0.95, w: 11.8, h: 0.8, isTextBox: true, margin: 0, fontFace: HF, fontSize: 34, bold: true, color: TEXT });

  // chart: operator-facing latency over a 10-tick mission
  card(s, 0.9, 2.0, 6.5, 4.9);
  s.addText("Operator-facing replan latency (10-tick mission)", { x: 1.15, y: 2.2, w: 6, h: 0.4, isTextBox: true, margin: 0, fontFace: HF, fontSize: 14, bold: true, color: TEXT });
  s.addChart(p.ChartType.bar, [
    { name: "Total latency (ms)", labels: ["A* every tick", "Adaptive (ours)"], values: [1420, 130] },
  ], { x: 1.0, y: 2.7, w: 6.3, h: 4.0, barDir: "col", chartColors: [ACC],
       showValue: true, dataLabelPosition: "outEnd", dataLabelColor: TEXT, dataLabelFontFace: HF, dataLabelFontSize: 13, dataLabelFormatCode: '#,##0" ms"',
       showLegend: false, showTitle: false,
       catAxisLabelColor: MUTED, catAxisLabelFontFace: BF, catAxisLabelFontSize: 12,
       valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
       valAxisMaxVal: 1650, chartColorsOpacity: [100] });

  // right column: how + numbers
  const items = [
    ["Gradual drift (weather)", "D* Lite repairs only affected cells", "~0 ms", GREEN],
    ["Major event (SAM pop-up)", "Full A* replan, D* Lite re-warms", "~130 ms", AMBER],
  ];
  items.forEach((it, i) => {
    const y = 2.0 + i * 1.35;
    card(s, 7.7, y, 4.7, 1.2, PANEL);
    dot(s, 7.98, y + 0.28, it[3]);
    s.addText(it[0], { x: 8.25, y: y + 0.18, w: 3.0, h: 0.4, isTextBox: true, margin: 0, fontFace: HF, fontSize: 14, bold: true, color: TEXT });
    s.addText(it[1], { x: 8.25, y: y + 0.6, w: 3.1, h: 0.5, isTextBox: true, margin: 0, fontFace: BF, fontSize: 12, color: MUTED });
    s.addText(it[2], { x: 11.2, y: y + 0.3, w: 1.1, h: 0.6, isTextBox: true, margin: 0, align: "right", fontFace: HF, fontSize: 18, bold: true, color: it[3] });
  });
  card(s, 7.7, 4.75, 4.7, 2.15, PANEL2);
  s.addText("Correctness, not just speed", { x: 7.98, y: 4.95, w: 4.2, h: 0.4, isTextBox: true, margin: 0, fontFace: HF, fontSize: 14, bold: true, color: ACC });
  s.addText([
    { text: "D* Lite is proven to return the ", options: { color: TEXT } },
    { text: "identical optimal cost as A*", options: { color: GREEN, bold: true } },
    { text: " (unit-tested). The planner adaptively picks the cheaper strategy each tick — honest engineering, not a one-size claim.", options: { color: TEXT } },
  ], { x: 7.98, y: 5.4, w: 4.2, h: 1.4, isTextBox: true, margin: 0, fontFace: BF, fontSize: 14 });
  s.addNotes("A* every tick = 1420ms total; adaptive = 130ms → 10.9x. Continuous drift ticks are ~0ms via D* Lite incremental repair.");
})();

// ============ SLIDE 5 — ML FORECASTING ============
(() => {
  const s = p.addSlide(); bg(s);
  eyebrow(s, "Prediction accuracy", 0.9, 0.6);
  s.addText("Two trained models, beaten baselines", { x: 0.85, y: 0.95, w: 11.8, h: 0.8, isTextBox: true, margin: 0, fontFace: HF, fontSize: 34, bold: true, color: TEXT });

  // left: weather nowcast stat
  card(s, 0.9, 2.0, 5.55, 4.9);
  s.addText("Weather nowcaster — PyTorch CNN", { x: 1.2, y: 2.2, w: 5, h: 0.4, isTextBox: true, margin: 0, fontFace: HF, fontSize: 15, bold: true, color: TEXT });
  s.addText("Predicts the weather field 6 minutes ahead; learns the front's advection.", { x: 1.2, y: 2.6, w: 5, h: 0.6, isTextBox: true, margin: 0, fontFace: BF, fontSize: 13, color: MUTED });
  s.addText("39.4%", { x: 1.2, y: 3.35, w: 5, h: 1.1, isTextBox: true, margin: 0, fontFace: HF, fontSize: 66, bold: true, color: GREEN });
  s.addText("lower RMSE than persistence", { x: 1.2, y: 4.45, w: 5, h: 0.4, isTextBox: true, margin: 0, fontFace: BF, fontSize: 15, color: TEXT });
  s.addShape(p.ShapeType.line, { x: 1.2, y: 5.05, w: 5, h: 0, line: { color: LINE, width: 1 } });
  [["RMSE (model)", "0.029"], ["RMSE (persistence)", "0.049"], ["Trains on CPU in", "~15 s"]].forEach((r, i) => {
    const y = 5.2 + i * 0.5;
    s.addText(r[0], { x: 1.2, y, w: 3.6, h: 0.4, isTextBox: true, margin: 0, fontFace: BF, fontSize: 13, color: MUTED });
    s.addText(r[1], { x: 4.8, y, w: 1.4, h: 0.4, isTextBox: true, margin: 0, align: "right", fontFace: HF, fontSize: 13, bold: true, color: TEXT });
  });

  // right: AD activity chart by horizon
  card(s, 6.7, 2.0, 5.7, 4.9);
  s.addText("Air-defense activity — sklearn GBM", { x: 7.0, y: 2.2, w: 5.2, h: 0.4, isTextBox: true, margin: 0, fontFace: HF, fontSize: 15, bold: true, color: TEXT });
  s.addText("Forecasts which SAM emits next; gain over persistence grows with horizon.", { x: 7.0, y: 2.6, w: 5.2, h: 0.6, isTextBox: true, margin: 0, fontFace: BF, fontSize: 13, color: MUTED });
  s.addChart(p.ChartType.bar, [
    { name: "Model", labels: ["t+2 min", "t+4 min", "t+6 min"], values: [79, 72, 73] },
    { name: "Persistence", labels: ["t+2 min", "t+4 min", "t+6 min"], values: [78, 63, 50] },
  ], { x: 6.85, y: 3.2, w: 5.4, h: 3.5, barDir: "col", chartColors: [ACC, "3A4A6B"],
       showValue: true, dataLabelPosition: "outEnd", dataLabelColor: TEXT, dataLabelFontFace: BF, dataLabelFontSize: 10, dataLabelFormatCode: '0"%"',
       showLegend: true, legendPos: "t", legendColor: MUTED, legendFontFace: BF, legendFontSize: 11, showTitle: false,
       catAxisLabelColor: MUTED, catAxisLabelFontFace: BF, catAxisLabelFontSize: 11,
       valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, valAxisMaxVal: 100, barGapWidthPct: 60 });
  s.addText("+22 pts accuracy · AUC 0.79 at 6-minute horizon", { x: 7.0, y: 6.5, w: 5.2, h: 0.35, isTextBox: true, margin: 0, fontFace: BF, fontSize: 12, italic: true, color: AMBER });
})();

// ============ SLIDE 6 — RISK-AWARE ROUTING (schematic) ============
(() => {
  const s = p.addSlide(); bg(s);
  eyebrow(s, "Route efficiency", 0.9, 0.6);
  s.addText("Risk-aware routing around live threats", { x: 0.85, y: 0.95, w: 11.8, h: 0.8, isTextBox: true, margin: 0, fontFace: HF, fontSize: 34, bold: true, color: TEXT });

  // schematic "map"
  const mx = 0.9, my = 2.0, mw = 7.0, mh = 4.9;
  s.addShape(p.ShapeType.roundRect, { x: mx, y: my, w: mw, h: mh, fill: { color: "0E1A30" }, line: { color: LINE, width: 1 }, rectRadius: 0.09 });
  s.addText("THEATRE · ASTANA REGION, KAZAKHSTAN", { x: mx + 0.2, y: my + 0.14, w: 6.5, h: 0.3, isTextBox: true, margin: 0, fontFace: HF, fontSize: 10, bold: true, color: MUTED, charSpacing: 2 });
  // threat rings
  s.addShape(p.ShapeType.ellipse, { x: mx + 3.0, y: my + 1.3, w: 2.6, h: 2.6, fill: { color: RED, transparency: 82 }, line: { color: RED, width: 1.5 } });
  s.addShape(p.ShapeType.ellipse, { x: mx + 1.0, y: my + 3.3, w: 1.4, h: 1.4, fill: { color: RED, transparency: 82 }, line: { color: RED, width: 1.5 } });
  s.addText("SAM (active)", { x: mx + 3.9, y: my + 2.45, w: 1.6, h: 0.3, isTextBox: true, margin: 0, align: "center", fontFace: BF, fontSize: 10, color: RED });
  // route: start (bottom-left) detouring around big ring to goal (top-right)
  const pts = [[mx + 0.7, my + 4.3], [mx + 1.0, my + 2.6], [mx + 2.3, my + 1.0], [mx + 4.6, my + 0.6], [mx + 6.3, my + 0.7]];
  for (let i = 1; i < pts.length; i++)
    s.addShape(p.ShapeType.line, { x: Math.min(pts[i-1][0], pts[i][0]), y: Math.min(pts[i-1][1], pts[i][1]),
      w: Math.abs(pts[i][0]-pts[i-1][0]), h: Math.abs(pts[i][1]-pts[i-1][1]),
      line: { color: GREEN, width: 3, beginArrowType: "none", endArrowType: i === pts.length-1 ? "triangle" : "none" },
      flipH: (pts[i][0]-pts[i-1][0])*(pts[i][1]-pts[i-1][1]) < 0 });
  s.addShape(p.ShapeType.ellipse, { x: pts[0][0]-0.11, y: pts[0][1]-0.11, w: 0.22, h: 0.22, fill: { color: GREEN } });
  s.addText("Start", { x: pts[0][0]-0.2, y: pts[0][1]+0.12, w: 0.9, h: 0.25, isTextBox: true, margin: 0, fontFace: BF, fontSize: 10, color: TEXT });
  s.addShape(p.ShapeType.ellipse, { x: pts[4][0]-0.11, y: pts[4][1]-0.11, w: 0.22, h: 0.22, fill: { color: ACC } });
  s.addText("Objective", { x: pts[4][0]-0.75, y: pts[4][1]-0.4, w: 1.1, h: 0.25, isTextBox: true, margin: 0, fontFace: BF, fontSize: 10, color: TEXT });

  // right: metrics + sliders concept
  s.addText("The operator sets priorities; the optimizer returns three routes:", { x: 8.2, y: 2.0, w: 4.2, h: 0.7, isTextBox: true, margin: 0, fontFace: BF, fontSize: 14, color: MUTED });
  const routes = [["Optimal", "operator weights", ACC], ["Safest", "safety-heavy", GREEN], ["Fastest", "time-heavy", AMBER]];
  routes.forEach((r, i) => {
    const y = 2.9 + i * 0.62;
    s.addShape(p.ShapeType.line, { x: 8.2, y: y + 0.16, w: 0.5, h: 0, line: { color: r[2], width: 3, dashType: i === 0 ? "solid" : "dash" } });
    s.addText(r[0], { x: 8.8, y, w: 1.6, h: 0.35, isTextBox: true, margin: 0, fontFace: HF, fontSize: 14, bold: true, color: TEXT });
    s.addText(r[1], { x: 10.2, y, w: 2.2, h: 0.35, isTextBox: true, margin: 0, fontFace: BF, fontSize: 12, color: MUTED });
  });
  card(s, 8.2, 5.0, 4.2, 1.9, PANEL2);
  s.addText("Recommended route", { x: 8.45, y: 5.15, w: 3.8, h: 0.35, isTextBox: true, margin: 0, fontFace: HF, fontSize: 13, bold: true, color: ACC });
  [["Max detection risk", "7%", GREEN], ["Flight time", "70 min", TEXT], ["Segment risk", "color-coded", TEXT]].forEach((r, i) => {
    const y = 5.55 + i * 0.42;
    s.addText(r[0], { x: 8.45, y, w: 2.7, h: 0.35, isTextBox: true, margin: 0, fontFace: BF, fontSize: 13, color: MUTED });
    s.addText(r[1], { x: 11.0, y, w: 1.2, h: 0.35, isTextBox: true, margin: 0, align: "right", fontFace: HF, fontSize: 13, bold: true, color: r[2] });
  });
  s.addText("Constraints enforced: flight time · fuel · altitude band (100–3000 m; altitude scales radar exposure)", { x: 0.9, y: 7.0, w: 11.5, h: 0.35, isTextBox: true, margin: 0, fontFace: BF, fontSize: 11, italic: true, color: MUTED });
})();

// ============ SLIDE 7 — ARCHITECTURE & SECURITY ============
(() => {
  const s = p.addSlide(); bg(s);
  eyebrow(s, "Under the hood", 0.9, 0.6);
  s.addText("Architecture, stack & security", { x: 0.85, y: 0.95, w: 11.8, h: 0.8, isTextBox: true, margin: 0, fontFace: HF, fontSize: 34, bold: true, color: TEXT });

  const cols = [
    ["Backend", ["FastAPI REST + WebSocket", "NumPy vectorized cost field", "Per-session live missions", "Stateless, shardable"], ACC],
    ["Intelligence", ["PyTorch CNN nowcaster", "scikit-learn GBM classifier", "A* + D* Lite optimizer", "Multi-objective weighting"], GREEN],
    ["Frontend", ["Leaflet operator dashboard", "Danger heatmap + threat rings", "Priority sliders, live clock", "Zero-build, one command"], AMBER],
  ];
  cols.forEach((c, i) => {
    const x = 0.9 + i * 3.9;
    card(s, x, 2.0, 3.6, 3.1);
    s.addShape(p.ShapeType.roundRect, { x: x + 0.3, y: 2.25, w: 1.5, h: 0.5, fill: { color: c[2] }, rectRadius: 0.08 });
    s.addText(c[0], { x: x + 0.3, y: 2.25, w: 1.5, h: 0.5, isTextBox: true, margin: 0, align: "center", valign: "middle", fontFace: HF, fontSize: 14, bold: true, color: "0B1220" });
    c[1].forEach((li, j) => {
      const y = 3.0 + j * 0.5;
      dot(s, x + 0.32, y + 0.06, c[2], 0.1);
      s.addText(li, { x: x + 0.55, y, w: 2.9, h: 0.45, isTextBox: true, margin: 0, fontFace: BF, fontSize: 12.5, color: TEXT });
    });
  });
  // security band
  card(s, 0.9, 5.35, 11.5, 1.5, PANEL2);
  s.addText("Security (brief §7)", { x: 1.2, y: 5.55, w: 4, h: 0.35, isTextBox: true, margin: 0, fontFace: HF, fontSize: 14, bold: true, color: RED });
  const sec = [["JWT auth", "hashed operator credential (PBKDF2)"], ["AES / Fernet", "encryption of stored scenarios"], ["Env-var secrets", "no plaintext keys in code"]];
  sec.forEach((r, i) => {
    const x = 1.2 + i * 3.75;
    s.addText(r[0], { x, y: 5.95, w: 3.6, h: 0.35, isTextBox: true, margin: 0, fontFace: HF, fontSize: 14, bold: true, color: TEXT });
    s.addText(r[1], { x, y: 6.3, w: 3.6, h: 0.45, isTextBox: true, margin: 0, fontFace: BF, fontSize: 12, color: MUTED });
  });
})();

// ============ SLIDE 8 — RESULTS / CLOSE ============
(() => {
  const s = p.addSlide(); bg(s);
  // dark close slide
  eyebrow(s, "Results · mapped to judging criteria", 0.9, 0.7);
  s.addText("A complete, working prototype", { x: 0.85, y: 1.1, w: 11.8, h: 0.9, isTextBox: true, margin: 0, fontFace: HF, fontSize: 40, bold: true, color: TEXT });

  const grid = [
    ["Prediction accuracy", "-39% weather RMSE · +22 pts AD (AUC 0.79)", GREEN],
    ["Route efficiency", "time / fuel / risk per route; detours keep risk ~7%", ACC],
    ["Innovation", "adaptive D* Lite + ML pre-emptive avoidance · 10.9×", AMBER],
    ["User interface", "live command-center dashboard, one command", ACC],
    ["Documentation", "README + architecture doc + 21 passing tests", GREEN],
    ["Scalability", "stateless API · vectorized · O(cells) optimizer", ACC],
  ];
  grid.forEach((g, i) => {
    const x = 0.9 + (i % 2) * 5.85;
    const y = 2.3 + Math.floor(i / 2) * 1.15;
    card(s, x, y, 5.55, 1.0);
    dot(s, x + 0.28, y + 0.42, g[2]);
    s.addText(g[0], { x: x + 0.55, y: y + 0.13, w: 4.9, h: 0.4, isTextBox: true, margin: 0, fontFace: HF, fontSize: 15, bold: true, color: TEXT });
    s.addText(g[1], { x: x + 0.55, y: y + 0.52, w: 4.9, h: 0.4, isTextBox: true, margin: 0, fontFace: BF, fontSize: 12.5, color: MUTED });
  });
  s.addText([
    { text: "Simulated feeds → trained forecasts → risk field → adaptive optimizer → operator dashboard.", options: { color: TEXT } },
  ], { x: 0.9, y: 6.35, w: 11.5, h: 0.5, isTextBox: true, margin: 0, align: "center", fontFace: BF, fontSize: 15, italic: true, color: ACC });
  s.addText("python -m uvicorn backend.api.main:app  →  http://localhost:8017", { x: 0.9, y: 6.85, w: 11.5, h: 0.4, isTextBox: true, margin: 0, align: "center", fontFace: "Courier New", fontSize: 13, color: MUTED });
})();

p.writeFile({ fileName: "C:/Users/Asus/Desktop/defenceTech/Eighth_01_project/docs/UAV_DSS_Deck.pptx" }).then(f => console.log("WROTE", f));
