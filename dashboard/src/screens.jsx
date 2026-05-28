/* ============================================================
   TAP — Screens (Overview, Properties, Insights, Settings)
   ============================================================ */

// ---------------------------------------------------------------------
// Overview — main dashboard
// ---------------------------------------------------------------------
function OverviewScreen({
  viewMode, setViewMode, filters, setFilter, resetFilters,
  filteredStats, portfolio, insights, dataQuality,
  layout, onOpenProperty, targetOcc,
}) {
  const D = window.TAP_DATA;
  const monthYear = fmtMonthYear(D.MONTH_START);
  const isFinance = viewMode === "finance";
  const headlineRate = isFinance ? portfolio.financeRate : portfolio.opsRate;
  const headlineLabel = isFinance ? "Finance %" : "Operations %";
  const headlineHelper = isFinance
    ? `Occupied at any point in ${monthYear}`
    : `Avg of daily occupancy across ${monthYear}`;

  return (
    <>
      <div className="pageheader">
        <div className="pageheader__title">
          <div className="t-eyebrow">Co-living · {monthYear}</div>
          <h1 className="t-h1">Occupancy</h1>
          <p className="t-lede">{headlineHelper}.</p>
        </div>
        <div className="pageheader__actions">
          <span className="t-eyebrow" style={{ marginRight: 6 }}>Updated 2 min ago</span>
          <ExportMenu portfolio={portfolio} filteredStats={filteredStats} />
        </div>
      </div>

      <FilterBar
        filters={filters}
        setFilter={setFilter}
        resetFilters={resetFilters}
        viewMode={viewMode}
        setViewMode={setViewMode}
      />

      <ViewExplainer viewMode={viewMode} />

      <KPISummary portfolio={portfolio} viewMode={viewMode} dense={layout === "dense"} />

      {layout === "balanced" && (
        <BalancedLayout
          filteredStats={filteredStats}
          portfolio={portfolio}
          viewMode={viewMode}
          insights={insights}
          dataQuality={dataQuality}
          onOpenProperty={onOpenProperty}
          targetOcc={targetOcc}
        />
      )}
      {layout === "stacked" && (
        <StackedLayout
          filteredStats={filteredStats}
          portfolio={portfolio}
          viewMode={viewMode}
          insights={insights}
          dataQuality={dataQuality}
          onOpenProperty={onOpenProperty}
          targetOcc={targetOcc}
        />
      )}
      {layout === "dense" && (
        <DenseLayout
          filteredStats={filteredStats}
          portfolio={portfolio}
          viewMode={viewMode}
          insights={insights}
          dataQuality={dataQuality}
          onOpenProperty={onOpenProperty}
          targetOcc={targetOcc}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------
// View explainer — the critical Finance vs Ops difference
// ---------------------------------------------------------------------
function ViewExplainer({ viewMode }) {
  const isFinance = viewMode === "finance";
  return (
    <div style={{
      display: "flex",
      gap: 14,
      padding: "10px 14px",
      border: "1px solid var(--line)",
      background: isFinance ? "rgba(74,91,180,0.05)" : "rgba(47,125,91,0.05)",
      borderRadius: "var(--r-2)",
      marginBottom: 18,
      alignItems: "center",
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      color: "var(--ink-2)",
    }}>
      <span style={{
        background: isFinance ? "var(--res)" : "var(--occ)",
        color: "white",
        padding: "2px 8px",
        borderRadius: 2,
        fontSize: 9,
        letterSpacing: "0.16em",
        textTransform: "uppercase",
        fontWeight: 700,
      }}>
        {isFinance ? "Finance View" : "Operations View"}
      </span>
      <span>
        {isFinance
          ? "A unit counts as occupied if it was let at any point during the month. Use for monthly close."
          : "Each day is counted separately. The headline number is the average daily occupancy. Use for live operations."}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------
// KPI Summary — 8 cards
// ---------------------------------------------------------------------
function KPISummary({ portfolio, viewMode, dense }) {
  const D = window.TAP_DATA;
  const monthAbbr = fmtMonthAbbr(D.MONTH_START);
  const prevMonthAbbr = fmtMonthAbbr(
    D.MONTH_START ? new Date(Date.UTC(D.MONTH_START.getUTCFullYear(), D.MONTH_START.getUTCMonth() - 1, 1)) : null
  );
  const todayLabel = D.TODAY.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const isFinance = viewMode === "finance";
  const headlineRate = isFinance ? portfolio.financeRate : portfolio.opsRate;
  return (
    <div className={`kpigrid${dense ? " kpigrid--dense" : ""}`} style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
      <KPI
        label={isFinance ? "Finance Occupancy" : "Operations Occupancy"}
        value={fmtPct(headlineRate, 1)}
        sub={fmtSigned(portfolio.delta, 1) + " vs " + prevMonthAbbr}
        subTone={portfolio.delta >= 0 ? "good" : "bad"}
        accent
      />
      <KPI label="Total Units"  value={fmtNum(portfolio.totalUnits)} sub="rooms / beds / units" />
      <KPI label="Occupied" value={fmtNum(portfolio.occupied)}
            sub={fmtPct(portfolio.occupied / portfolio.totalUnits, 0) + " of stock"} />
      <KPI label="Vacant" value={fmtNum(portfolio.vacant)}
            sub={`${portfolio.reserved} reserved · ${portfolio.maintenance} mnt`} />
      <KPI label="Today" value={fmtPct(portfolio.todayRate, 1)} sub={"As of " + todayLabel} />
      <KPI label="Highest Day" value={fmtPct(portfolio.highest.rate, 1)} sub={monthAbbr + " " + portfolio.highest.day} subTone="good" />
      <KPI label="Lowest Day"  value={fmtPct(portfolio.lowest.rate, 1)}  sub={monthAbbr + " " + portfolio.lowest.day}  subTone="bad" />
      <KPI label="Below Target" value={fmtNum(portfolio.belowTarget)}
            sub={`${portfolio.moveIns} move-ins · ${portfolio.moveOuts} out`}
            subTone={portfolio.belowTarget > 0 ? "warn" : "good"} />
    </div>
  );
}

// ---------------------------------------------------------------------
// LAYOUT — BALANCED (default)
// ---------------------------------------------------------------------
function BalancedLayout({ filteredStats, portfolio, viewMode, insights, dataQuality, onOpenProperty, targetOcc }) {
  const D = window.TAP_DATA;
  const monthYear = fmtMonthYear(D.MONTH_START);
  return (
    <>
      <div className="row row--main-rail">
        <div className="panel">
          <div className="panel__head">
            <div className="panel__head-title">
              <div className="t-eyebrow">Daily Occupancy Rate · {monthYear}</div>
              <div className="t-h2">{viewMode === "finance" ? "Coverage trend" : "Daily occupancy trend"}</div>
            </div>
            <div className="t-eyebrow">{viewMode === "finance" ? "Cumulative unique occupancy" : "Today " + fmtPct(portfolio.todayRate, 1)}</div>
          </div>
          <div className="panel__body">
            <DailyTrendChart daily={portfolio.dailyAgg} todayDay={D.TODAY_DAY} viewMode={viewMode} target={targetOcc} />
          </div>
        </div>
        <RightRail insights={insights} dataQuality={dataQuality} />
      </div>

      <div className="row row--2eq">
        <div className="panel">
          <div className="panel__head">
            <div className="panel__head-title">
              <div className="t-eyebrow">Occupancy by Property</div>
              <div className="t-h2">Finance vs Operations</div>
            </div>
          </div>
          <div className="panel__body">
            <PropertyBarChart stats={filteredStats} viewMode={viewMode} onPick={onOpenProperty} />
          </div>
        </div>
        <div className="panel">
          <div className="panel__head">
            <div className="panel__head-title">
              <div className="t-eyebrow">Calendar Heatmap · Portfolio</div>
              <div className="t-h2">Daily intensity</div>
            </div>
          </div>
          <div className="panel__body">
            <CalendarHeatmap daily={portfolio.dailyAgg} todayDay={D.TODAY_DAY} />
          </div>
        </div>
      </div>

      <PropertyTable stats={filteredStats} viewMode={viewMode} onOpenProperty={onOpenProperty} targetOcc={targetOcc} />
    </>
  );
}

// ---------------------------------------------------------------------
// LAYOUT — STACKED  (chart hero, big table below, insights side rail)
// ---------------------------------------------------------------------
function StackedLayout({ filteredStats, portfolio, viewMode, insights, dataQuality, onOpenProperty, targetOcc }) {
  const D = window.TAP_DATA;
  const monthYear = fmtMonthYear(D.MONTH_START);
  return (
    <>
      <div className="panel" style={{ marginBottom: 16 }}>
        <div className="panel__head">
          <div className="panel__head-title">
            <div className="t-eyebrow">Daily Occupancy · Full month</div>
            <div className="t-h2">{viewMode === "finance" ? "Coverage trend" : "Daily occupancy trend"}</div>
          </div>
          <div className="t-eyebrow">Target {fmtPct(targetOcc, 0)}</div>
        </div>
        <div className="panel__body">
          <DailyTrendChart daily={portfolio.dailyAgg} todayDay={D.TODAY_DAY} viewMode={viewMode} target={targetOcc} />
        </div>
      </div>

      <div className="row row--main-rail">
        <div>
          <PropertyTable stats={filteredStats} viewMode={viewMode} onOpenProperty={onOpenProperty} targetOcc={targetOcc} sparkline />
          <div style={{ height: 16 }} />
          <div className="panel">
            <div className="panel__head">
              <div className="panel__head-title">
                <div className="t-eyebrow">Occupancy by Property</div>
                <div className="t-h2">Finance vs Operations</div>
              </div>
            </div>
            <div className="panel__body">
              <PropertyBarChart stats={filteredStats} viewMode={viewMode} onPick={onOpenProperty} />
            </div>
          </div>
        </div>
        <div>
          <RightRail insights={insights} dataQuality={dataQuality} />
          <div style={{ height: 16 }} />
          <div className="panel">
            <div className="panel__head">
              <div className="panel__head-title">
                <div className="t-eyebrow">Calendar</div>
                <div className="t-h2">{monthYear}</div>
              </div>
            </div>
            <div className="panel__body">
              <CalendarHeatmap daily={portfolio.dailyAgg} todayDay={D.TODAY_DAY} />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------
// LAYOUT — DENSE (Bloomberg-style — everything visible)
// ---------------------------------------------------------------------
function DenseLayout({ filteredStats, portfolio, viewMode, insights, dataQuality, onOpenProperty, targetOcc }) {
  const D = window.TAP_DATA;
  return (
    <>
      <div className="row row--main-rail">
        <div>
          <div className="row row--2eq">
            <div className="panel">
              <div className="panel__head">
                <div className="panel__head-title">
                  <div className="t-eyebrow">Daily Trend</div>
                </div>
                <div className="t-eyebrow">Target {fmtPct(targetOcc, 0)}</div>
              </div>
              <div className="panel__body" style={{ padding: 8 }}>
                <DailyTrendChart daily={portfolio.dailyAgg} todayDay={D.TODAY_DAY} viewMode={viewMode} target={targetOcc} />
              </div>
            </div>
            <div className="panel">
              <div className="panel__head">
                <div className="panel__head-title">
                  <div className="t-eyebrow">By Property</div>
                </div>
              </div>
              <div className="panel__body" style={{ padding: 8 }}>
                <PropertyBarChart stats={filteredStats} viewMode={viewMode} onPick={onOpenProperty} />
              </div>
            </div>
          </div>
          <PropertyTable stats={filteredStats} viewMode={viewMode} onOpenProperty={onOpenProperty} targetOcc={targetOcc} compact sparkline />
        </div>
        <div>
          <RightRail insights={insights} dataQuality={dataQuality} />
          <div style={{ height: 16 }} />
          <div className="panel">
            <div className="panel__head">
              <div className="panel__head-title">
                <div className="t-eyebrow">Calendar</div>
              </div>
            </div>
            <div className="panel__body">
              <CalendarHeatmap daily={portfolio.dailyAgg} todayDay={D.TODAY_DAY} />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------
// Right rail — insights + data quality
// ---------------------------------------------------------------------
function RightRail({ insights, dataQuality }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="panel">
        <div className="panel__head">
          <div className="panel__head-title">
            <div className="t-eyebrow t-eyebrow--strong">Needs Attention</div>
            <div className="t-h2" style={{ fontSize: 14 }}>Actionable insights</div>
          </div>
          <span className="tag tag--ghost">{insights.length}</span>
        </div>
        <div className="panel__body panel__body--flush">
          <InsightsList insights={insights} />
        </div>
      </div>
      <div className="panel">
        <div className="panel__head">
          <div className="panel__head-title">
            <div className="t-eyebrow t-eyebrow--strong">Data Quality</div>
            <div className="t-h2" style={{ fontSize: 14 }}>{dataQuality.length} issues</div>
          </div>
          <span className="tag tag--ghost">CRM</span>
        </div>
        <div className="panel__body panel__body--flush">
          <DataQualityList issues={dataQuality} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------
// Property-level table
// ---------------------------------------------------------------------
function PropertyTable({ stats, viewMode, onOpenProperty, targetOcc, compact, sparkline }) {
  const D = window.TAP_DATA;
  const [sort, setSort] = useState({ key: "opsRate", dir: "desc" });
  const sorted = useMemo(() => {
    const s = [...stats];
    s.sort((a, b) => {
      const av = sortValue(a, sort.key);
      const bv = sortValue(b, sort.key);
      if (av < bv) return sort.dir === "asc" ? -1 : 1;
      if (av > bv) return sort.dir === "asc" ? 1 : -1;
      return 0;
    });
    return s;
  }, [stats, sort]);

  function toggleSort(k) {
    setSort(s => s.key === k ? { key: k, dir: s.dir === "asc" ? "desc" : "asc" } : { key: k, dir: "desc" });
  }
  function HeaderCell({ k, children, num }) {
    const active = sort.key === k;
    return (
      <th className={num ? "num" : ""} onClick={() => toggleSort(k)} style={{ cursor: "pointer", userSelect: "none" }}>
        {children} {active ? (sort.dir === "asc" ? "↑" : "↓") : <span style={{ opacity: 0.3 }}>↕</span>}
      </th>
    );
  }

  return (
    <div className="panel">
      <div className="panel__head">
        <div className="panel__head-title">
          <div className="t-eyebrow">Property-Level Report</div>
          <div className="t-h2">{stats.length} {stats.length === 1 ? "property" : "properties"} · click a row to drill in</div>
        </div>
        <div className="t-eyebrow">{viewMode === "finance" ? "Finance %" : "Ops %"} sorted</div>
      </div>
      <div className="panel__body panel__body--flush" style={{ overflowX: "auto" }}>
        <table className={`dt${compact ? " dt--compact" : ""}`}>
          <thead>
            <tr>
              <HeaderCell k="name">Property</HeaderCell>
              <HeaderCell k="units" num>Units</HeaderCell>
              <th>Mix</th>
              <HeaderCell k="financeRate" num>Finance %</HeaderCell>
              <HeaderCell k="opsRate" num>Ops %</HeaderCell>
              {sparkline && <th>Trend</th>}
              <HeaderCell k="delta" num>Δ</HeaderCell>
              <HeaderCell k="moveIns" num>Move-ins</HeaderCell>
              <HeaderCell k="moveOuts" num>Move-outs</HeaderCell>
              <th>Target</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(s => {
              const onTarget = s.opsRate >= s.property.target;
              const near = !onTarget && s.opsRate >= s.property.target - 0.05;
              return (
                <tr key={s.property.id} onClick={() => onOpenProperty(s.property.id)}>
                  <td>
                    <div className="dt__primary">
                      <div>
                        <div>{s.property.name}</div>
                        <div className="dt__sub">{s.property.type.toUpperCase()} · {s.property.region.toUpperCase()}</div>
                      </div>
                    </div>
                  </td>
                  <td className="num">{s.units}</td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <MixBar stats={s} />
                      <span className="dt__sub t-num">{s.occupied}/{s.vacant}/{s.reserved}/{s.maintenance}</span>
                    </div>
                  </td>
                  <td className="num">
                    <PctBar value={s.financeRate} target={s.property.target} />
                  </td>
                  <td className="num">
                    <PctBar value={s.opsRate} target={s.property.target} />
                  </td>
                  {sparkline && (
                    <td className="num"><div style={{ width: 110 }}><PropertySpark daily={s.daily} todayDay={D.TODAY_DAY} /></div></td>
                  )}
                  <td className="num" style={{ color: s.delta >= 0 ? "var(--good)" : "var(--danger)" }}>
                    {fmtSigned(s.delta, 1)}
                  </td>
                  <td className="num">{s.moveIns}</td>
                  <td className="num">{s.moveOuts}</td>
                  <td>
                    {onTarget ? <Tag status="good">On Target</Tag>
                    : near    ? <Tag status="warn">Near</Tag>
                    : <Tag status="bad">Below {fmtPct(s.property.target, 0)}</Tag>}
                  </td>
                  <td className="num"><span className="dt__chev">›</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {sorted.length === 0 && <div className="empty">No properties match the filters.</div>}
      </div>
    </div>
  );
}

function sortValue(s, k) {
  switch (k) {
    case "name":  return s.property.name;
    case "units": return s.units;
    case "financeRate": return s.financeRate;
    case "opsRate":     return s.opsRate;
    case "delta": return s.delta;
    case "moveIns": return s.moveIns;
    case "moveOuts": return s.moveOuts;
    default: return 0;
  }
}

// ---------------------------------------------------------------------
// Export menu
// ---------------------------------------------------------------------
function ExportMenu({ portfolio, filteredStats }) {
  const D = window.TAP_DATA;
  // Derive the current month string from TAP_DATA
  const month = D.MONTH_START
    ? D.MONTH_START.toISOString().slice(0, 7)
    : new Date().toISOString().slice(0, 7);

  function downloadCSV(filename, rows) {
    const csv = rows.map(r => r.map(v => {
      const s = v == null ? "" : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    }).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function propertyCSV() {
    const rows = [["property", "type", "region", "units", "occupied", "vacant", "reserved", "maintenance",
                   "finance_rate", "ops_rate", "target", "delta_vs_prev", "move_ins", "move_outs", "last_updated"]];
    filteredStats.forEach(s => {
      rows.push([s.property.name, s.property.type, s.property.region, s.units,
                 s.occupied, s.vacant, s.reserved, s.maintenance,
                 (s.financeRate * 100).toFixed(2) + "%",
                 (s.opsRate * 100).toFixed(2) + "%",
                 (s.property.target * 100).toFixed(0) + "%",
                 (s.delta * 100).toFixed(2) + "pp",
                 s.moveIns, s.moveOuts, s.lastUpdated || "recently"]);
    });
    downloadCSV(`tap-property-occupancy-${month}.csv`, rows);
  }
  function financeCSV() {
    const rows = [["property", "units", "ever_occupied", "finance_rate"]];
    filteredStats.forEach(s => {
      rows.push([s.property.name, s.units, s.financeOccCount, (s.financeRate * 100).toFixed(2) + "%"]);
    });
    downloadCSV(`tap-finance-${month}.csv`, rows);
  }
  function opsCSV() {
    const rows = [["property", "day", "occupied", "total", "rate"]];
    filteredStats.forEach(s => {
      s.daily.forEach(d => {
        rows.push([s.property.name, `${month}-${String(d.day).padStart(2, "0")}`,
                   d.occ, d.total, (d.rate * 100).toFixed(2) + "%"]);
      });
    });
    downloadCSV(`tap-operations-${month}.csv`, rows);
  }
  function pdf() { window.print(); }

  return (
    <Dropdown trigger={<button className="btn btn--ghost">Export ▾</button>}>
      <div className="dropdown__hint">Reports</div>
      <button className="dropdown__item" onClick={propertyCSV}>Property report · CSV</button>
      <button className="dropdown__item" onClick={financeCSV}>Finance monthly · CSV</button>
      <button className="dropdown__item" onClick={opsCSV}>Operations daily · CSV</button>
      <div className="dropdown__sep" />
      <button className="dropdown__item" onClick={pdf}>Dashboard snapshot · PDF</button>
    </Dropdown>
  );
}

// ---------------------------------------------------------------------
// Properties screen — full table view
// ---------------------------------------------------------------------
function PropertiesScreen({ filteredStats, viewMode, setViewMode, filters, setFilter, resetFilters, onOpenProperty, targetOcc, portfolio }) {
  return (
    <>
      <div className="pageheader">
        <div className="pageheader__title">
          <div className="t-eyebrow">Properties</div>
          <h1 className="t-h1">Portfolio</h1>
          <p className="t-lede">{filteredStats.length} properties · {filteredStats.reduce((a,s) => a + s.units, 0)} units · click any row to drill into units.</p>
        </div>
        <div className="pageheader__actions">
          <ExportMenu portfolio={portfolio} filteredStats={filteredStats} />
        </div>
      </div>
      <FilterBar filters={filters} setFilter={setFilter} resetFilters={resetFilters} viewMode={viewMode} setViewMode={setViewMode} />
      <PropertyTable stats={filteredStats} viewMode={viewMode} onOpenProperty={onOpenProperty} targetOcc={targetOcc} sparkline />
    </>
  );
}

// ---------------------------------------------------------------------
// Insights screen
// ---------------------------------------------------------------------
function InsightsScreen({ insights, dataQuality }) {
  return (
    <>
      <div className="pageheader">
        <div className="pageheader__title">
          <div className="t-eyebrow">Action Center</div>
          <h1 className="t-h1">Insights & Data Quality</h1>
          <p className="t-lede">Issues that need eyes before the monthly close — surfaced from CRM data.</p>
        </div>
      </div>
      <div className="row row--2eq">
        <div className="panel">
          <div className="panel__head">
            <div className="panel__head-title">
              <div className="t-eyebrow t-eyebrow--strong">Needs Attention</div>
              <div className="t-h2">{insights.length} actionable items</div>
            </div>
          </div>
          <div className="panel__body panel__body--flush">
            <InsightsList insights={insights} />
          </div>
        </div>
        <div className="panel">
          <div className="panel__head">
            <div className="panel__head-title">
              <div className="t-eyebrow t-eyebrow--strong">Data Quality</div>
              <div className="t-h2">{dataQuality.length} issues from CRM</div>
            </div>
          </div>
          <div className="panel__body panel__body--flush">
            <DataQualityList issues={dataQuality} />
          </div>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------
// Settings screen — target occupancy
// ---------------------------------------------------------------------
function SettingsScreen({ targetOcc, setTargetOcc, perPropertyTargets, setPerPropertyTarget, showToast }) {
  const D = window.TAP_DATA;
  const [draft, setDraft] = useState(Math.round(targetOcc * 100));
  useEffect(() => { setDraft(Math.round(targetOcc * 100)); }, [targetOcc]);

  function save() {
    setTargetOcc(draft / 100);
    showToast("Target saved");
  }

  return (
    <>
      <div className="pageheader">
        <div className="pageheader__title">
          <div className="t-eyebrow">Configuration</div>
          <h1 className="t-h1">Targets</h1>
          <p className="t-lede">Set a portfolio-wide occupancy target and override per property. Targets drive the “On / Near / Below” pills on the dashboard.</p>
        </div>
      </div>

      <div className="row row--2eq">
        <div className="panel">
          <div className="panel__head">
            <div className="panel__head-title">
              <div className="t-eyebrow">Global Target</div>
              <div className="t-h2">Portfolio-wide occupancy goal</div>
            </div>
          </div>
          <div className="panel__body">
            <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14 }}>
              <input type="range" min="60" max="100" step="1"
                     value={draft} onChange={e => setDraft(+e.target.value)}
                     style={{ flex: 1, accentColor: "var(--ink-1)" }} />
              <div style={{ minWidth: 80, textAlign: "right" }}>
                <div className="t-mono" style={{ fontSize: 32, fontWeight: 700, lineHeight: 1 }}>{draft}%</div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <button className="btn btn--primary" onClick={save}>Save Target</button>
              <button className="btn btn--ghost" onClick={() => setDraft(90)}>Reset to 90%</button>
              <span className="t-eyebrow" style={{ marginLeft: "auto" }}>Near-target band: ±5%</span>
            </div>
            <div className="divider" />
            <div className="t-eyebrow" style={{ marginBottom: 10 }}>Preview</div>
            <div style={{ display: "flex", gap: 8 }}>
              <Tag status="good">≥ {draft}% On Target</Tag>
              <Tag status="warn">{Math.max(0, draft - 5)}–{draft}% Near</Tag>
              <Tag status="bad">&lt; {Math.max(0, draft - 5)}% Below</Tag>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel__head">
            <div className="panel__head-title">
              <div className="t-eyebrow">Per-Property Overrides</div>
              <div className="t-h2">Set a custom target per property</div>
            </div>
          </div>
          <div className="panel__body panel__body--flush">
            <table className="dt dt--compact">
              <thead>
                <tr>
                  <th>Property</th>
                  <th className="num">Current</th>
                  <th className="num">Target</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {D.PROPERTIES.map(p => {
                  const stat = D.PROPERTY_STATS.find(s => s.property.id === p.id);
                  const t = perPropertyTargets[p.id] != null ? perPropertyTargets[p.id] : p.target;
                  const onTarget = stat.opsRate >= t;
                  return (
                    <tr key={p.id} style={{ cursor: "default" }}>
                      <td>
                        <div className="dt__primary">
                          <div>
                            <div>{p.name}</div>
                            <div className="dt__sub">{p.type.toUpperCase()} · {p.region.toUpperCase()}</div>
                          </div>
                        </div>
                      </td>
                      <td className="num">{fmtPct(stat.opsRate, 1)}</td>
                      <td className="num">
                        <input className="input input--num" type="number" min="60" max="100" step="1"
                               value={Math.round(t * 100)}
                               onChange={e => setPerPropertyTarget(p.id, (+e.target.value || 90) / 100)}
                               style={{ width: 60, padding: "4px 8px", fontSize: 12 }} />
                        <span style={{ color: "var(--ink-4)", fontFamily: "var(--font-mono)", marginLeft: 4 }}>%</span>
                      </td>
                      <td>
                        {onTarget ? <Tag status="good">On Target</Tag> : <Tag status="bad">Below</Tag>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 16 }} className="panel">
        <div className="panel__head">
          <div className="panel__head-title">
            <div className="t-eyebrow">How TAP calculates occupancy</div>
            <div className="t-h2">Finance vs Operations</div>
          </div>
        </div>
        <div className="panel__body">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
            <div>
              <div className="t-eyebrow" style={{ marginBottom: 8 }}><span style={{ color: "var(--res)" }}>Finance View</span></div>
              <p style={{ margin: 0, color: "var(--ink-2)", fontSize: 13, lineHeight: 1.6 }}>
                A room / bed / unit counts as occupied if it was let at any point during the selected month.
                Use this for monthly close and revenue reconciliation. One single number per property per month.
              </p>
              <pre className="t-mono" style={{ background: "var(--bg-1)", padding: 12, borderRadius: 4,
                                    marginTop: 12, fontSize: 12, lineHeight: 1.5, border: "1px solid var(--line)" }}>
{`finance_rate = (units occupied at any point in month)
               / (total available units)`}
              </pre>
            </div>
            <div>
              <div className="t-eyebrow" style={{ marginBottom: 8 }}><span style={{ color: "var(--occ)" }}>Operations View</span></div>
              <p style={{ margin: 0, color: "var(--ink-2)", fontSize: 13, lineHeight: 1.6 }}>
                Each calendar day is counted separately. The monthly figure is the average of daily occupancy rates.
                Use this for live ops: vacant units, upcoming move-outs, marketing pressure.
              </p>
              <pre className="t-mono" style={{ background: "var(--bg-1)", padding: 12, borderRadius: 4,
                                    marginTop: 12, fontSize: 12, lineHeight: 1.5, border: "1px solid var(--line)" }}>
{`daily_rate   = (units occupied on day d) / (units available)
ops_rate     = avg(daily_rate for d in month)`}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, {
  OverviewScreen, PropertiesScreen, InsightsScreen, SettingsScreen,
  PropertyTable, ExportMenu,
});
