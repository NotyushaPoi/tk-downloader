import type { DraftPerson, Job } from "../types";
import { Plus, Trash2, X } from "./Icons";

interface Props {
  people: DraftPerson[];
  job: Job | null;
  outputDir: string;
  locked: boolean;
  onChange: (people: DraftPerson[]) => void;
}

function personStatus(personId: string, job: Job | null) {
  if (!job) return { title: "等待下载", detail: "", tone: "muted" };
  const items = job.items.filter((item) => item.person_id === personId);
  if (!items.length) return { title: "未加入任务", detail: "", tone: "muted" };
  const completed = items.filter((item) => item.status === "completed").length;
  const skipped = items.filter((item) => item.status === "skipped").length;
  const failed = items.filter((item) => item.status === "failed");
  const unsupported = failed.filter((item) => item.error_code === "unsupported_work");
  const active = items.find((item) => item.status === "downloading");
  if (active) {
    return {
      title: `下载中 ${completed + skipped}/${items.length}`,
      detail: `${active.sequence}.mp4 · ${Math.round(active.progress)}%`,
      tone: "active",
      progress: active.progress,
    };
  }
  if (failed.length) {
    if (unsupported.length) {
      return {
        title: `图文作品 ${unsupported.length} · 已拒绝下载`,
        detail: "请在企微中标记该作品",
        tone: "danger",
      };
    }
    const pending = items.filter((item) => ["pending", "resolving"].includes(item.status)).length;
    return {
      title: `失败 ${failed.length}${pending ? ` · 等待 ${pending}` : ""}`,
      detail: failed[0].error,
      tone: "danger",
    };
  }
  if (completed + skipped === items.length) {
    return {
      title: `已完成 ${items.length}/${items.length}`,
      detail: skipped ? `完成 ${completed} · 跳过 ${skipped}` : "全部视频下载完成",
      tone: "success",
    };
  }
  return { title: "等待下载", detail: "", tone: "muted" };
}

export function BatchTable({ people, job, outputDir, locked, onChange }: Props) {
  const updatePerson = (id: string, patch: Partial<DraftPerson>) =>
    onChange(people.map((person) => (person.id === id ? { ...person, ...patch } : person)));

  const removePerson = (id: string) => {
    const next = people.filter((person) => person.id !== id);
    onChange(next.length ? next : [newPerson()]);
  };

  return (
    <div className="table-scroll" aria-label="批量下载录入表">
      <div className="batch-table">
        <div className="batch-header table-grid">
          <input
            aria-label="选择全部同事"
            type="checkbox"
            checked={people.length > 0 && people.every((person) => person.selected)}
            disabled={locked}
            onChange={(event) =>
              onChange(people.map((person) => ({ ...person, selected: event.target.checked })))
            }
          />
          <strong>同事名</strong>
          <strong>视频链接</strong>
          <strong>保存路径</strong>
          <strong>状态</strong>
          <strong>操作</strong>
        </div>
        {people.map((person) => {
          const status = personStatus(person.id, job);
          return (
            <div className={`person-row table-grid ${!person.selected ? "is-unselected" : ""}`} key={person.id}>
              <input
                aria-label={`选择${person.name || "未命名同事"}`}
                type="checkbox"
                checked={person.selected}
                disabled={locked}
                onChange={(event) => updatePerson(person.id, { selected: event.target.checked })}
              />
              <div className="name-cell">
                <input
                  aria-label="同事名"
                  className="name-input"
                  placeholder="输入同事名"
                  value={person.name}
                  disabled={locked}
                  onChange={(event) => updatePerson(person.id, { name: event.target.value })}
                />
              </div>
              <div className="links-cell">
                {person.links.map((link, index) => (
                  <div className="link-input" key={`${person.id}-${index}`}>
                    <span>{index + 1}</span>
                    <input
                      aria-label={`${person.name || "同事"}视频链接${index + 1}`}
                      placeholder="粘贴完整分享文案或链接"
                      value={link}
                      disabled={locked}
                      onChange={(event) => {
                        const links = [...person.links];
                        links[index] = event.target.value;
                        updatePerson(person.id, { links });
                      }}
                    />
                    {person.links.length > 1 && !locked && (
                      <button
                        className="icon-button link-remove"
                        aria-label={`删除视频链接${index + 1}`}
                        onClick={() =>
                          updatePerson(person.id, {
                            links: person.links.filter((_, linkIndex) => linkIndex !== index),
                          })
                        }
                      >
                        <X size={15} />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  className="text-action"
                  disabled={locked}
                  onClick={() => updatePerson(person.id, { links: [...person.links, ""] })}
                >
                  <Plus size={16} /> 添加视频链接
                </button>
              </div>
              <div className="paths-cell" title={outputDir}>
                {person.links.map((_, index) => (
                  <div key={`${person.id}-path-${index}`}>{person.name.trim() || "同事名"}/{index + 1}.mp4</div>
                ))}
              </div>
              <div className={`status-cell status-${status.tone}`}>
                <strong>{status.title}</strong>
                {status.detail && <span>{status.detail}</span>}
                {status.progress !== undefined && (
                  <div className="mini-progress"><i style={{ width: `${status.progress}%` }} /></div>
                )}
              </div>
              <div className="action-cell">
                <button
                  className="icon-button"
                  aria-label={`删除${person.name || "同事"}`}
                  disabled={locked}
                  onClick={() => removePerson(person.id)}
                >
                  <Trash2 size={19} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function newPerson(): DraftPerson {
  return {
    id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
    name: "",
    links: [""],
    selected: true,
  };
}
