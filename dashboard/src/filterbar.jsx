/* ============================================================
   TAP — Filter bar
   ============================================================ */

function FilterBar({ filters, setFilter, resetFilters, viewMode, setViewMode }) {
  const D = window.TAP_DATA;
  const propertyTypes = ["All", "Co-living", "Serviced", "Student"];
  const regions = ["All", "North", "South", "East", "West", "Central"];
  const statuses = ["All", "Occupied", "Vacant", "Reserved", "Maintenance"];

  return (
    <div className="filterbar">
      <div className="filterbar__group">
        <span className="filterbar__label">Month</span>
        <select className="select" value={filters.month} onChange={(e) => setFilter("month", e.target.value)}>
          <option value="2026-05">May 2026</option>
          <option value="2026-04">Apr 2026</option>
          <option value="2026-03">Mar 2026</option>
          <option value="2026-02">Feb 2026</option>
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
