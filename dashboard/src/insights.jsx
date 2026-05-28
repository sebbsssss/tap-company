/* ============================================================
   TAP — Insights / Data Quality panel
   ============================================================ */

function InsightsList({ insights, onJumpProperty }) {
  if (!insights || !insights.length) {
    return <div className="empty">No issues — everything looks healthy.</div>;
  }
  return (
    <div className="insights">
      {insights.map((ins, i) => (
        <div key={i} className={`insight insight--${ins.severity}`}>
          <span className="insight__rail" />
          <div>
            <div className="insight__title">{ins.title}</div>
            <div className="insight__detail">{ins.detail}</div>
          </div>
          <span className="insight__count">{ins.count}</span>
        </div>
      ))}
    </div>
  );
}

function DataQualityList({ issues }) {
  if (!issues || !issues.length) {
    return <div className="empty">No data-quality issues detected.</div>;
  }
  return (
    <div className="insights">
      {issues.map((q, i) => (
        <div key={i} className={`insight insight--${q.severity}`}>
          <span className="insight__rail" />
          <div>
            <div className="insight__title">{q.title}</div>
            <div className="insight__detail">Sourced from CRM · review before month close.</div>
          </div>
          <span className="insight__count">{q.count}</span>
        </div>
      ))}
    </div>
  );
}

Object.assign(window, { InsightsList, DataQualityList });
