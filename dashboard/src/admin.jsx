/* ============================================================
   TAP — Admin screen (Join requests + Active users)
   Gated to users with role = "admin" in app.jsx
   ============================================================ */

const SEED_REQUESTS = [
  { id: "REQ-A41Q", firstName: "Maya", lastName: "Chen",  email: "maya.chen@assemblyplace.co",
    role: "ops", properties: ["P01", "P02"],
    submitted: "2026-05-26T09:42:00Z", status: "pending",
    note: "New ops team hire — Q2 onboarding cohort." },
  { id: "REQ-B7T2", firstName: "Theo", lastName: "Park",  email: "theo.park@assemblyplace.co",
    role: "finance", properties: "all",
    submitted: "2026-05-27T14:18:00Z", status: "pending",
    note: "Replacing previous finance lead." },
  { id: "REQ-C9XD", firstName: "Iris", lastName: "Walsh", email: "iris.walsh@assemblyplace.co",
    role: "gm", properties: ["P05", "P07"],
    submitted: "2026-05-28T08:05:00Z", status: "pending",
    note: "Promoted to West region GM." },
  { id: "REQ-D2LR", firstName: "Felix", lastName: "Tanaka", email: "felix@nordconsulting.co",
    role: "ops", properties: ["P06"],
    submitted: "2026-05-28T11:30:00Z", status: "pending",
    note: "External consultant — temporary 60-day access." },
  { id: "REQ-E6PM", firstName: "Hana", lastName: "Lin",   email: "hana.lin@assemblyplace.co",
    role: "ops", properties: ["P03", "P05"],
    submitted: "2026-05-25T16:14:00Z", status: "approved",
    note: "Approved by Anya Patel." },
  { id: "REQ-F3KS", firstName: "Diego", lastName: "Rossi", email: "diego@external-vendor.com",
    role: "admin", properties: "all",
    submitted: "2026-05-24T10:02:00Z", status: "denied",
    note: "Denied — admin requests require GM approval." },
];

const ACTIVE_USERS = [
  { id: "USR-000", firstName: "Sebastien", lastName: "",      email: "sebastien@clude.io",
    role: "admin", properties: "all",                  lastActive: "Just now",   status: "active" },
  { id: "USR-001", firstName: "Anya",  lastName: "Patel",   email: "anya.patel@assemblyplace.co",
    role: "admin", properties: "all",                  lastActive: "2 min ago",  status: "active" },
  { id: "USR-002", firstName: "Leo",   lastName: "Garcia",  email: "leo.garcia@assemblyplace.co",
    role: "gm",    properties: "all",                  lastActive: "14 min ago", status: "active" },
  { id: "USR-003", firstName: "Mira",  lastName: "Singh",   email: "mira.singh@assemblyplace.co",
    role: "ops",   properties: ["P01", "P02", "P04"],  lastActive: "1 hr ago",   status: "active" },
  { id: "USR-004", firstName: "Owen",  lastName: "Cohen",   email: "owen.cohen@assemblyplace.co",
    role: "finance", properties: "all",                lastActive: "Yesterday", status: "active" },
  { id: "USR-005", firstName: "Naomi", lastName: "Antonsen", email: "naomi.a@assemblyplace.co",
    role: "ops",   properties: ["P05", "P07", "P08"],  lastActive: "Yesterday", status: "active" },
  { id: "USR-006", firstName: "Kai",   lastName: "Murphy",  email: "kai.murphy@assemblyplace.co",
    role: "ops",   properties: ["P06"],                lastActive: "3 days ago", status: "suspended" },
];

const ROLE_LABELS = {
  ops:     "Operations",
  finance: "Finance",
  gm:      "General Manager",
  admin:   "Admin",
};

function timeAgo(iso) {
  const now = new Date("2026-05-29T10:00:00Z");
  const d = new Date(iso);
  const mins = Math.floor((now - d) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return mins + " min ago";
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + " hr ago";
  const days = Math.floor(hrs / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return days + " days ago";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

function PropList({ value }) {
  const D = window.TAP_DATA;
  if (value === "all") return <span className="t-mono" style={{ color: "var(--ink-2)" }}>All properties</span>;
  if (!Array.isArray(value) || value.length === 0) return <span style={{ color: "var(--ink-4)" }}>—</span>;
  const names = value.map(id => D.PROPERTIES.find(p => p.id === id)).filter(Boolean);
  if (names.length <= 2) {
    return <span className="t-mono" style={{ color: "var(--ink-2)" }}>
      {names.map(n => n.name).join(", ")}
    </span>;
  }
  return <span className="t-mono" style={{ color: "var(--ink-2)" }}>
    {names[0].name}, {names[1].name}
    <span style={{ color: "var(--ink-4)" }}> +{names.length - 2} more</span>
  </span>;
}

function RoleTag({ role }) {
  return <Tag className="">{ROLE_LABELS[role] || role}</Tag>;
}

function StatusTag({ status }) {
  if (status === "approved" || status === "active") return <Tag status="good">{status === "approved" ? "Approved" : "Active"}</Tag>;
  if (status === "denied")    return <Tag status="bad">Denied</Tag>;
  if (status === "suspended") return <Tag status="warn">Suspended</Tag>;
  return <Tag status="warn">Pending</Tag>;
}

// ============================================================
// Admin screen
// ============================================================
function AdminScreen({ showToast }) {
  // Combine seeded + signup-generated requests
  const [requests, setRequests] = useState(() => {
    let dynamic = [];
    try {
      dynamic = JSON.parse(localStorage.getItem("tap.joinRequests") || "[]");
    } catch (e) { dynamic = []; }
    // Decisions overlay
    let decisions = {};
    try { decisions = JSON.parse(localStorage.getItem("tap.requestDecisions") || "{}"); }
    catch (e) { decisions = {}; }
    const all = [...dynamic, ...SEED_REQUESTS];
    return all.map(r => decisions[r.id] ? { ...r, status: decisions[r.id].status, note: decisions[r.id].note || r.note } : r);
  });

  function persist(nextRequests) {
    setRequests(nextRequests);
    const decisions = {};
    nextRequests.forEach(r => {
      if (r.status !== "pending") decisions[r.id] = { status: r.status, note: r.note };
    });
    localStorage.setItem("tap.requestDecisions", JSON.stringify(decisions));
  }

  function decide(id, status) {
    const next = requests.map(r => r.id === id ? {
      ...r,
      status,
      note: status === "approved" ? "Approved by you · " + new Date().toLocaleDateString() : "Denied by you · " + new Date().toLocaleDateString(),
    } : r);
    persist(next);
    showToast(status === "approved" ? "Request approved" : "Request denied");
  }
  function resetDecision(id) {
    const dynamic = (JSON.parse(localStorage.getItem("tap.joinRequests") || "[]"));
    const seed = SEED_REQUESTS;
    const all = [...dynamic, ...seed];
    const original = all.find(r => r.id === id);
    if (!original) return;
    const next = requests.map(r => r.id === id ? { ...original } : r);
    persist(next);
    showToast("Decision reverted");
  }

  // Filters
  const [filter, setFilter] = useState("pending");
  const [tab, setTab] = useState("requests");
  const [expanded, setExpanded] = useState(null);

  const visibleRequests = useMemo(() => {
    if (filter === "all") return requests;
    return requests.filter(r => r.status === filter);
  }, [requests, filter]);

  const counts = useMemo(() => ({
    pending:  requests.filter(r => r.status === "pending").length,
    approved: requests.filter(r => r.status === "approved").length,
    denied:   requests.filter(r => r.status === "denied").length,
  }), [requests]);

  const userCounts = useMemo(() => ({
    active:    ACTIVE_USERS.filter(u => u.status === "active").length,
    suspended: ACTIVE_USERS.filter(u => u.status === "suspended").length,
    admins:    ACTIVE_USERS.filter(u => u.role === "admin").length,
  }), []);

  return (
    <>
      <div className="pageheader">
        <div className="pageheader__title">
          <div className="t-eyebrow">Admin · Access Control</div>
          <h1 className="t-h1">Approvals</h1>
          <p className="t-lede">Approve join requests and manage who can see which properties. Only admins see this page.</p>
        </div>
        <div className="pageheader__actions">
          <span className="tag tag--ghost" style={{ alignSelf: "center" }}>You · Admin</span>
        </div>
      </div>

      {/* KPI summary */}
      <div className="kpigrid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KPI
          label="Pending Requests"
          value={fmtNum(counts.pending)}
          sub={counts.pending > 0 ? "Awaiting your review" : "All clear"}
          subTone={counts.pending > 0 ? "warn" : "good"}
          accent
        />
        <KPI label="Approved (30d)" value={fmtNum(counts.approved)} sub="Active in workspace" />
        <KPI label="Denied (30d)"   value={fmtNum(counts.denied)}   sub="Archived for audit" />
        <KPI label="Active Users"   value={fmtNum(userCounts.active)}
              sub={`${userCounts.admins} admins · ${userCounts.suspended} suspended`} />
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--line)", margin: "18px 0 0" }}>
        {[
          { id: "requests", label: "Join Requests", count: counts.pending },
          { id: "users",    label: "Active Users",  count: userCounts.active },
          { id: "audit",    label: "Audit Log",     count: null },
        ].map(t => (
          <button key={t.id}
                  onClick={() => setTab(t.id)}
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                    padding: "12px 16px",
                    background: "transparent",
                    border: 0,
                    color: tab === t.id ? "var(--ink-1)" : "var(--ink-3)",
                    borderBottom: "2px solid " + (tab === t.id ? "var(--ink-1)" : "transparent"),
                    marginBottom: -1,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}>
            {t.label}
            {t.count != null && t.count > 0 && (
              <span style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                background: tab === t.id ? "var(--ink-1)" : "var(--bg-2)",
                color: tab === t.id ? "var(--bg-0)" : "var(--ink-3)",
                padding: "1px 6px",
                borderRadius: 2,
                fontVariantNumeric: "tabular-nums",
              }}>{t.count}</span>
            )}
          </button>
        ))}
      </div>

      <div style={{ height: 16 }} />

      {tab === "requests" && (
        <RequestsPanel
          requests={visibleRequests}
          allRequests={requests}
          filter={filter}
          setFilter={setFilter}
          counts={counts}
          expanded={expanded}
          setExpanded={setExpanded}
          onDecide={decide}
          onReset={resetDecision}
        />
      )}

      {tab === "users" && <UsersPanel users={ACTIVE_USERS} showToast={showToast} />}

      {tab === "audit" && <AuditLogPanel requests={requests} />}
    </>
  );
}

// ============================================================
// Join Requests panel
// ============================================================
function RequestsPanel({ requests, filter, setFilter, counts, expanded, setExpanded, onDecide, onReset }) {
  return (
    <div className="panel">
      <div className="panel__head">
        <div className="panel__head-title">
          <div className="t-eyebrow">Join Requests</div>
          <div className="t-h2">{requests.length} {requests.length === 1 ? "request" : "requests"}</div>
        </div>
        <Segmented
          value={filter}
          onChange={setFilter}
          options={[
            { value: "pending",  label: `Pending · ${counts.pending}` },
            { value: "approved", label: `Approved · ${counts.approved}` },
            { value: "denied",   label: `Denied · ${counts.denied}` },
            { value: "all",      label: "All" },
          ]}
        />
      </div>
      <div className="panel__body panel__body--flush" style={{ overflowX: "auto" }}>
        <table className="dt">
          <thead>
            <tr>
              <th>Person</th>
              <th>Role</th>
              <th>Properties</th>
              <th>Submitted</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {requests.map(r => (
              <React.Fragment key={r.id}>
                <tr onClick={() => setExpanded(expanded === r.id ? null : r.id)}
                    className={expanded === r.id ? "is-selected" : ""}>
                  <td>
                    <div className="dt__primary">
                      <div style={{
                        width: 32, height: 32, borderRadius: "50%",
                        background: "var(--bg-2)",
                        display: "grid", placeItems: "center",
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        fontWeight: 700,
                        color: "var(--ink-2)",
                        flexShrink: 0,
                      }}>
                        {r.firstName[0]}{r.lastName[0]}
                      </div>
                      <div>
                        <div>{r.firstName} {r.lastName}</div>
                        <div className="dt__sub">{r.email}</div>
                      </div>
                    </div>
                  </td>
                  <td><RoleTag role={r.role} /></td>
                  <td><PropList value={r.properties} /></td>
                  <td className="num">{timeAgo(r.submitted)}</td>
                  <td><StatusTag status={r.status} /></td>
                  <td className="num">
                    <span className="dt__chev">{expanded === r.id ? "▾" : "›"}</span>
                  </td>
                </tr>
                {expanded === r.id && (
                  <tr className="is-selected">
                    <td colSpan={6} style={{ background: "var(--bg-1)", padding: 18 }}>
                      <RequestDetail
                        req={r}
                        onDecide={onDecide}
                        onReset={onReset}
                      />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
        {requests.length === 0 && (
          <div className="empty">
            {filter === "pending"  ? "No pending requests — inbox zero." :
             filter === "approved" ? "No approvals yet." :
             filter === "denied"   ? "No denials yet." : "No requests."}
          </div>
        )}
      </div>
    </div>
  );
}

function RequestDetail({ req, onDecide, onReset }) {
  const D = window.TAP_DATA;
  const propsList = req.properties === "all"
    ? D.PROPERTIES.map(p => p.id)
    : (req.properties || []);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}>
      <dl className="kv">
        <dt>Request ID</dt><dd>{req.id}</dd>
        <dt>Name</dt><dd>{req.firstName} {req.lastName}</dd>
        <dt>Email</dt><dd>{req.email}</dd>
        <dt>Role</dt><dd>{ROLE_LABELS[req.role]}</dd>
        <dt>Submitted</dt><dd>{new Date(req.submitted).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" })}</dd>
        <dt>Status</dt><dd><StatusTag status={req.status} /></dd>
      </dl>

      <div>
        <div className="t-eyebrow" style={{ marginBottom: 8 }}>Properties Requested
          <span style={{ marginLeft: 6, color: "var(--ink-3)", fontWeight: 500 }}>· {propsList.length}</span>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {propsList.map(pid => {
            const p = D.PROPERTIES.find(pp => pp.id === pid);
            if (!p) return null;
            return <Tag key={pid} status="ghost">{p.name}</Tag>;
          })}
        </div>

        {req.note && (
          <>
            <div className="t-eyebrow" style={{ marginTop: 18, marginBottom: 8 }}>Note</div>
            <p style={{ margin: 0, fontFamily: "var(--font-mono)", fontSize: 12,
                        color: "var(--ink-2)", lineHeight: 1.5,
                        padding: "10px 12px",
                        background: "var(--card)",
                        border: "1px solid var(--line)",
                        borderRadius: "var(--r-2)" }}>{req.note}</p>
          </>
        )}
      </div>

      <div style={{ gridColumn: "1 / -1", display: "flex", gap: 8, paddingTop: 4 }}>
        {req.status === "pending" ? (
          <>
            <button className="btn btn--primary" onClick={(e) => { e.stopPropagation(); onDecide(req.id, "approved"); }}>
              ✓ Approve
            </button>
            <button className="btn btn--ghost" onClick={(e) => { e.stopPropagation(); onDecide(req.id, "denied"); }}>
              ✕ Deny
            </button>
            <a className="btn btn--ghost" href={"mailto:" + req.email} onClick={e => e.stopPropagation()}>
              Email applicant
            </a>
          </>
        ) : (
          <>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)",
                            display: "flex", alignItems: "center", padding: "0 4px" }}>
              {req.status === "approved" ? "Approved" : "Denied"} — visible in audit log
            </span>
            <button className="btn btn--ghost" onClick={(e) => { e.stopPropagation(); onReset(req.id); }}>
              Undo
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================
// Active Users panel
// ============================================================
function UsersPanel({ users, showToast }) {
  const [statusOverrides, setStatusOverrides] = useState(() => {
    try { return JSON.parse(localStorage.getItem("tap.userStatus") || "{}"); }
    catch (e) { return {}; }
  });
  function setStatus(id, status) {
    const next = { ...statusOverrides, [id]: status };
    setStatusOverrides(next);
    localStorage.setItem("tap.userStatus", JSON.stringify(next));
    showToast(status === "active" ? "User reactivated" : "User suspended");
  }
  const merged = users.map(u => statusOverrides[u.id] ? { ...u, status: statusOverrides[u.id] } : u);

  return (
    <div className="panel">
      <div className="panel__head">
        <div className="panel__head-title">
          <div className="t-eyebrow">Active Users</div>
          <div className="t-h2">{merged.length} accounts</div>
        </div>
      </div>
      <div className="panel__body panel__body--flush" style={{ overflowX: "auto" }}>
        <table className="dt">
          <thead>
            <tr>
              <th>Person</th>
              <th>Role</th>
              <th>Properties</th>
              <th>Last Active</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {merged.map(u => (
              <tr key={u.id} style={{ cursor: "default" }}>
                <td>
                  <div className="dt__primary">
                    <div style={{
                      width: 32, height: 32, borderRadius: "50%",
                      background: u.role === "admin" ? "var(--ink-1)" : "var(--bg-2)",
                      color:      u.role === "admin" ? "var(--bg-0)" : "var(--ink-2)",
                      display: "grid", placeItems: "center",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      fontWeight: 700,
                      flexShrink: 0,
                    }}>
                      {u.firstName[0]}{u.lastName[0]}
                    </div>
                    <div>
                      <div>{u.firstName} {u.lastName}</div>
                      <div className="dt__sub">{u.email}</div>
                    </div>
                  </div>
                </td>
                <td><RoleTag role={u.role} /></td>
                <td><PropList value={u.properties} /></td>
                <td className="num">{u.lastActive}</td>
                <td><StatusTag status={u.status} /></td>
                <td className="num" style={{ whiteSpace: "nowrap" }}>
                  {u.status === "active" ? (
                    <button className="btn btn--ghost btn--sm" onClick={() => setStatus(u.id, "suspended")}>
                      Suspend
                    </button>
                  ) : (
                    <button className="btn btn--ghost btn--sm" onClick={() => setStatus(u.id, "active")}>
                      Reactivate
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// Audit log panel — derived from decided requests
// ============================================================
function AuditLogPanel({ requests }) {
  const decided = requests
    .filter(r => r.status !== "pending")
    .sort((a, b) => new Date(b.submitted) - new Date(a.submitted));

  if (decided.length === 0) {
    return (
      <div className="panel">
        <div className="panel__body">
          <div className="empty">No decisions logged yet. Approve or deny a request to start the audit trail.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel__head">
        <div className="panel__head-title">
          <div className="t-eyebrow">Audit Log</div>
          <div className="t-h2">{decided.length} {decided.length === 1 ? "entry" : "entries"}</div>
        </div>
      </div>
      <div className="panel__body panel__body--flush">
        <div style={{ padding: 8 }}>
          {decided.map(r => (
            <div key={r.id} style={{
              display: "grid",
              gridTemplateColumns: "100px 1fr auto",
              gap: 14,
              padding: "10px 8px",
              borderBottom: "1px solid var(--line)",
              alignItems: "center",
              fontFamily: "var(--font-mono)",
              fontSize: 12,
            }}>
              <div style={{ color: "var(--ink-4)", fontSize: 10, letterSpacing: "0.14em",
                            textTransform: "uppercase", fontWeight: 700 }}>
                {timeAgo(r.submitted)}
              </div>
              <div style={{ color: "var(--ink-1)" }}>
                <strong style={{ fontWeight: 700 }}>{r.firstName} {r.lastName}</strong>
                <span style={{ color: "var(--ink-3)" }}> · {ROLE_LABELS[r.role]} · {r.status}</span>
                <div className="dt__sub" style={{ marginTop: 2 }}>{r.note}</div>
              </div>
              <StatusTag status={r.status} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AdminScreen });
