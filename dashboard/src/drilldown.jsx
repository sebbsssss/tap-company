/* ============================================================
   TAP — Drill-down slide-over (Property → Units)
   ============================================================ */

function PropertyDrilldown({ propertyId, onClose, viewMode }) {
  const D = window.TAP_DATA;
  const stat = D.PROPERTY_STATS.find(s => s.property.id === propertyId);
  const [tab, setTab] = useState("units");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedUnit, setSelectedUnit] = useState(null);

  useEffect(() => {
    setTab("units"); setStatusFilter("all"); setSelectedUnit(null);
  }, [propertyId]);

  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!stat) return null;
  const p = stat.property;
  const units = D.UNITS.filter(u => u.propertyId === p.id);
  const filteredUnits = statusFilter === "all" ? units : units.filter(u => u.status === statusFilter);

  return (
    <div className="slideover is-open" role="dialog" aria-label={p.name + " details"}>
      <div className="slideover__head">
        <div>
          <div className="t-eyebrow" style={{ marginBottom: 8 }}>Property · {p.id}</div>
          <div className="t-h1">{p.name}</div>
          <div style={{ display: "flex", gap: 12, marginTop: 8, color: "var(--ink-3)", fontSize: 12 }}>
            <span><Tag>{p.type.toUpperCase()}</Tag></span>
            <span style={{ alignSelf: "center" }}>· {p.region} Region</span>
            <span style={{ alignSelf: "center" }}>· {p.units} units</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
          <a className="btn btn--ghost btn--sm" href="#" onClick={e => e.preventDefault()}
             title="Open in CRM (Zoho)">CRM ↗</a>
          <button className="slideover__close" onClick={onClose} aria-label="Close">✕</button>
        </div>
      </div>

      <div className="slideover__tabs">
        {[
          { id: "units",   label: "Units" },
          { id: "summary", label: "Summary" },
          { id: "trend",   label: "Trend" },
        ].map(t => (
          <button key={t.id}
                  className={`slideover__tab${tab === t.id ? " is-active" : ""}`}
                  onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>

      <div className="slideover__body">
        {tab === "summary" && <DrilldownSummary stat={stat} viewMode={viewMode} />}
        {tab === "units" && (
          <DrilldownUnits
            stat={stat}
            statusFilter={statusFilter}
            setStatusFilter={setStatusFilter}
            filteredUnits={filteredUnits}
            selectedUnit={selectedUnit}
            setSelectedUnit={setSelectedUnit}
          />
        )}
        {tab === "trend" && <DrilldownTrend stat={stat} viewMode={viewMode} />}
      </div>
    </div>
  );
}

function DrilldownSummary({ stat, viewMode }) {
  const p = stat.property;
  return (
    <div style={{ paddingTop: 18 }}>
      <div className="kpigrid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KPI label="Finance %" value={fmtPct(stat.financeRate, 1)} sub={`${stat.financeOccCount} of ${stat.units} ever occupied`} />
        <KPI label="Operations %" value={fmtPct(stat.opsRate, 1)} sub={fmtSigned(stat.delta) + " vs last month"} subTone={stat.delta >= 0 ? "good" : "bad"} />
        <KPI label="Target" value={fmtPct(p.target, 0)} sub={stat.opsRate >= p.target ? "On target" : "Below target"} subTone={stat.opsRate >= p.target ? "good" : "bad"} />
        <KPI label="Vacant" value={stat.vacant} sub={`${stat.reserved} reserved · ${stat.maintenance} mnt`} />
      </div>

      <div className="t-eyebrow" style={{ marginTop: 24, marginBottom: 10 }}>Unit Mix · As of Today</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 1, background: "var(--line)",
                    border: "1px solid var(--line)", borderRadius: "var(--r-2)", overflow: "hidden" }}>
        {[
          { key: "occupied",    label: "Occupied",    value: stat.occupied,    cls: "dot--occ" },
          { key: "vacant",      label: "Vacant",      value: stat.vacant,      cls: "dot--vac" },
          { key: "reserved",    label: "Reserved",    value: stat.reserved,    cls: "dot--res" },
          { key: "maintenance", label: "Maintenance", value: stat.maintenance, cls: "dot--mnt" },
        ].map(r => (
          <div key={r.key} className="kpi">
            <div className="kpi__label"><span className={"dot " + r.cls} style={{ marginRight: 6 }} />{r.label}</div>
            <div className="kpi__value">{r.value}</div>
            <div className="kpi__sub">{fmtPct(r.value / stat.units, 0)} of stock</div>
          </div>
        ))}
      </div>

      <div className="t-eyebrow" style={{ marginTop: 24, marginBottom: 10 }}>Move Activity</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line)",
                    border: "1px solid var(--line)", borderRadius: "var(--r-2)", overflow: "hidden" }}>
        <div className="kpi">
          <div className="kpi__label">Move-ins this month</div>
          <div className="kpi__value">{stat.moveIns}</div>
        </div>
        <div className="kpi">
          <div className="kpi__label">Move-outs (next 30 days)</div>
          <div className="kpi__value">{stat.moveOuts}</div>
        </div>
      </div>
    </div>
  );
}

function DrilldownTrend({ stat, viewMode }) {
  const D = window.TAP_DATA;
  return (
    <div style={{ paddingTop: 18 }}>
      <div className="panel">
        <div className="panel__head">
          <div className="panel__head-title">
            <div className="t-eyebrow">Daily Occupancy · May 2026</div>
            <div className="t-h2">{stat.property.name}</div>
          </div>
        </div>
        <div className="panel__body">
          <DailyTrendChart daily={stat.daily} todayDay={D.TODAY_DAY} viewMode={viewMode} target={stat.property.target} />
        </div>
      </div>
      <div style={{ marginTop: 16 }}>
        <div className="t-eyebrow" style={{ marginBottom: 10 }}>Calendar Heatmap</div>
        <CalendarHeatmap daily={stat.daily} todayDay={D.TODAY_DAY} />
      </div>
    </div>
  );
}

function DrilldownUnits({ stat, statusFilter, setStatusFilter, filteredUnits, selectedUnit, setSelectedUnit }) {
  return (
    <div style={{ paddingTop: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div className="t-eyebrow">Units · {filteredUnits.length} shown · {stat.units} total</div>
        <Segmented
          value={statusFilter}
          onChange={setStatusFilter}
          options={[
            { value: "all",         label: "All" },
            { value: "occupied",    label: "Occ" },
            { value: "vacant",      label: "Vac" },
            { value: "reserved",    label: "Res" },
            { value: "maintenance", label: "Mnt" },
          ]}
        />
      </div>

      <div className="panel" style={{ borderRadius: 4 }}>
        <table className="dt dt--compact">
          <thead>
            <tr>
              <th>Unit</th>
              <th>Status</th>
              <th>Tenant</th>
              <th>Lease</th>
              <th className="num">Days Vac</th>
              <th>Next Avail</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filteredUnits.map(u => (
              <React.Fragment key={u.id}>
                <tr className={selectedUnit === u.id ? "is-selected" : ""}
                    onClick={() => setSelectedUnit(selectedUnit === u.id ? null : u.id)}>
                  <td>
                    <div className="dt__primary">
                      <Dot status={u.status} />
                      <div>
                        <div>{u.label}</div>
                        <div className="dt__sub">{u.kind} · Floor {u.floor}</div>
                      </div>
                    </div>
                  </td>
                  <td><Tag status={u.status}>{statusLabel(u.status)}</Tag></td>
                  <td>{u.tenant || <span style={{ color: "var(--ink-4)" }}>—</span>}</td>
                  <td className="num">
                    {u.leaseStart ? `${fmtDateMD(u.leaseStart)} → ${fmtDateMD(u.leaseEnd)}` : "—"}
                  </td>
                  <td className="num">{u.daysVacant > 0 ? u.daysVacant : "—"}</td>
                  <td className="num">{fmtDateMD(u.nextAvailable)}</td>
                  <td className="num"><span className="dt__chev">{selectedUnit === u.id ? "▾" : "›"}</span></td>
                </tr>
                {selectedUnit === u.id && (
                  <tr className="is-selected">
                    <td colSpan={7} style={{ background: "var(--bg-1)", padding: 18 }}>
                      <UnitDetail unit={u} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
        {filteredUnits.length === 0 && <div className="empty">No units match.</div>}
      </div>
    </div>
  );
}

function UnitDetail({ unit }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}>
      <dl className="kv">
        <dt>Unit ID</dt><dd>{unit.id}</dd>
        <dt>Kind</dt><dd>{unit.kind}</dd>
        <dt>Floor</dt><dd>{unit.floor}</dd>
        <dt>Status</dt><dd><Tag status={unit.status}>{statusLabel(unit.status)}</Tag></dd>
        <dt>Tenant</dt><dd>{unit.tenant || <span style={{ color: "var(--ink-4)" }}>—</span>}</dd>
        <dt>Lease start</dt><dd>{fmtDateShort(unit.leaseStart)}</dd>
        <dt>Lease end</dt><dd>{fmtDateShort(unit.leaseEnd)}</dd>
      </dl>
      <dl className="kv">
        <dt>Move-in</dt><dd>{fmtDateShort(unit.moveIn)}</dd>
        <dt>Move-out</dt><dd>{fmtDateShort(unit.moveOut)}</dd>
        <dt>Days vacant</dt><dd>{unit.daysVacant > 0 ? unit.daysVacant + " days" : "—"}</dd>
        <dt>Next available</dt><dd>{fmtDateShort(unit.nextAvailable)}</dd>
        <dt>Notes</dt><dd style={{ color: unit.notes ? "var(--ink-1)" : "var(--ink-4)" }}>{unit.notes || "—"}</dd>
        <dt>CRM</dt><dd><a className="t-mono" style={{ color: "var(--ink-1)", textDecoration: "underline" }}
                            href="#" onClick={e => e.preventDefault()}>Open record ↗</a></dd>
      </dl>

      {unit.dqFlags && unit.dqFlags.length > 0 && (
        <div style={{ gridColumn: "1 / -1", marginTop: 6, padding: "10px 12px", border: "1px solid rgba(184,58,43,0.25)",
                      background: "var(--danger-tint)", borderRadius: 4, fontFamily: "var(--font-mono)", fontSize: 11,
                      color: "var(--danger)" }}>
          ⚠ Data quality: {unit.dqFlags.join(", ")}
        </div>
      )}

      <div style={{ gridColumn: "1 / -1" }}>
        <div className="t-eyebrow" style={{ marginBottom: 8 }}>Occupancy this month</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(31, 1fr)", gap: 2 }}>
          {unit.days.map((occ, i) => (
            <div key={i}
                 title={`May ${i+1}: ${occ ? "occupied" : "vacant"}`}
                 style={{
                   aspectRatio: "1/1.6",
                   background: occ ? "var(--occ)" : "var(--bg-2)",
                   borderRadius: 2,
                   opacity: occ ? 0.7 : 1,
                 }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { PropertyDrilldown });
