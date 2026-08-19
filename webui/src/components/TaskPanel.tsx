import { useState } from "react";

import type { Job, JobItem, ItemStatus } from "../types";
import { ChevronDown } from "./Icons";

const LABELS: Record<ItemStatus, string> = {
  pending: "等待",
  resolving: "解析中",
  downloading: "下载中",
  completed: "已完成",
  skipped: "跳过",
  failed: "失败",
};

interface Props {
  job: Job | null;
  onRetry: (item: JobItem) => void;
}

export function TaskPanel({ job, onRetry }: Props) {
  const [expanded, setExpanded] = useState(Boolean(job));
  const counts = job?.counts;
  return (
    <section className={`task-panel ${expanded && job ? "is-expanded" : ""}`}>
      <button className="task-panel-header" onClick={() => setExpanded((value) => !value)}>
        <ChevronDown className={expanded ? "rotated" : ""} size={17} />
        <strong>下载任务</strong>
        <span>等待 {counts ? counts.pending + counts.resolving : 0}</span>
        <b>·</b>
        <span>下载中 {counts?.downloading || 0}</span>
        <b>·</b>
        <span>已完成 {counts ? counts.completed + counts.skipped : 0}</span>
        <b>·</b>
        <span>失败 {counts?.failed || 0}</span>
      </button>
      {expanded && job && (
        <div className="task-list">
          <div className="task-list-head"><span>文件</span><span>状态</span><span>进度</span><span /></div>
          {job.items.map((item) => (
            <div className={`task-item ${item.status === "failed" ? "has-error" : ""}`} key={item.id}>
              <span>{item.person_name}/{item.sequence}.mp4</span>
              <span className={`task-status status-${item.status}`}>
                {item.error_code === "unsupported_work" ? "已拒绝" : LABELS[item.status]}
              </span>
              <div className="task-progress">
                <span title={item.error || undefined}>{item.status === "completed" || item.status === "skipped" ? "100%" : item.status === "downloading" ? `${Math.round(item.progress)}%` : item.error || "排队中"}</span>
                <i><b style={{ width: `${item.progress}%` }} /></i>
              </div>
              {item.status === "failed" && item.error_code !== "unsupported_work" ? (
                <button className="retry-button" onClick={() => onRetry(item)}>重试</button>
              ) : item.error_code === "unsupported_work" ? <span className="no-download">无需下载</span> : <span />}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
