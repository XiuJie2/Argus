import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useNavigate, useOutletContext, useParams, useSearchParams } from "react-router-dom";

import { api } from "../../api";
import { PlusIcon } from "../../shared/ActionIcons.jsx";
import { ChartIcon, ClockIcon, GearIcon, HomeIcon, RulesIcon, SpiderIcon } from "../../shared/LineIcons.jsx";

const PROJECT_NAV = [
  { key: "overview", label: "總覽", icon: HomeIcon },
  { key: "scans", label: "網站掃描", icon: SpiderIcon },
  { key: "issues", label: "問題分析", icon: RulesIcon },
  { key: "reports", label: "歷史報告", icon: ClockIcon },
  { key: "settings", label: "專案設定", icon: GearIcon },
];

const SCAN_STATUS_LABELS = {
  queued: "等待中",
  crawling: "爬取中",
  scanning: "分析中",
  agent_testing: "Agent 測試中",
  completed: "已完成",
  failed: "失敗",
  cancelled: "已取消",
};

function scanStatusLabel(status) {
  return SCAN_STATUS_LABELS[status] || "尚未掃描";
}

function propertyCoversHostname(siteUrl, hostname) {
  if (siteUrl.startsWith("sc-domain:")) {
    const domain = siteUrl.slice("sc-domain:".length).toLowerCase().replace(/\.$/, "");
    return hostname === domain || hostname.endsWith(`.${domain}`);
  }
  try {
    return new URL(siteUrl).hostname.toLowerCase().replace(/\.$/, "") === hostname;
  } catch {
    return false;
  }
}

function verificationMethodLabel(method) {
  return {
    dns_txt: "DNS TXT",
    meta_tag: "HTML meta 標籤",
    html_file: "驗證檔案",
    gsc: "Google Search Console",
  }[method] || "網站所有權驗證";
}

function ProjectWorkspaceLayout() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api.get(`/projects/${projectId}/`)
      .then(({ data }) => { if (active) setProject(data); })
      .catch(() => { if (active) setError("找不到這個網站專案，或你沒有存取權限。"); });
    return () => { active = false; };
  }, [projectId]);

  if (error) return <section className="project-state panel"><p className="error-text">{error}</p><button className="secondary-button" onClick={() => navigate("/projects")}>返回所有網站</button></section>;
  if (!project) return <section className="project-state panel"><p className="hint-text">正在載入網站專案…</p></section>;

  return (
    <div className="project-workspace">
      <aside className="project-sidebar" aria-label="網站專案功能">
        <div className="project-sidebar__identity"><strong>{project.name}</strong><span>{project.hostname}</span></div>
        <nav className="project-sidebar__nav">
          {PROJECT_NAV.map(({ key, label, icon: Icon }) => (
            <NavLink key={key} to={`/projects/${project.id}/${key}`} className={({ isActive }) => `project-sidebar__link${isActive ? " is-active" : ""}`}>
              <Icon aria-hidden="true" /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="project-sidebar__footer"><a className="project-sidebar__domain" href={project.canonical_url} target="_blank" rel="noreferrer">開啟網站 ↗</a></div>
      </aside>
      <section className="project-content"><Outlet context={{ project, setProject }} /></section>
    </div>
  );
}

function ProjectListPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get("/projects/").then((r) => setProjects(r.data)).catch(() => setError("無法載入網站專案。")); }, []);
  return <div className="project-index page-stack">
    <header className="project-page-header"><div><p className="eyebrow">網站工作區</p><h1>所有網站</h1><p>選擇一個網站，持續追蹤掃描結果與修復進度。</p></div><button className="primary-button" onClick={() => navigate("/projects/new")}><PlusIcon />新增網站</button></header>
    {error && <p className="error-text">{error}</p>}
    {projects && projects.length === 0 && <section className="project-empty panel"><ChartIcon /><h2>建立第一個網站專案</h2><p>新增網站不會開始掃描，也不會扣除點數。</p><button className="primary-button" onClick={() => navigate("/projects/new")}>新增網站</button></section>}
    <div className="project-card-grid">{projects?.map((project) => <button key={project.id} className="project-card" onClick={() => navigate(`/projects/${project.id}/overview`)}><div className="project-card__top"><span className="project-card__favicon">{project.hostname.slice(0, 1).toUpperCase()}</span><span className={`status-badge status-${project.latest_scan?.status || "idle"}`}>{scanStatusLabel(project.latest_scan?.status)}</span></div><h2>{project.name}</h2><p>{project.hostname}</p><div className="project-card__metrics"><span><strong>{project.scan_count}</strong> 次掃描</span><span><strong>{project.latest_scan?.overall_score ?? "—"}</strong> 最新分數</span></div></button>)}</div>
  </div>;
}

function NewProjectPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", canonical_url: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  async function submit(event) { event.preventDefault(); setSaving(true); setError(""); try { const { data } = await api.post("/projects/", form); navigate(`/projects/${data.id}/overview`, { replace: true }); } catch (err) { const data = err.response?.data; setError(data?.canonical_url?.[0] || data?.non_field_errors?.[0] || "無法建立網站專案。"); } finally { setSaving(false); } }
  return <div className="project-form-page"><button className="text-button" onClick={() => navigate("/projects")}>← 返回所有網站</button><form className="project-form panel" onSubmit={submit}><p className="eyebrow">新增網站</p><h1>建立網站專案</h1><p>專案是掃描、問題與報告的長期工作空間；此步驟不會扣點。</p><label>網站名稱<input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="例如：品牌官網" required /></label><label>網站網址<input className="input" value={form.canonical_url} onChange={(e) => setForm({ ...form, canonical_url: e.target.value })} placeholder="https://example.com" required /></label>{error && <p className="error-text">{error}</p>}<button className="primary-button" disabled={saving}>{saving ? "建立中…" : "建立網站專案"}</button></form></div>;
}

function useProjectData(endpoint) {
  const { project } = useOutletContext();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { let active = true; api.get(endpoint, { params: { project_id: project.id } }).then((r) => { if (active) setData(r.data); }).catch(() => { if (active) setError("資料載入失敗，請稍後再試。"); }); return () => { active = false; }; }, [endpoint, project.id]);
  return { project, data, error };
}

function ProjectOverviewPage() {
  const navigate = useNavigate();
  const { project, data, error } = useProjectData("/dashboard/");
  if (error) return <p className="error-text">{error}</p>;
  if (!data) return <p className="hint-text">正在整理網站總覽…</p>;
  const severities = data.severity_totals || {};
  const hasScans = data.recent_scans.length > 0;
  return <div className="page-stack"><header className="project-page-header project-page-header--overview"><div><p className="eyebrow">網站總覽</p><h1>{project.name}</h1><p className="project-page-header__url">{project.hostname}</p></div>{hasScans && <button className="primary-button" onClick={() => navigate(`/projects/${project.id}/scans`)}>開始新掃描</button>}</header>{hasScans ? <><section className="project-summary-grid"><article className="project-score panel"><span>最新健康基準</span><strong>{data.recent_scans[0]?.overall_score ?? "—"}</strong><small>Argus 綜合診斷分數</small></article><article className="project-stat panel"><span>掃描次數</span><strong>{data.total_scans}</strong><small>{data.completed_scans} 次完成</small></article><article className="project-stat panel"><span>高風險問題</span><strong>{(severities.critical || 0) + (severities.high || 0)}</strong><small>需優先處理</small></article></section><section className="project-activity panel"><div className="section-heading"><div><p className="eyebrow">最近活動</p><h2>掃描快照</h2></div><button className="secondary-button" onClick={() => navigate(`/projects/${project.id}/reports`)}>查看全部</button></div><div className="project-scan-list">{data.recent_scans.map((scan) => <button key={scan.id} onClick={() => navigate(`/scans/${scan.id}`)}><span>{new Date(scan.created_at).toLocaleString("zh-TW")}</span><strong>{scan.overall_score ?? "—"} 分</strong><span className={`status-badge status-${scan.status}`}>{scanStatusLabel(scan.status)}</span></button>)}</div></section></> : <section className="project-first-run"><div className="project-first-run__icon" aria-hidden="true"><ChartIcon /></div><div className="project-first-run__copy"><p className="eyebrow">尚無掃描紀錄</p><h2>開始第一次網站診斷</h2><p>建立基準報告後，這裡會顯示分數、問題與歷次變化。</p></div><button className="primary-button" onClick={() => navigate(`/projects/${project.id}/scans`)}>設定第一次掃描</button></section>}</div>;
}

function ProjectScansPage() {
  const { project } = useOutletContext();
  const navigate = useNavigate();
  const [scans, setScans] = useState(null);
  const [form, setForm] = useState({ max_pages: 10, authorization_confirmed: false });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  useEffect(() => {
    api.get("/scans/", { params: { project_id: project.id, include_history: true } })
      .then((r) => setScans(r.data.results || r.data))
      .catch(() => setError("無法載入掃描紀錄。"));
  }, [project.id]);
  async function submit(event) { event.preventDefault(); setSubmitting(true); setError(""); try { const { data } = await api.post("/scans/", { project_id: project.id, url: project.canonical_url, authorization_confirmed: form.authorization_confirmed, scan_mode: "passive", categories: ["seo", "aeo", "geo", "ux", "security"], max_depth: 3, max_pages: Number(form.max_pages), respect_robots: true }); navigate(`/scans/${data.id}`); } catch (err) { const data = err.response?.data; setError(data?.coin?.[0] || data?.url?.[0] || data?.authorization_confirmed?.[0] || data?.detail || "無法建立掃描。"); } finally { setSubmitting(false); } }
  return <div className="page-stack"><header className="project-page-header"><div><p className="eyebrow">網站掃描</p><h1>建立新的診斷快照</h1><p>掃描目標固定為目前網站；送出前會顯示並依既有規則預扣點數。</p></div></header><div className="project-two-column"><form className="project-scan-form panel" onSubmit={submit}><h2>掃描設定</h2><label>目標網址<input className="input" value={project.canonical_url} readOnly /></label><label>最多頁數<input className="input" type="number" min="1" max="50" value={form.max_pages} onChange={(e) => setForm({ ...form, max_pages: e.target.value })} /></label><label className="project-check"><input type="checkbox" checked={form.authorization_confirmed} onChange={(e) => setForm({ ...form, authorization_confirmed: e.target.checked })} />我確認擁有此網站或已取得書面掃描授權。</label>{error && <p className="error-text">{error}</p>}<button className="primary-button" disabled={submitting}>{submitting ? "建立中…" : "開始五維掃描"}</button></form><section className="panel"><h2>掃描紀錄</h2><div className="project-scan-list">{scans?.map((scan) => <button key={scan.id} onClick={() => navigate(`/scans/${scan.id}`)}><span>{new Date(scan.created_at).toLocaleString("zh-TW")}</span><strong>{scan.overall_score ?? "—"} 分</strong><span className={`status-badge status-${scan.status}`}>{scan.status}</span></button>)}{scans?.length === 0 && <p className="hint-text">目前沒有掃描紀錄。</p>}</div></section></div></div>;
}

function ProjectIssuesPage() {
  const { data, error } = useProjectData("/findings/");
  const [severity, setSeverity] = useState("all");
  const filtered = useMemo(() => {
    const findings = data?.results || data || [];
    return severity === "all" ? findings : findings.filter((f) => f.severity === severity);
  }, [data, severity]);
  return <div className="page-stack"><header className="project-page-header"><div><p className="eyebrow">問題分析</p><h1>有證據的診斷問題</h1><p>依風險檢視 Argus 在這個網站歷次掃描中找到的問題。</p></div><select className="input project-filter" value={severity} onChange={(e) => setSeverity(e.target.value)}><option value="all">所有風險</option><option value="critical">嚴重</option><option value="high">高</option><option value="medium">中</option><option value="low">低</option></select></header>{error && <p className="error-text">{error}</p>}<div className="project-issue-list">{filtered.map((finding) => <article className="project-issue panel" key={finding.id}><span className={`severity severity-${finding.severity}`}>{finding.severity}</span><div><p>{finding.category.toUpperCase()} · {finding.rule_id || "一般規則"}</p><h2>{finding.title}</h2><p>{finding.description}</p><details><summary>查看證據與修復建議</summary><pre>{finding.evidence || "此項目沒有文字證據。"}</pre><p>{finding.remediation}</p></details></div></article>)}{data && !filtered.length && <section className="project-empty panel"><RulesIcon /><h2>目前沒有符合條件的問題</h2></section>}</div></div>;
}

function ProjectReportsPage() {
  const { project } = useOutletContext();
  const navigate = useNavigate();
  const [scans, setScans] = useState(null);
  useEffect(() => { api.get("/scans/", { params: { project_id: project.id, include_history: true } }).then((r) => setScans(r.data.results || r.data)); }, [project.id]);
  return <div className="page-stack"><header className="project-page-header"><div><p className="eyebrow">歷史報告</p><h1>每次掃描都是一份快照</h1><p>比較不同時間的分數，並開啟完整互動報告或下載文件。</p></div></header><section className="panel project-report-table"><div className="project-report-row is-heading"><span>掃描時間</span><span>狀態</span><span>分數</span><span>操作</span></div>{scans?.map((scan) => <div className="project-report-row" key={scan.id}><span>{new Date(scan.created_at).toLocaleString("zh-TW")}</span><span className={`status-badge status-${scan.status}`}>{scan.status}</span><strong>{scan.overall_score ?? "—"}</strong><button className="secondary-button" onClick={() => navigate(`/scans/${scan.id}`)}>開啟報告</button></div>)}{scans?.length === 0 && <p className="hint-text">完成第一次掃描後，報告會出現在這裡。</p>}</section></div>;
}

function ProjectSettingsPage() {
  const { project, setProject } = useOutletContext();
  const navigate = useNavigate();
  const [name, setName] = useState(project.name);
  const [message, setMessage] = useState("");
  async function save(event) { event.preventDefault(); const { data } = await api.patch(`/projects/${project.id}/`, { name }); setProject(data); setMessage("專案名稱已更新。"); }
  async function archive() { if (!window.confirm("封存後將從網站切換器隱藏，但掃描與報告仍會保留。確定封存？")) return; await api.post(`/projects/${project.id}/archive/`); navigate("/projects", { replace: true }); }
  return <div className="page-stack"><header className="project-page-header"><div><p className="eyebrow">專案設定</p><h1>管理網站專案</h1><p>管理網站名稱、所有權驗證與外部資料連線。</p></div></header><form className="project-form panel" onSubmit={save}><label>專案名稱<input className="input" value={name} onChange={(e) => setName(e.target.value)} /></label><label>標準網址<input className="input" value={project.canonical_url} readOnly /></label>{message && <p className="success-text">{message}</p>}<button className="primary-button">儲存變更</button></form><ProjectOwnershipPanel project={project} /><section className="project-danger panel"><div><h2>封存網站</h2><p>網站會從工作區移除，但歷史掃描、報告和計費紀錄不會刪除。</p></div><button className="danger-button" onClick={archive}>封存網站</button></section></div>;
}

function ProjectOwnershipPanel({ project }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [status, setStatus] = useState(null);
  const [selectedProperty, setSelectedProperty] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadStatus = useCallback(async () => {
    setError("");
    try {
      const { data } = await api.get("/integrations/gsc/status/", { params: { project_id: project.id } });
      setStatus(data);
      setSelectedProperty(data.selected_property || "");
    } catch (err) {
      setError(err.response?.data?.detail || "無法載入網站驗證狀態。");
    }
  }, [project.id]);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  useEffect(() => {
    const result = searchParams.get("gsc");
    if (!result) return;
    setMessage(result === "connected" ? "Google Search Console 已連線，驗證狀態已更新。" : "Google Search Console 連線失敗。");
    setError(result === "error" ? searchParams.get("message") || "請重新連線後再試。" : "");
    const next = new URLSearchParams(searchParams);
    next.delete("gsc");
    next.delete("message");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const matchingProperties = (status?.properties || []).filter((item) => propertyCoversHostname(item.site_url, project.hostname));
  const verification = status?.domain_verification;

  async function connect() {
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post("/integrations/gsc/authorize/", { project_id: project.id });
      window.location.assign(data.authorization_url);
    } catch (err) {
      setError(err.response?.data?.detail || "無法開始 Google 授權流程。");
      setBusy(false);
    }
  }

  async function chooseProperty(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const { data } = await api.post("/integrations/gsc/property/", {
        project_id: project.id,
        site_url: selectedProperty,
      });
      await loadStatus();
      setMessage(data.domain_verified ? "已用 Search Console 完成網域驗證。" : "資源已綁定，但目前權限不足以證明網站所有權。" );
    } catch (err) {
      setError(err.response?.data?.detail || "無法綁定這個 Search Console 資源。");
    } finally {
      setBusy(false);
    }
  }

  return <section className="project-ownership panel" aria-labelledby="project-ownership-title">
    <div className="project-ownership__heading"><div><p className="eyebrow">網站所有權</p><h2 id="project-ownership-title">網域驗證與 Search Console</h2><p>通過驗證後才能使用主動式安全測試；Search Console 只會讀取搜尋成效資料。</p></div>{verification?.is_effectively_verified ? <span className="project-verification-status is-verified">已驗證</span> : <span className="project-verification-status">未驗證</span>}</div>
    {status === null && !error && <p className="hint-text">正在確認網域驗證狀態…</p>}
    {verification?.is_effectively_verified && <dl className="project-verification-details"><div><dt>涵蓋網域</dt><dd>{verification.domain}</dd></div><div><dt>驗證方式</dt><dd>{verificationMethodLabel(verification.method)}</dd></div><div><dt>有效期限</dt><dd>{verification.expires_at ? new Date(verification.expires_at).toLocaleDateString("zh-TW") : "持續有效"}</dd></div></dl>}
    {status && !verification?.is_effectively_verified && <p className="project-ownership__notice">目前尚未找到涵蓋 <strong>{project.hostname}</strong> 的有效所有權證明。</p>}
    {status?.connected ? <form className="project-property-form" onSubmit={chooseProperty}><label>Search Console 資源<select className="input" value={selectedProperty} onChange={(event) => setSelectedProperty(event.target.value)} required><option value="">選擇涵蓋目前網站的資源</option>{matchingProperties.map((item) => <option key={item.site_url} value={item.site_url}>{item.site_url} · {item.permission_level}</option>)}</select></label><button className="secondary-button" disabled={busy || !selectedProperty}>{busy ? "更新中…" : "套用資源"}</button><p>只有 Google 回報為 <code>siteOwner</code> 的網域資源或網站根目錄資源，才能作為所有權證明。</p></form> : status && <div className="project-ownership__actions"><button className="primary-button" onClick={connect} disabled={busy}>{busy ? "準備授權中…" : "連接 Google Search Console"}</button><button className="secondary-button" onClick={() => navigate(`/domains?domain=${encodeURIComponent(project.hostname)}&return=${encodeURIComponent(`/projects/${project.id}/settings`)}`)}>改用 DNS／HTML 驗證</button></div>}
    {message && <p className="success-text">{message}</p>}
    {error && <p className="error-text">{error}</p>}
  </section>;
}

export { NewProjectPage, ProjectIssuesPage, ProjectListPage, ProjectOverviewPage, ProjectReportsPage, ProjectScansPage, ProjectSettingsPage, ProjectWorkspaceLayout };
