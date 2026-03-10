import { useState } from "react";
import { generateProblem, type GenerationResponse, type DifficultyLevel, type Purpose } from "./api";
import { renderLatexToHtml } from "./latex";
import "./styles.css";

function randomRequestId() {
  return "req_" + Math.random().toString(36).slice(2, 10);
}

const difficulties: DifficultyLevel[] = ["Level 1", "Level 2", "Level 3"];

const purposes: { value: Purpose; label: string }[] = [
  { value: "practice", label: "연습" },
  { value: "diagnostic", label: "진단" },
  { value: "exam", label: "시험" }
];

function App() {
  const [grade, setGrade] = useState("중1");
  const [unit, setUnit] = useState("일차방정식");
  const [topic, setTopic] = useState("기본 개념");
  const [difficulty, setDifficulty] = useState<DifficultyLevel>("Level 1");
  const [purpose, setPurpose] = useState<Purpose>("practice");

  const [loading, setLoading] = useState(false);
  const [problem, setProblem] = useState<GenerationResponse | null>(null);
  const [answerInput, setAnswerInput] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setFeedback(null);
    setProblem(null);
    setAnswerInput("");
    try {
      const resp = await generateProblem({
        request_id: randomRequestId(),
        grade,
        semester: "1학기",
        course: "수학",
        unit,
        topic,
        difficulty_target: difficulty,
        item_type: "5지선다",
        purpose
      });
      setProblem(resp);
    } catch (e: any) {
      alert(e.message ?? "문제 생성 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleCheck = () => {
    if (!problem?.final_problem) return;
    const correct = problem.final_problem.answer.trim() === answerInput.trim();
    const base = correct ? "정답입니다! 🎉\n\n" : "아惜어요, 다시 한 번 생각해 볼까요?\n\n";
    setFeedback(base + (problem.final_problem.explanation || ""));
  };

  return (
    <div className="page">
      <header className="header">
        <h1>TutorAI 수학 튜터 (베타)</h1>
        <p>학년/단원 선택 → 문제 생성 → 답 입력 → 피드백 보기</p>
      </header>

      <main className="layout">
        <section className="card">
          <h2>학습 조건</h2>
          <div className="form-grid">
            <label>
              <span>학년</span>
              <input value={grade} onChange={e => setGrade(e.target.value)} placeholder="예: 중1" />
            </label>
            <label>
              <span>단원</span>
              <input value={unit} onChange={e => setUnit(e.target.value)} placeholder="예: 일차방정식" />
            </label>
            <label>
              <span>주제</span>
              <input value={topic} onChange={e => setTopic(e.target.value)} placeholder="예: 기본 개념" />
            </label>
            <label>
              <span>난이도</span>
              <select value={difficulty} onChange={e => setDifficulty(e.target.value as DifficultyLevel)}>
                {difficulties.map(d => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>용도</span>
              <select value={purpose} onChange={e => setPurpose(e.target.value as Purpose)}>
                {purposes.map(p => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <button className="primary-btn" onClick={handleGenerate} disabled={loading}>
            {loading ? "문제 생성 중..." : "문제 생성하기"}
          </button>
        </section>

        {problem?.final_problem && (
          <section className="card">
            <h2>문제</h2>
            <p
              className="question"
              dangerouslySetInnerHTML={{ __html: renderLatexToHtml(problem.final_problem.question) }}
            />
            <ol className="options" type="A">
              {problem.final_problem.options.map((opt, idx) => (
                <li key={idx} dangerouslySetInnerHTML={{ __html: renderLatexToHtml(opt) }} />
              ))}
            </ol>

            <div className="answer-row">
              <input
                value={answerInput}
                onChange={e => setAnswerInput(e.target.value)}
                placeholder="정답 (예: 1, 2, 3, 4, 5 또는 A,B,C...)"
              />
              <button onClick={handleCheck}>정답 확인</button>
            </div>

            {feedback && (
              <div className="feedback">
                {feedback.split("\n").map((line, i) => (
                  <p key={i} dangerouslySetInnerHTML={{ __html: renderLatexToHtml(line) }} />
                ))}
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;

