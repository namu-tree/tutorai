from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class DifficultyLevel(str, Enum):
    LEVEL_1 = "Level 1"
    LEVEL_2 = "Level 2"
    LEVEL_3 = "Level 3"


class Purpose(str, Enum):
    PRACTICE = "practice"
    DIAGNOSTIC = "diagnostic"
    EXAM = "exam"


class AgentDecision(str, Enum):
    APPROVED = "approved"
    REVISE = "revise"
    REJECTED = "rejected"


class StudentProfile(BaseModel):
    target_weakness: List[str] = Field(default_factory=list)
    mastery_estimate: Dict[str, float] = Field(default_factory=dict)


class Constraints(BaseModel):
    latex_required: bool = True
    single_correct_answer: bool = True
    max_revision_rounds: int = 3
    language: str = "ko"


class TaskSpec(BaseModel):
    request_id: str
    grade: str
    semester: str
    course: str
    unit: str
    topic: str
    difficulty_target: DifficultyLevel
    item_type: str = "5지선다"
    purpose: Purpose = Purpose.DIAGNOSTIC
    student_profile: Optional[StudentProfile] = None
    constraints: Constraints = Field(default_factory=Constraints)
    revision_feedback: List[str] = Field(default_factory=list)


class CurriculumReport(BaseModel):
    message_type: str = "curriculum_report"
    request_id: str
    curriculum_fit: str = "pass"
    allowed_concepts: List[str] = Field(default_factory=list)
    forbidden_concepts: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    recommended_item_patterns: List[str] = Field(default_factory=list)
    curriculum_notes: List[str] = Field(default_factory=list)


class ProblemDraft(BaseModel):

    message_type: Literal["problem_draft"] = "problem_draft"
    request_id: str

    draft_version: int = 1
    metadata: Dict[str, str] = Field(default_factory=dict)

    question: str = ""
    options: List[str] = Field(default_factory=list)

    intended_answer: str = ""

    intended_solution_path: List[str] = Field(default_factory=list)

    target_concepts: List[str] = Field(default_factory=list)

    prerequisites: List[str] = Field(default_factory=list)

    difficulty_rationale: str = ""

    uniqueness_assumption: str = ""

class UniquenessCheck(BaseModel):
    is_unique: bool
    reason: str


class SolverReport(BaseModel):
    message_type: Literal["solver_report"] = "solver_report"
    request_id: str
    draft_version: int
    solve_status: Literal["pass", "fail"]
    derived_answer: str
    solution_summary: List[str]
    alternative_paths: List[str]
    uniqueness_check: UniquenessCheck
    ambiguity_flags: List[str]
    mathematical_issues: List[str]


class CriticReport(BaseModel):
    message_type: Literal["critic_report"] = "critic_report"
    request_id: str
    draft_version: int
    review_decision: Literal["pass", "revise", "reject"]
    fatal_issues: List[str]
    major_issues: List[str]
    minor_issues: List[str]
    clarity_score: float
    curriculum_fit_score: float
    difficulty_fit_score: float
    distractor_quality_score: float
    revision_requests: List[str]


class TargetedWeaknessCoverage(BaseModel):
    node: str
    coverage: float


class StudentAlignmentReport(BaseModel):
    message_type: Literal["student_alignment_report"] = "student_alignment_report"
    request_id: str
    draft_version: int
    alignment_score: float
    diagnostic_value: float
    targeted_weakness_coverage: List[TargetedWeaknessCoverage]
    expected_error_patterns: List[str]
    comments: List[str]

class RevisionRequest(BaseModel):
    message_type: Literal["revision_request"] = "revision_request"
    request_id: str
    target_agent: str = "ProblemDesigner"
    draft_version: int
    revision_version: int
    must_fix: List[str]
    should_fix: List[str]
    keep_unchanged: List[str]


class FinalProblemPackage(BaseModel):
    message_type: Literal["final_problem_package"] = "final_problem_package"
    request_id: str
    problem_id: str
    metadata: Dict[str, str]
    question: str
    options: List[str]
    answer: str
    explanation: str
    concept_ontology: List[Dict[str, str]] | List[str]
    validation_report: Dict[str, str]
    revision_history: List[Dict[str, str]]


class OrchestratorDecision(BaseModel):
    status: AgentDecision
    reason: str
    revision_request: Optional[RevisionRequest] = None


class GenerationResponse(BaseModel):
    status: AgentDecision
    request_id: str
    curriculum: Optional[CurriculumReport] = None
    final_problem: Optional[FinalProblemPackage] = None
    last_solver_report: Optional[SolverReport] = None
    last_critic_report: Optional[CriticReport] = None
    last_student_report: Optional[StudentAlignmentReport] = None
    message: str


# -------- Realtime session / A2A messaging models --------


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StudentEventType(str, Enum):
    SESSION_STARTED = "session_started"
    ATTEMPT_STARTED = "attempt_started"
    ANSWER_SELECTED = "answer_selected"
    WORK_STEP_ADDED = "work_step_added"
    HINT_REQUESTED = "hint_requested"
    SUBMITTED = "submitted"
    TIME_TICK = "time_tick"


class SessionUpdateType(str, Enum):
    STATUS = "status"
    PROBLEM_PUBLISHED = "problem_published"
    HINT = "hint"
    FEEDBACK = "feedback"
    CONCEPT_STATUS = "concept_status"
    NEXT_PROBLEM = "next_problem"
    ERROR = "error"


class ConceptLight(str, Enum):
    """개념 신호등: 초록=양호, 노랑=힌트 사용/주의, 빨강=오답/미숙"""
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ConceptStatusUpdate(BaseModel):
    concept: str
    status: ConceptLight


class StudentEvent(BaseModel):
    event_id: str
    session_id: str
    event_type: StudentEventType
    created_at: str = Field(default_factory=utc_now_iso)
    payload: Dict[str, Any] = Field(default_factory=dict)


class SessionUpdate(BaseModel):
    update_id: str
    session_id: str
    update_type: SessionUpdateType
    created_at: str = Field(default_factory=utc_now_iso)
    data: Dict[str, Any] = Field(default_factory=dict)


class SessionState(BaseModel):
    session_id: str
    task_spec: Optional[TaskSpec] = None
    last_problem: Optional[FinalProblemPackage] = None
    last_message: str = ""
    concept_status: Dict[str, str] = Field(default_factory=dict)  # 개념명 -> green|yellow|red
    suggested_difficulty: Optional[str] = None  # 다음 문항 난이도 제안 (Level 1 등)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class AgentCommand(BaseModel):
    command_id: str
    session_id: str
    agent_name: str
    created_at: str = Field(default_factory=utc_now_iso)
    payload: Dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    command_id: str
    session_id: str
    agent_name: str
    created_at: str = Field(default_factory=utc_now_iso)
    ok: bool = True
    result: Dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class SessionCreateRequest(BaseModel):
    task_spec: TaskSpec


class SessionCreateResponse(BaseModel):
    session_id: str