import katex from "katex";
import "katex/dist/katex.min.css";

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * 문자열 안의 LaTeX을 HTML로 렌더링합니다.
 * - $...$ 인라인 수식
 * - \(...\) 인라인 수식
 */
export function renderLatexToHtml(text: string): string {
  if (!text || typeof text !== "string") return "";

  let out = "";

  // \( ... \) 먼저 처리 (백슬래시 괄호형)
  const parts = text.split(/(\\\([\s\S]*?\\\))/g);
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    if (part.startsWith("\\(") && part.endsWith("\\)")) {
      const latex = part.slice(2, -2).trim();
      try {
        out += katex.renderToString(latex, { throwOnError: false, displayMode: false });
      } catch {
        out += escapeHtml(part);
      }
    } else {
      // 이 조각 안에서 $...$ 처리
      const byDollar = part.split(/(\$[^$]*\$)/g);
      for (let j = 0; j < byDollar.length; j++) {
        const seg = byDollar[j];
        if (seg.startsWith("$") && seg.endsWith("$") && seg.length > 1) {
          const latex = seg.slice(1, -1).trim();
          try {
            out += katex.renderToString(latex, { throwOnError: false, displayMode: false });
          } catch {
            out += escapeHtml(seg);
          }
        } else {
          out += escapeHtml(seg);
        }
      }
    }
  }

  return out;
}
