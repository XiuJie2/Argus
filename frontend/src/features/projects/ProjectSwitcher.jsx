import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { api } from "../../api";
import { PlusIcon } from "../../shared/ActionIcons.jsx";

export default function ProjectSwitcher() {
  const location = useLocation();
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const match = location.pathname.match(/^\/projects\/([^/]+)/);
  const currentId = match?.[1] || "";
  useEffect(() => { api.get("/projects/").then((r) => setProjects(r.data)).catch(() => setProjects([])); }, [location.pathname]);
  function change(event) { const id = event.target.value; if (id) navigate(`/projects/${id}/overview`); else navigate("/projects"); }
  return <div className="project-switcher"><select aria-label="切換網站專案" value={currentId} onChange={change}><option value="">選擇網站</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select><button type="button" onClick={() => navigate("/projects/new")} aria-label="新增網站專案" title="新增網站專案"><PlusIcon /><span>新增網站</span></button></div>;
}
