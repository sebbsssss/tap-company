/* ============================================================
   TAP — App shell + navigation + tweaks
   ============================================================ */

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "layout": "balanced",
  "density": "regular",
  "accent": "#0E0E0C",
  "showInsightsBanner": true
}/*EDITMODE-END*/;

const ACCENT_INK = {
  "#0E0E0C": "#0E0E0C",   // graphite (default)
  "#3D49A6": "#1B1F38",   // indigo
  "#1F5A45": "#0F2820",   // forest
  "#7A2D2A": "#2A0F0E",   // burgundy
};

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // -------- User identity & role (persisted) --------
  const [role, setRoleState] = useState(() => localStorage.getItem("tap.role") || "admin");
  const [firstName] = useState(() => localStorage.getItem("tap.firstName") || "Sebastien");
  const [lastName]  = useState(() => localStorage.getItem("tap.lastName")  || "");
  function setRole(r) {
    setRoleState(r);
    localStorage.setItem("tap.role", r);
  }

  // Apply accent
  useEffect(() => {
    const root = document.documentElement;
    const ink1 = ACCENT_INK[t.accent] || t.accent;
    root.style.setProperty("--accent", t.accent);
    root.style.setProperty("--ink-1", ink1);
    return () => {
      root.style.removeProperty("--accent");
      root.style.removeProperty("--ink-1");
    };
  }, [t.accent]);

  // Persisted target config
  const [targetOcc, setTargetOcc] = useState(() => {
    const stored = localStorage.getItem("tap.target");
    return stored ? +stored : 0.90;
  });
  const [perPropertyTargets, setPerPropertyTargets] = useState(() => {
    try { return JSON.parse(localStorage.getItem("tap.targets") || "{}"); }
    catch (e) { return {}; }
  });
  useEffect(() => { localStorage.setItem("tap.target", String(targetOcc)); }, [targetOcc]);
  useEffect(() => { localStorage.setItem("tap.targets", JSON.stringify(perPropertyTargets)); }, [perPropertyTargets]);

  function setPerPropertyTarget(id, value) {
    setPerPropertyTargets(m => ({ ...m, [id]: value }));
  }

  // Apply per-property target overrides to PROPERTY_STATS
  const D = window.TAP_DATA;
  const statsWithTargets = useMemo(() => {
    return D.PROPERTY_STATS.map(s => ({
      ...s,
      property: { ...s.property, target: perPropertyTargets[s.property.id] != null ? perPropertyTargets[s.property.id] : s.property.target }
    }));
  }, [perPropertyTargets]);

  // Nav route
  const [route, setRoute] = useState(() => location.hash.replace("#", "") || "overview");
  useEffect(() => {
    function onHash() { setRoute(location.hash.replace("#", "") || "overview"); }
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  function go(r) { location.hash = "#" + r; }

  // Gate admin route — redirect non-admins away
  useEffect(() => {
    if (route === "admin" && role !== "admin") go("overview");
  }, [route, role]);

  // View mode (Finance / Operations)
  const [viewMode, setViewMode] = useState(() => localStorage.getItem("tap.view") || "operations");
  useEffect(() => { localStorage.setItem("tap.view", viewMode); }, [viewMode]);

  // Filters
  const FILTER_DEFAULTS = { month: D.MONTH_START.toISOString().slice(0, 7), property: "All", ptype: "All", region: "All", status: "all" };
  const [filters, setFilters] = useState(FILTER_DEFAULTS);
  function setFilter(k, v) { setFilters(f => ({ ...f, [k]: v })); }
  function resetFilters() { setFilters(FILTER_DEFAULTS); }

  // Apply filters to property stats
  const filteredStats = useMemo(() => {
    return statsWithTargets.filter(s => {
      if (filters.property !== "All" && s.property.id !== filters.property) return false;
      if (filters.ptype !== "All" && s.property.type !== filters.ptype) return false;
      if (filters.region !== "All" && s.property.region !== filters.region) return false;
      if (filters.status !== "all") {
        const hasStatus = (
          (filters.status === "occupied"    && s.occupied    > 0) ||
          (filters.status === "vacant"      && s.vacant      > 0) ||
          (filters.status === "reserved"    && s.reserved    > 0) ||
          (filters.status === "maintenance" && s.maintenance > 0)
        );
        if (!hasStatus) return false;
      }
      return true;
    });
  }, [statsWithTargets, filters]);

  // Portfolio recalculated from filteredStats
  const filteredPortfolio = useMemo(() => {
    const totalUnits = filteredStats.reduce((a, s) => a + s.units, 0) || 1;
    const occupied = filteredStats.reduce((a, s) => a + s.occupied, 0);
    const vacant   = filteredStats.reduce((a, s) => a + s.vacant, 0);
    const reserved = filteredStats.reduce((a, s) => a + s.reserved, 0);
    const maintenance = filteredStats.reduce((a, s) => a + s.maintenance, 0);
    const moveIns  = filteredStats.reduce((a, s) => a + s.moveIns, 0);
    const moveOuts = filteredStats.reduce((a, s) => a + s.moveOuts, 0);
    const financeOccCount = filteredStats.reduce((a, s) => a + s.financeOccCount, 0);
    const financeRate = financeOccCount / totalUnits;
    const dailyAgg = Array.from({ length: D.DAYS_IN_MONTH }, (_, d) => {
      let occ = 0, tot = 0;
      filteredStats.forEach(s => { occ += s.daily[d].occ; tot += s.daily[d].total; });
      return { day: d + 1, occ, total: tot || 1, rate: tot ? occ / tot : 0 };
    });
    const opsRate = dailyAgg.reduce((a, d) => a + d.rate, 0) / D.DAYS_IN_MONTH;
    const prevAvg = filteredStats.reduce((a, s) => a + s.opsRatePrev * s.units, 0) / totalUnits;
    const sortedDays = [...dailyAgg].sort((a, b) => b.rate - a.rate);
    return {
      totalUnits, occupied, vacant, reserved, maintenance, moveIns, moveOuts,
      financeOccCount, financeRate, opsRate, opsRatePrev: prevAvg,
      delta: opsRate - prevAvg,
      dailyAgg,
      highest: sortedDays[0] || { day: 1, rate: 0 },
      lowest:  sortedDays[sortedDays.length - 1] || { day: 1, rate: 0 },
      todayRate: (dailyAgg[Math.min(D.TODAY_DAY - 1, dailyAgg.length - 1)] || { rate: 0 }).rate,
      belowTarget: filteredStats.filter(s => s.opsRate < s.property.target).length,
    };
  }, [filteredStats]);

  // Recompute insights against filteredStats
  const filteredInsights = useMemo(() => {
    const insights = [];
    const propIds = new Set(filteredStats.map(s => s.property.id));
    const units = D.UNITS.filter(u => propIds.has(u.propertyId));

    const below = filteredStats.filter(s => s.opsRate < s.property.target);
    if (below.length) insights.push({
      severity: below.some(s => (s.property.target - s.opsRate) > 0.10) ? "bad" : "warn",
      title: `${below.length} ${below.length === 1 ? "property" : "properties"} below target`,
      detail: below.slice(0, 3).map(s => `${s.property.name} ${(s.opsRate * 100).toFixed(0)}%`).join(" · "),
      count: below.length,
    });

    const vac14 = units.filter(u => (u.status === "vacant" || u.status === "maintenance") && u.daysVacant > 14 && u.daysVacant <= 30);
    if (vac14.length) insights.push({ severity: "warn", title: `${vac14.length} units vacant 14+ days`, detail: "Refresh listings — rent, photos, channel mix.", count: vac14.length });
    const vac30 = units.filter(u => (u.status === "vacant" || u.status === "maintenance") && u.daysVacant > 30);
    if (vac30.length) insights.push({ severity: "bad", title: `${vac30.length} units vacant 30+ days`, detail: "Sustained vacancy — escalate to GM.", count: vac30.length });
    const moveouts = units.filter(u => u.upcomingMoveOut);
    if (moveouts.length) insights.push({ severity: "info", title: `${moveouts.length} move-outs in next 30 days`, detail: "Open re-letting workflow now.", count: moveouts.length });
    const declining = filteredStats.filter(s => s.delta < -0.02);
    if (declining.length) insights.push({
      severity: "warn",
      title: `${declining.length} ${declining.length === 1 ? "property has" : "properties have"} declining occupancy`,
      detail: declining.slice(0, 3).map(s => `${s.property.name} ${(s.delta * 100).toFixed(1)}pp`).join(" · "),
      count: declining.length,
    });
    return insights;
  }, [filteredStats]);

  const filteredDQ = useMemo(() => {
    const propIds = new Set(filteredStats.map(s => s.property.id));
    const units = D.UNITS.filter(u => propIds.has(u.propertyId));
    const issues = [];
    const missMI = units.filter(u => u.dqFlags.includes("missing-movein"));
    if (missMI.length) issues.push({ severity: "warn", title: `${missMI.length} units missing move-in date`, count: missMI.length });
    const inverted = units.filter(u => u.dqFlags.includes("inverted-lease"));
    if (inverted.length) issues.push({ severity: "bad", title: `${inverted.length} units lease-end < lease-start`, count: inverted.length });
    const occNoT = units.filter(u => u.dqFlags.includes("occupied-no-tenant"));
    if (occNoT.length) issues.push({ severity: "bad", title: `${occNoT.length} occupied units with no tenant attached`, count: occNoT.length });
    const vacWL = units.filter(u => u.dqFlags.includes("vacant-with-lease"));
    if (vacWL.length) issues.push({ severity: "warn", title: `${vacWL.length} units vacant but lease active`, count: vacWL.length });
    return issues;
  }, [filteredStats]);

  // Drilldown
  const [drilldownId, setDrilldownId] = useState(null);
  function openProperty(id) { setDrilldownId(id); }
  function closeDrilldown() { setDrilldownId(null); }

  // Toast
  const [showToast, toastEl] = useToast();

  // Pending admin request count (for sidebar badge)
  const pendingCount = useMemo(() => {
    try {
      const dynamic = JSON.parse(localStorage.getItem("tap.joinRequests") || "[]");
      const decisions = JSON.parse(localStorage.getItem("tap.requestDecisions") || "{}");
      const seedPending = 4; // 4 of the 6 seed requests start pending
      const allDynamic = dynamic.filter(r => !decisions[r.id] || decisions[r.id].status === "pending").length;
      return seedPending + allDynamic;
    } catch (e) { return 0; }
  }, [route]);

  // Page padding density
  const mainCls = "main" + (t.density === "compact" ? " main--dense" : (t.density === "comfy" ? " main--spacious" : ""));

  return (
    <div className="app">
      <Sidebar
        route={route}
        go={go}
        insightsCount={filteredInsights.length}
        dqCount={filteredDQ.length}
        role={role}
        setRole={setRole}
        firstName={firstName}
        lastName={lastName}
        pendingCount={pendingCount}
      />
      <div className={mainCls}>
        {route === "overview" && (
          <OverviewScreen
            viewMode={viewMode}
            setViewMode={setViewMode}
            filters={filters}
            setFilter={setFilter}
            resetFilters={resetFilters}
            filteredStats={filteredStats}
            portfolio={filteredPortfolio}
            insights={filteredInsights}
            dataQuality={filteredDQ}
            layout={t.layout}
            onOpenProperty={openProperty}
            targetOcc={targetOcc}
          />
        )}
        {route === "properties" && (
          <PropertiesScreen
            filteredStats={filteredStats}
            viewMode={viewMode}
            setViewMode={setViewMode}
            filters={filters}
            setFilter={setFilter}
            resetFilters={resetFilters}
            onOpenProperty={openProperty}
            targetOcc={targetOcc}
            portfolio={filteredPortfolio}
          />
        )}
        {route === "insights" && (
          <InsightsScreen insights={filteredInsights} dataQuality={filteredDQ} />
        )}
        {route === "settings" && (
          <SettingsScreen
            targetOcc={targetOcc}
            setTargetOcc={setTargetOcc}
            perPropertyTargets={perPropertyTargets}
            setPerPropertyTarget={setPerPropertyTarget}
            showToast={showToast}
          />
        )}
        {route === "admin" && role === "admin" && (
          <AdminScreen showToast={showToast} />
        )}
      </div>

      {/* Drilldown slide-over */}
      <div className={`scrim${drilldownId ? " is-open" : ""}`} onClick={closeDrilldown} />
      {drilldownId && (
        <PropertyDrilldown
          propertyId={drilldownId}
          onClose={closeDrilldown}
          viewMode={viewMode}
        />
      )}

      {toastEl}

      <TweaksPanel>
        <TweakSection label="Layout" />
        <TweakRadio
          label="Variation"
          value={t.layout}
          options={[
            { value: "balanced", label: "Balanced" },
            { value: "stacked",  label: "Stacked" },
            { value: "dense",    label: "Dense" },
          ]}
          onChange={v => setTweak("layout", v)}
        />
        <TweakRadio
          label="Density"
          value={t.density}
          options={["compact", "regular", "comfy"]}
          onChange={v => setTweak("density", v)}
        />
        <TweakSection label="Theme" />
        <TweakColor
          label="Accent"
          value={t.accent}
          options={["#0E0E0C", "#3D49A6", "#1F5A45", "#7A2D2A"]}
          onChange={v => setTweak("accent", v)}
        />
      </TweaksPanel>
    </div>
  );
}

// ---------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------
const ROLE_LABEL = { ops: "Operations", finance: "Finance", gm: "General Manager", admin: "Admin" };

function Sidebar({ route, go, insightsCount, dqCount, role, setRole, firstName, lastName, pendingCount }) {
  const items = [
    { id: "overview",   label: "Overview",   icon: "◉" },
    { id: "properties", label: "Properties", icon: "▤" },
    { id: "insights",   label: "Insights",   icon: "◇", count: insightsCount + dqCount },
    { id: "settings",   label: "Settings",   icon: "⚙" },
  ];
  if (role === "admin") {
    items.splice(3, 0, { id: "admin", label: "Admin", icon: "◈", count: pendingCount });
  }
  const initials = (firstName?.[0] || "?") + (lastName?.[0] || "");

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <span className="brand-wm">TAP</span>
        <span className="brand-badge">Occupancy</span>
      </div>
      <div style={{ padding: "0 20px 18px", marginTop: -16,
                    fontFamily: "var(--font-mono)", fontSize: 9.5,
                    letterSpacing: "0.18em", textTransform: "uppercase",
                    color: "var(--ink-4)" }}>
        The Assembly Place
      </div>

      <div className="sidebar__section">Co-Living</div>
      <nav className="sidebar__nav">
        {items.map(it => (
          <button key={it.id}
                  className={`navitem${route === it.id ? " is-active" : ""}`}
                  onClick={() => go(it.id)}>
            <span className="navitem__icon">{it.icon}</span>
            <span>{it.label}</span>
            {it.count > 0 && <span className="navitem__count">{it.count}</span>}
          </button>
        ))}
      </nav>

      <div className="sidebar__foot">
        {/* User identity */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, paddingBottom: 10,
                      borderBottom: "1px solid var(--line)" }}>
          <div style={{
            width: 28, height: 28, borderRadius: "50%",
            background: role === "admin" ? "var(--ink-1)" : "var(--bg-2)",
            color:      role === "admin" ? "var(--bg-0)" : "var(--ink-2)",
            display: "grid", placeItems: "center",
            fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 700,
            flexShrink: 0,
          }}>{initials}</div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ color: "var(--ink-1)", fontSize: 11, fontWeight: 600,
                          fontFamily: "var(--font-sans)", letterSpacing: 0,
                          textTransform: "none", whiteSpace: "nowrap",
                          overflow: "hidden", textOverflow: "ellipsis" }}>
              {firstName} {lastName}
            </div>
            <div style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--ink-4)" }}>
              {ROLE_LABEL[role] || role}
            </div>
          </div>
        </div>

        {/* Demo role switcher */}
        <div style={{ paddingTop: 6 }}>
          <div style={{ fontSize: 9, letterSpacing: "0.18em", color: "var(--ink-4)",
                        marginBottom: 6, fontWeight: 700 }}>
            View as (demo)
          </div>
          <select
            className="select"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            style={{ width: "100%", fontSize: 10, padding: "5px 22px 5px 8px", minHeight: 26 }}>
            <option value="admin">Admin</option>
            <option value="gm">General Manager</option>
            <option value="finance">Finance</option>
            <option value="ops">Operations</option>
          </select>
        </div>

        <div style={{ paddingTop: 10, borderTop: "1px solid var(--line)", marginTop: 8 }}>
          <div><strong>Source</strong> · Zoho CRM</div>
          <div>Synced 2 min ago</div>
        </div>

        <a href="login.html" style={{
          marginTop: 8, padding: "6px 0", color: "var(--ink-3)",
          textDecoration: "none", letterSpacing: "0.14em",
          textTransform: "uppercase", fontWeight: 600, fontSize: 9.5,
        }}>
          Sign out ↗
        </a>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------
// Mount (async — waits for TAP_DATA_READY promise set by data.js)
// ---------------------------------------------------------------------
(window.TAP_DATA_READY || Promise.resolve()).then(() => {
  const loadingEl = document.getElementById("tap-loading");
  if (loadingEl) loadingEl.style.display = "none";
  const root = ReactDOM.createRoot(document.getElementById("root"));
  root.render(<App />);
}).catch(err => {
  const loadingEl = document.getElementById("tap-loading");
  if (loadingEl) loadingEl.innerHTML = `
    <div style="font-family:var(--font-mono,monospace);font-size:12px;color:var(--danger,#B83A2B);
                padding:32px;text-align:center;max-width:480px;">
      <div style="font-weight:700;margin-bottom:8px;">Failed to load dashboard</div>
      <div style="color:var(--ink-3,#5C5C56);margin-bottom:16px;">${err.message}</div>
      <button onclick="location.reload()"
              style="padding:8px 16px;background:#0E0E0C;color:#FBFAF6;border:0;border-radius:4px;
                     font-family:inherit;font-size:11px;letter-spacing:0.1em;text-transform:uppercase;cursor:pointer;">
        Retry
      </button>
    </div>`;
});
