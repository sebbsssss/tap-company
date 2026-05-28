/* ============================================================
   TAP — Filter bar
   ============================================================ */

function FilterBar({ filters, setFilter, resetFilters, viewMode, setViewMode }) {
  const D = window.TAP_DATA;
  const propertyTypes = ["All", "Co-living", "Serviced", "Student"];
  const regions = ["All", "North", "South", "East", "West", "Central"];
  const statuses = ["All", "Occupied", "Vacant", "Reserved", "Maintenance"];

  // Generate 4 month options ending at the current data month.
  const monthOptions = useMemo(() => {
    const ms = D.MONTH_START;
    return Array.from({ length: 4 }, (_, i) => {
      const d = new Date(Date.UTC(ms.getUTCFullYear(), ms.getUTCMonth() - i, 1));
      return {
        value: d.toISOString().slice(0, 7),
        label: d.toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" }),
      };
    });
  }, []);

  return (
    <div className="filterbar">
      <div className="filterbar__group">
        <span className="filterbar__label">Month</span>
        <select className="select" value={filters.month} onChange={(e) => setFilter("month", e.target.value)}>
          {monthOptions.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
      </div>
      <div className="filterbar__sep" />
      <div className="filterbar__group">
        <span className="filterbar__label">Property</span>
        <select className="select" value={filters.property} onChange={(e) => setFilter("property", e.target.value)}>
          <option value="All">All Properties</option>
          {D.PROPERTIES.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>
      <div className="filterbar__group">
        <span className="filterbar__label">Type</span>
        <select className="select" value={filters.ptype} onChange={(e) => setFilter("ptype", e.target.value)}>
          {propertyTypes.map(t => <option key={t} value={t}>{t === "All" ? "All Types" : t}</option>)}
        </select>
      </div>
      <div className="filterbar__group">
        <span className="filterbar__label">Region</span>
        <select className="select" value={filters.region} onChange={(e) => setFilter("region", e.target.value)}>
          {regions.map(r => <option key={r} value={r}>{r === "All" ? "All Regions" : r}</option>)}
        </select>
      </div>
      <div className="filterbar__group">
        <span className="filterbar__label">Status</span>
        <select className="select" value={filters.status} onChange={(e) => setFilter("status", e.target.value)}>
          {statuses.map(s => <option key={s} value={s.toLowerCase()}>{s === "All" ? "All Statuses" : s}</option>)}
        </select>
      </div>

      <div className="filterbar__spacer" />

      <div className="filterbar__group">
        <span className="filterbar__label">View</span>
        <Segmented
          value={viewMode}
          onChange={setViewMode}
          options={[
            { value: "finance",    label: "Finance" },
            { value: "operations", label: "Operations" },
          ]}
        />
      </div>

      <button className="filterbar__reset" onClick={resetFilters}>Reset</button>
    </div>
  );
}

Object.assign(window, { FilterBar });
