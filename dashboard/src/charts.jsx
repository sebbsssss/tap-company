/* ============================================================
   TAP — Recharts wrappers
   Uses Recharts via CDN: window.Recharts
   ============================================================ */

const R = window.Recharts;

// Color helpers (read from CSS vars for tone consistency)
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// -------- Daily occupancy trend (line) -------------------------------
function DailyTrendChart({ daily, todayDay, viewMode, target }) {
  const data = daily.map(d => ({
    day: d.day,
    rate: +(d.rate * 100).toFixed(1),
    occ: d.occ,
    total: d.total,
    isFuture: d.day > todayDay,
  }));
  const ink = "#0E0E0C";
  const ink3 = "#5C5C56";
  const occColor = "#2F7D5B";
  return (
    <R.ResponsiveContainer width="100%" height={260}>
      <R.LineChart data={data} margin={{ top: 12, right: 20, left: 0, bottom: 8 }}>
        <R.CartesianGrid stroke="rgba(20,18,12,0.07)" vertical={false} />
        <R.XAxis
          dataKey="day"
          tick={{ fill: ink3, fontSize: 10, fontFamily: "Inconsolata" }}
          tickLine={false}
          axisLine={{ stroke: "rgba(20,18,12,0.14)" }}
          interval={2}
          tickFormatter={d => "May " + d}
        />
        <R.YAxis
          tick={{ fill: ink3, fontSize: 10, fontFamily: "Inconsolata" }}
          tickLine={false}
          axisLine={false}
          domain={[0, 100]}
          tickFormatter={v => v + "%"}
          width={40}
        />
        <R.Tooltip
          formatter={(v, _n, p) => [`${v}%  (${p.payload.occ}/${p.payload.total})`, viewMode === "finance" ? "Occupied" : "Daily rate"]}
          labelFormatter={d => "May " + d + ", 2026"}
          cursor={{ stroke: "rgba(20,18,12,0.22)", strokeDasharray: "2 3" }}
        />
        {target != null && (
          <R.ReferenceLine y={target * 100} stroke="rgba(20,18,12,0.45)" strokeDasharray="3 3"
                           label={{ value: `Target ${(target * 100).toFixed(0)}%`, position: "insideTopRight", fill: ink3, fontSize: 10, fontFamily: "Inconsolata" }} />
        )}
        <R.ReferenceLine x={todayDay} stroke="rgba(20,18,12,0.30)" strokeDasharray="2 4"
                         label={{ value: "TODAY", position: "top", fill: ink, fontSize: 9, fontFamily: "Inconsolata", letterSpacing: 2 }} />
        <R.Line
          type="monotone"
          dataKey="rate"
          stroke={ink}
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 4, fill: ink, stroke: "#fff", strokeWidth: 1.5 }}
        />
      </R.LineChart>
    </R.ResponsiveContainer>
  );
}

// -------- Bar chart — occupancy by property -------------------------
function PropertyBarChart({ stats, viewMode, onPick }) {
  const data = stats.map(s => ({
    name: s.property.name,
    short: s.property.name.split(" ").slice(0, 2).join(" "),
    id: s.property.id,
    finance: +(s.financeRate * 100).toFixed(1),
    ops:     +(s.opsRate     * 100).toFixed(1),
    target:  +(s.property.target * 100).toFixed(0),
  }));
  return (
    <R.ResponsiveContainer width="100%" height={300}>
      <R.BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 30 }}>
        <R.CartesianGrid stroke="rgba(20,18,12,0.07)" vertical={false} />
        <R.XAxis
          dataKey="short"
          tick={{ fill: "#5C5C56", fontSize: 10, fontFamily: "Inconsolata" }}
          tickLine={false}
          axisLine={{ stroke: "rgba(20,18,12,0.14)" }}
          interval={0}
          angle={-18}
          textAnchor="end"
          height={50}
        />
        <R.YAxis
          tick={{ fill: "#5C5C56", fontSize: 10, fontFamily: "Inconsolata" }}
          tickLine={false}
          axisLine={false}
          domain={[0, 100]}
          tickFormatter={v => v + "%"}
          width={36}
        />
        <R.Tooltip
          cursor={{ fill: "rgba(20,18,12,0.04)" }}
          formatter={(v, name) => [v + "%", name === "finance" ? "Finance" : name === "ops" ? "Operations" : "Target"]}
        />
        <R.Legend
          wrapperStyle={{ fontSize: 10 }}
          iconType="square"
          iconSize={8}
          formatter={(v) => v === "finance" ? "Finance %" : "Operations %"}
        />
        <R.Bar dataKey="finance" fill="#0E0E0C" radius={[2, 2, 0, 0]} maxBarSize={18}
               onClick={(_e, idx) => onPick && onPick(data[idx].id)}
               style={{ cursor: "pointer" }} />
        <R.Bar dataKey="ops"     fill="#2F7D5B" radius={[2, 2, 0, 0]} maxBarSize={18}
               onClick={(_e, idx) => onPick && onPick(data[idx].id)}
               style={{ cursor: "pointer" }} />
      </R.BarChart>
    </R.ResponsiveContainer>
  );
}

// -------- Calendar heatmap ------------------------------------------
function heatColor(rate) {
  // Map 0..1 to warm paper → ink with a green tint pass-through
  if (rate == null) return "transparent";
  // Use 4-step ramp on green
  const steps = [
    { t: 0.50, c: "rgba(176,100,30,0.10)" },   // amber low
    { t: 0.70, c: "rgba(176,100,30,0.18)" },
    { t: 0.85, c: "rgba(47,125,91,0.18)" },
    { t: 0.93, c: "rgba(47,125,91,0.32)" },
    { t: 1.01, c: "rgba(47,125,91,0.48)" },
  ];
  for (const s of steps) if (rate < s.t) return s.c;
  return steps[steps.length - 1].c;
}

function CalendarHeatmap({ daily, todayDay }) {
  // Build 6x7 grid. May 1, 2026 = Friday. Pad with empties.
  const FIRST_DOW = new Date(Date.UTC(2026, 4, 1)).getUTCDay(); // 5 (Fri)
  const cells = [];
  for (let i = 0; i < FIRST_DOW; i++) cells.push(null);
  for (let i = 0; i < daily.length; i++) cells.push(daily[i]);
  while (cells.length % 7 !== 0) cells.push(null);

  const dayLabels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  return (
    <div>
      <div className="cal">
        {dayLabels.map(d => <div key={d} className="cal__head">{d}</div>)}
        {cells.map((c, i) => {
          if (!c) return <div key={i} className="cal__cell cal__cell--empty" />;
          const future = c.day > todayDay;
          return (
            <div key={i}
                 className={`cal__cell${c.day === todayDay ? " is-today" : ""}`}
                 style={{ background: future ? "transparent" : heatColor(c.rate), opacity: future ? 0.35 : 1 }}
                 title={`May ${c.day}: ${(c.rate * 100).toFixed(1)}%  (${c.occ}/${c.total})`}>
              <span className="cal__day">{c.day}</span>
              <span className="cal__pct">{future ? "—" : (c.rate * 100).toFixed(0) + "%"}</span>
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 10,
                    fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--ink-4)",
                    letterSpacing: "0.12em", textTransform: "uppercase" }}>
        <span>Low</span>
        {[0.50, 0.70, 0.85, 0.93, 1.0].map((t, i) => (
          <span key={i} style={{ width: 22, height: 12, background: heatColor(t - 0.01),
                                  border: "1px solid var(--line)", borderRadius: 2 }} />
        ))}
        <span>High</span>
      </div>
    </div>
  );
}

// -------- Mini sparkline used in property table rows ----------------
function PropertySpark({ daily, todayDay }) {
  const values = daily.map(d => d.rate);
  return <Sparkline values={values} color="var(--ink-2)" height={22} />;
}

Object.assign(window, { DailyTrendChart, PropertyBarChart, CalendarHeatmap, PropertySpark });
