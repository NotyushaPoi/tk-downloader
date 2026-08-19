import { useEffect, useRef, useState } from "react";

import { api } from "./api";
import { BatchTable, newPerson } from "./components/BatchTable";
import { FolderOpen, Moon, Plus, SettingsIcon, Sun } from "./components/Icons";
import { SettingsDialog } from "./components/SettingsDialog";
import { TaskPanel } from "./components/TaskPanel";
import type { DraftPerson, Job, JobItem, Settings } from "./types";
import "./styles.css";

const DRAFT_KEY = "wecom-video-downloader-draft-v1";
const JOB_KEY = "wecom-video-downloader-job-v1";
const THEME_KEY = "wecom-video-downloader-theme-v1";

function loadDraft(): DraftPerson[] {
  try {
    const value = JSON.parse(window.localStorage.getItem(DRAFT_KEY) || "null");
    return Array.isArray(value) && value.length ? value : [newPerson()];
  } catch {
    return [newPerson()];
  }
}

function emptySettings(): Settings {
  return { cookie_status: "missing", cookie_source: "missing", output_dir: "", conflict_policy: "skip", version: "" };
}

export default function App() {
  const [people, setPeople] = useState<DraftPerson[]>(loadDraft);
  const [settings, setSettings] = useState<Settings>(emptySettings);
  const [job, setJob] = useState<Job | null>(null);
  const [message, setMessage] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">(() =>
    window.localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark",
  );
  const eventSource = useRef<EventSource | null>(null);

  const active = job?.status === "pending" || job?.status === "running";
  const selected = people.filter((person) => person.selected);
  const videoCount = selected.reduce((total, person) => total + person.links.filter((link) => link.trim()).length, 0);
  const unsupportedItems = job?.items.filter((item) => item.error_code === "unsupported_work") || [];

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => window.localStorage.setItem(DRAFT_KEY, JSON.stringify(people)), [people]);

  useEffect(() => {
    api.settings().then(setSettings).catch((error) => setMessage(error.message));
    const savedJob = window.localStorage.getItem(JOB_KEY);
    if (savedJob) {
      api.job(savedJob).then((value) => {
        setJob(value);
        if (value.status === "pending" || value.status === "running") connectEvents(value.id);
      }).catch(() => window.localStorage.removeItem(JOB_KEY));
    }
    return () => eventSource.current?.close();
  }, []);

  const connectEvents = (jobId: string) => {
    eventSource.current?.close();
    const source = new EventSource(`/api/webui/jobs/${jobId}/events`);
    eventSource.current = source;
    source.addEventListener("job", (event) => {
      const next = JSON.parse((event as MessageEvent).data) as Job;
      setJob(next);
      if (next.status === "completed" || next.status === "completed_with_errors") source.close();
    });
    source.onerror = () => source.close();
  };

  const startJob = async () => {
    setMessage("");
    try {
      const created = await api.createJob(people);
      setJob(created);
      window.localStorage.setItem(JOB_KEY, created.id);
      connectEvents(created.id);
    } catch (error) {
      setMessage((error as Error).message);
    }
  };

  const retry = async (item: JobItem) => {
    if (!job) return;
    try {
      const updated = await api.retry(job.id, item.id);
      setJob(updated);
      connectEvents(job.id);
    } catch (error) {
      setMessage((error as Error).message);
    }
  };

  const clear = () => {
    setPeople([newPerson()]);
    setJob(null);
    setMessage("");
    window.localStorage.removeItem(JOB_KEY);
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="window-dots" aria-hidden="true"><i /><i /><i /></div>
        <h1>企微视频下载</h1>
        <div className="header-actions">
          <span className={`cookie-status ${settings.cookie_status}`}><i />抖音 Cookie {settings.cookie_status === "configured" ? "已导入" : "未配置"}</span>
          <button className="header-button theme-button" aria-label="切换明暗模式" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}</button>
          <button className="header-button" onClick={() => setSettingsOpen(true)}><SettingsIcon size={18} />设置</button>
        </div>
      </header>

      <section className="workspace">
        <div className="directory-bar">
          <span>保存到</span><div title={settings.output_dir}>{settings.output_dir || "正在读取设置…"}</div>
          <button className="secondary-button" onClick={() => setSettingsOpen(true)}><FolderOpen size={18} />更改目录</button>
        </div>
        {message && <div className="inline-alert" role="alert">{message}<button onClick={() => setMessage("")}>×</button></div>}
        {unsupportedItems.length > 0 && (
          <div className="unsupported-alert" role="alert">
            <strong>发现 {unsupportedItems.length} 个图文作品，已拒绝下载</strong>
            {unsupportedItems.map((item) => <span key={item.id}>{item.error}</span>)}
          </div>
        )}

        <BatchTable people={people} job={job} outputDir={settings.output_dir} locked={Boolean(active)} onChange={setPeople} />

        <button className="add-person-button" disabled={active} onClick={() => setPeople([...people, newPerson()])}><Plus size={18} />添加同事</button>

        <div className="action-bar">
          <strong>{selected.length} 位同事 · {videoCount} 个视频</strong>
          <span className="conflict-label">同名文件：跳过⌄</span>
          <button className="secondary-button clear-button" disabled={active} onClick={clear}>清空</button>
          <button className="primary-button start-button" disabled={active || !selected.length || !videoCount} onClick={startJob}>{active ? "下载进行中" : "开始下载"}</button>
        </div>

        <TaskPanel job={job} onRetry={retry} />
      </section>

      <SettingsDialog
        settings={settings}
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaveDirectory={async (path) => { setSettings(await api.updateSettings(path)); setMessage("下载目录已更新"); }}
        onImportCookie={async () => { setSettings(await api.importReleaseCookie()); setMessage("已检查 5.7 Cookie 配置"); }}
        onSaveCookie={async (cookie) => { setSettings(await api.updateCookie(cookie)); setMessage("Cookie 已更新"); }}
      />
    </main>
  );
}
