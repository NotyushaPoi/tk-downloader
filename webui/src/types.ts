export type ItemStatus =
  | "pending"
  | "resolving"
  | "downloading"
  | "completed"
  | "skipped"
  | "failed";

export type JobStatus = "pending" | "running" | "completed" | "completed_with_errors";

export interface Settings {
  cookie_status: "configured" | "missing";
  cookie_source: "current" | "release" | "missing";
  output_dir: string;
  conflict_policy: "skip";
  version: string;
}

export interface JobItem {
  id: string;
  person_id: string;
  person_index: number;
  person_name: string;
  sequence: number;
  source_text: string;
  target_path: string;
  status: ItemStatus;
  progress: number;
  error: string;
  error_code: "" | "unsupported_work";
  work_id: string;
}

export interface JobCounts {
  pending: number;
  resolving: number;
  downloading: number;
  completed: number;
  skipped: number;
  failed: number;
}

export interface Job {
  id: string;
  status: JobStatus;
  total_people: number;
  total_items: number;
  counts: JobCounts;
  items: JobItem[];
}

export interface DraftPerson {
  id: string;
  name: string;
  links: string[];
  selected: boolean;
}
