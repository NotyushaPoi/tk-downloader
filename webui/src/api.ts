import type { DraftPerson, Job, Settings } from "./types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `请求失败：HTTP ${response.status}`);
  }
  return response.json();
}

export const api = {
  settings: () => request<Settings>("/api/webui/settings"),
  updateSettings: (outputDir: string) =>
    request<Settings>("/api/webui/settings", {
      method: "PUT",
      body: JSON.stringify({ output_dir: outputDir }),
    }),
  importReleaseCookie: () =>
    request<Settings>("/api/webui/cookie/import-release", { method: "POST" }),
  updateCookie: (cookie: string) =>
    request<Settings>("/api/webui/cookie", {
      method: "PUT",
      body: JSON.stringify({ cookie }),
    }),
  createJob: (people: DraftPerson[]) =>
    request<Job>("/api/webui/jobs", {
      method: "POST",
      body: JSON.stringify({
        people: people
          .filter((person) => person.selected)
          .map(({ id, name, links }) => ({ client_id: id, name, links })),
      }),
    }),
  job: (jobId: string) => request<Job>(`/api/webui/jobs/${jobId}`),
  retry: (jobId: string, itemId: string) =>
    request<Job>(`/api/webui/jobs/${jobId}/items/${itemId}/retry`, { method: "POST" }),
};
