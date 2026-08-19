from typing import Literal

from pydantic import BaseModel, Field


ItemStatus = Literal[
    "pending",
    "resolving",
    "downloading",
    "completed",
    "skipped",
    "failed",
]
JobStatus = Literal["pending", "running", "completed", "completed_with_errors"]


class PersonInput(BaseModel):
    client_id: str = ""
    name: str
    links: list[str]


class CreateJobRequest(BaseModel):
    people: list[PersonInput] = Field(min_length=1)


class UpdateSettingsRequest(BaseModel):
    output_dir: str


class UpdateCookieRequest(BaseModel):
    cookie: str


class JobItemView(BaseModel):
    id: str
    person_id: str
    person_index: int
    person_name: str
    sequence: int
    source_text: str
    target_path: str
    status: ItemStatus
    progress: float = 0
    error: str = ""
    error_code: Literal["", "unsupported_work"] = ""
    work_id: str = ""


class JobCounts(BaseModel):
    pending: int = 0
    resolving: int = 0
    downloading: int = 0
    completed: int = 0
    skipped: int = 0
    failed: int = 0


class JobView(BaseModel):
    id: str
    status: JobStatus
    total_people: int
    total_items: int
    counts: JobCounts
    items: list[JobItemView]


class SettingsView(BaseModel):
    cookie_status: Literal["configured", "missing"]
    cookie_source: Literal["current", "release", "missing"]
    output_dir: str
    conflict_policy: Literal["skip"] = "skip"
    version: str
