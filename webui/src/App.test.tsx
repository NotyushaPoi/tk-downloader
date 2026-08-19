import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const settings = {
  cookie_status: "configured",
  cookie_source: "release",
  output_dir: "/Users/test/Downloads/视频下载",
  conflict_policy: "skip",
  version: "5.8.beta",
};

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.dataset.theme = "dark";
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => settings,
    })));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("defaults to dark mode and persists theme changes", async () => {
    render(<App />);
    await screen.findByText("抖音 Cookie 已导入");
    expect(document.documentElement.dataset.theme).toBe("dark");
    await userEvent.click(screen.getByRole("button", { name: "切换明暗模式" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem("wecom-video-downloader-theme-v1")).toBe("light");
  });

  it("adds links, removes them, and keeps consecutive labels", async () => {
    render(<App />);
    await screen.findByText("抖音 Cookie 已导入");
    await userEvent.type(screen.getByLabelText("同事名"), "张三");
    await userEvent.click(screen.getByRole("button", { name: "添加视频链接" }));
    expect(screen.getByLabelText("张三视频链接2")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "删除视频链接1" }));
    expect(screen.getByLabelText("张三视频链接1")).toBeInTheDocument();
    expect(screen.queryByLabelText("张三视频链接2")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(window.localStorage.getItem("wecom-video-downloader-draft-v1")).toContain("张三"),
    );
  });

  it("restores a saved draft", async () => {
    window.localStorage.setItem("wecom-video-downloader-draft-v1", JSON.stringify([
      { id: "saved", name: "李四", links: ["https://v.douyin.com/example/"], selected: true },
    ]));
    render(<App />);
    await screen.findByText("抖音 Cookie 已导入");
    expect(screen.getByDisplayValue("李四")).toBeInTheDocument();
    expect(screen.getByDisplayValue("https://v.douyin.com/example/")).toBeInTheDocument();
  });

  it("clears the current draft", async () => {
    render(<App />);
    await screen.findByText("抖音 Cookie 已导入");
    fireEvent.change(screen.getByLabelText("同事名"), { target: { value: "王五" } });
    await userEvent.click(screen.getByRole("button", { name: "清空" }));
    expect(screen.getByLabelText("同事名")).toHaveValue("");
  });

  it("prominently identifies rejected photo links", async () => {
    window.localStorage.setItem("wecom-video-downloader-job-v1", "photo-job");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => ({
      ok: true,
      json: async () => String(input).includes("/jobs/photo-job") ? {
        id: "photo-job",
        status: "completed_with_errors",
        total_people: 1,
        total_items: 1,
        counts: { pending: 0, resolving: 0, downloading: 0, completed: 0, skipped: 0, failed: 1 },
        items: [{
          id: "photo-item",
          person_id: "person-1",
          person_index: 0,
          person_name: "余俊廷",
          sequence: 2,
          source_text: "https://www.douyin.com/note/7674903698081926436",
          target_path: "/tmp/余俊廷/2.mp4",
          status: "failed",
          progress: 0,
          error: "余俊廷 · 链接 2：检测到图文作品，已拒绝下载（https://www.douyin.com/note/7674903698081926436）",
          error_code: "unsupported_work",
          work_id: "7674903698081926436",
        }],
      } : settings,
    })));

    render(<App />);

    expect(await screen.findByText("发现 1 个图文作品，已拒绝下载")).toBeInTheDocument();
    expect(screen.getByText(/余俊廷 · 链接 2.*7674903698081926436/)).toBeInTheDocument();
  });
});
