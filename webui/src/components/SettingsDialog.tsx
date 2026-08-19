import { useEffect, useState } from "react";

import type { Settings } from "../types";
import { X } from "./Icons";

interface Props {
  settings: Settings;
  open: boolean;
  onClose: () => void;
  onSaveDirectory: (path: string) => Promise<void>;
  onImportCookie: () => Promise<void>;
  onSaveCookie: (cookie: string) => Promise<void>;
}

export function SettingsDialog({
  settings,
  open,
  onClose,
  onSaveDirectory,
  onImportCookie,
  onSaveCookie,
}: Props) {
  const [path, setPath] = useState(settings.output_dir);
  const [cookie, setCookie] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => setPath(settings.output_dir), [settings.output_dir]);
  if (!open) return null;

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="settings-dialog" role="dialog" aria-modal="true" aria-label="设置" onMouseDown={(event) => event.stopPropagation()}>
        <header><h2>设置</h2><button className="icon-button" aria-label="关闭设置" onClick={onClose}><X size={19} /></button></header>
        <label className="form-field">
          <span>下载目录</span>
          <input value={path} onChange={(event) => setPath(event.target.value)} />
        </label>
        <button className="secondary-button align-start" disabled={busy} onClick={() => run(() => onSaveDirectory(path))}>保存下载目录</button>
        <div className="dialog-divider" />
        <div className="cookie-heading">
          <div><strong>抖音 Cookie</strong><span>当前状态：{settings.cookie_status === "configured" ? "已配置" : "未配置"}</span></div>
          <button className="secondary-button" disabled={busy} onClick={() => run(onImportCookie)}>从 5.7 配置导入</button>
        </div>
        <label className="form-field">
          <span>手动更新</span>
          <textarea value={cookie} placeholder="粘贴 Cookie；保存后输入内容不会再次显示" onChange={(event) => setCookie(event.target.value)} />
        </label>
        <footer>
          <button className="secondary-button" onClick={onClose}>关闭</button>
          <button className="primary-button" disabled={busy || !cookie.trim()} onClick={() => run(async () => { await onSaveCookie(cookie); setCookie(""); })}>保存 Cookie</button>
        </footer>
      </section>
    </div>
  );
}
