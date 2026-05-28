/* ============================================================
   TAP — atoms & helpers
   ============================================================ */

const { useState, useEffect, useRef, useMemo, useCallback } = React;

// -------- formatters --------------------------------------------------
const fmtPct = (v, d = 1) => (v == null || isNaN(v)) ? "—" : `${(v * 100).toFixed(d)}%`;
const fmtPct0 = (v) => fmtPct(v, 0);
const fmtNum = (v) => (v == null || isNaN(v)) ? "—" : new Intl.NumberFormat("en-US").format(v);
const fmtSigned = (v, d = 1) => {
  if (v == null || isNaN(v)) return "—";
  const s = (v * 100).toFixed(d);
  return (v >= 0 ? "+" : "") + s + "pp";
};
const fmtDateShort = (s) => {
  if (!s) return "—";
  const d = new Date(s + "T00:00:00Z");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
};
const fmtDateMD = (s) => {
  if (!s) return "—";
  const d = new Date(s + "T00:00:00Z");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
};
const fmtMonthYear = (d) => d
  ? d.toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" })
  : "";
const fmtMonthAbbr = (d) => d
  ? d.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" })
  : "";
const statusLabel = (s) => ({ occupied: "Occupied", vacant: "Vacant", reserved: "Reserved", maintenance: "Maintenance" }[s] || s);

// -------- tag / dot --------------------------------------------------
function Tag({ status, children, className }) {
  const cls = "tag tag--" + (
    status === "occupied" ? "occ" :
    status === "vacant" ? "vac" :
    status === "reserved" ? "res" :
    status === "maintenance" ? "mnt" :
    status || "ghost"
  );
  return <span className={`${cls}${className ? " " + className : ""}`}>{children}</span>;
}
function Dot({ status }) {
  const cls = "dot dot--" + (
    status === "occupied" ? "occ" :
    status === "vacant" ? "vac" :
    status === "reserved" ? "res" :
    "mnt"
  );
  return <span className={cls} />;
}

// -------- KPI card ---------------------------------------------------
function KPI({ label, value, suffix, sub, subTone, accent }) {
  return (
    <div className={`kpi${accent ? " kpi--accent" : ""}`}>
      <div className="kpi__label">{label}</div>
      <div className="kpi__value">
        <span>{value}</span>
        {suffix && <span className="kpi__suffix">{suffix}</span>}
      </div>
      {sub && (
        <div className={`kpi__sub ${subTone ? "kpi__sub--" + subTone : ""}`}>{sub}</div>
      )}
    </div>
  );
}

// -------- Pct bar --------------------------------------------------
function PctBar({ value, target }) {
  const pct = Math.max(0, Math.min(1, value));
  const cls = target == null ? "" :
              value >= target ? "is-good" :
              value >= target - 0.05 ? "is-warn" : "is-bad";
  return (
    <span className="dt__pct">
      <span className="dt__bar"><i className={cls} style={{ right: `${(1 - pct) * 100}%` }} /></span>
      <span>{fmtPct(value, 1)}</span>
    </span>
  );
}

// -------- Mix bar (status fractions) -------------------------------
function MixBar({ stats }) {
  const total = stats.units || 1;
  const o = stats.occupied / total;
  const r = stats.reserved / total;
  const m = stats.maintenance / total;
  const v = stats.vacant / total;
  return (
    <div className="mix" title={`Occ ${stats.occupied} · Res ${stats.reserved} · Mnt ${stats.maintenance} · Vac ${stats.vacant}`}>
      <span className="occ" style={{ width: `${o * 100}%` }} />
      <span className="res" style={{ width: `${r * 100}%` }} />
      <span className="mnt" style={{ width: `${m * 100}%` }} />
      <span className="vac" style={{ width: `${v * 100}%` }} />
    </div>
  );
}

// -------- Sparkline -------------------------------------------------
function Sparkline({ values, color = "var(--ink-1)", height = 28, baseline }) {
  if (!values || !values.length) return <svg className="spark" />;
  const w = 120, h = height, p = 2;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = (max - min) || 1;
  const pts = values.map((v, i) => {
    const x = p + (i / (values.length - 1)) * (w - p * 2);
    const y = h - p - ((v - min) / range) * (h - p * 2);
    return [x, y];
  });
  const path = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const area = path + ` L${w - p},${h - p} L${p},${h - p} Z`;
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ height }}>
      <path d={area} fill={color} opacity="0.08" />
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      {baseline != null && (
        <line x1={p} x2={w - p} y1={h - p - ((baseline - min) / range) * (h - p * 2)}
              y2={h - p - ((baseline - min) / range) * (h - p * 2)}
              stroke="var(--ink-5)" strokeWidth="1" strokeDasharray="2 3" />
      )}
    </svg>
  );
}

// -------- Dropdown (click-outside) ---------------------------------
function Dropdown({ trigger, children, align = "right" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    function onClick(e) {
      if (!ref.current) return;
      if (!ref.current.contains(e.target)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);
  return (
    <div className="dropdown" ref={ref}>
      {React.cloneElement(trigger, { onClick: () => setOpen(o => !o) })}
      {open && (
        <div className="dropdown__menu" style={align === "left" ? { right: "auto", left: 0 } : null}
             onClick={() => setOpen(false)}>
          {children}
        </div>
      )}
    </div>
  );
}

// -------- Toast (simple, ephemeral) ---------------------------------
function useToast() {
  const [msg, setMsg] = useState(null);
  const tRef = useRef(null);
  function show(text) {
    setMsg(text);
    clearTimeout(tRef.current);
    tRef.current = setTimeout(() => setMsg(null), 1800);
  }
  const el = msg ? <div className="toast is-on">{msg}</div> : null;
  return [show, el];
}

// -------- Pill segment toggle --------------------------------------
function Segmented({ value, onChange, options }) {
  return (
    <div className="segmented" role="tablist">
      {options.map(opt => (
        <button key={opt.value}
                className={`segmented__btn${opt.value === value ? " is-active" : ""}`}
                onClick={() => onChange(opt.value)}
                role="tab"
                aria-selected={opt.value === value}>
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// expose
Object.assign(window, {
  fmtPct, fmtPct0, fmtNum, fmtSigned, fmtDateShort, fmtDateMD, fmtMonthYear, fmtMonthAbbr, statusLabel,
  Tag, Dot, KPI, PctBar, MixBar, Sparkline, Dropdown, useToast, Segmented,
});
