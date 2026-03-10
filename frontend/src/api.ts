export type DifficultyLevel = "Level 1" | "Level 2" | "Level 3";
export type Purpose = "practice" | "diagnostic" | "exam";

export interface TaskSpec {
  request_id: string;
  grade: string;
  semester: string;
  course: string;
  unit: string;
  topic: string;
  difficulty_target: DifficultyLevel;
  item_type?: string;
  purpose?: Purpose;
}

export interface FinalProblem {
  question: string;
  options: string[];
  answer: string;
  explanation: string;
}

export interface GenerationResponse {
  status: string;
  message: string;
  final_problem?: FinalProblem | null;
}

const API_BASE = "/api";

export async function generateProblem(task: TaskSpec): Promise<GenerationResponse> {
  const res = await fetch(`${API_BASE}/generate-problem`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(task)
  });
  if (!res.ok) {
    throw new Error("문제 생성 API 호출 실패");
  }
  return res.json();
}

