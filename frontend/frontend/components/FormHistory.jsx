import Link from "next/link";
import { formatDate, loadText, percent } from "@/lib/format";

// One bar per recent set, oldest on the left. Bar height = share of reps with
// good form; colors use the same cutoffs as the adaptation engine
// (80%+ good, 50-80% form breakdown, under 50% poor).
export default function FormHistory({ sessions, limit = 12 }) {
  const recent = sessions.slice(0, limit).reverse();
  const level = (s) => (s == null ? "none" : s >= 0.8 ? "good" : s >= 0.5 ? "mid" : "poor");

  return (
    <div className="form-history">
      <ol className="bars" aria-label="Good-form share for recent sets, oldest first">
        {recent.map((s) => (
          <li key={s.session_id}>
            <Link
              href={`/sessions/${s.session_id}`}
              title={`${formatDate(s.created_at)}: ${loadText(s.workout?.load || 0, s.workout?.unit || "lb")}, ${s.rep_count} reps, ${percent(s.form_score)} good form`}
            >
              <span className="bar-plot">
                <span className="bar-value">{percent(s.form_score)}</span>
                <span className={`bar ${level(s.form_score)}`} style={{ height: `${Math.max(4, (s.form_score ?? 0) * 100)}%` }} />
              </span>
              <span className="bar-load">{s.workout?.load ? s.workout.load : "BW"}</span>
            </Link>
          </li>
        ))}
      </ol>
      <p className="muted small">
        Share of reps with good form in your last {recent.length === 1 ? "set" : `${recent.length} sets`}, oldest on the
        left, with the weight used (BW = bodyweight). Green is 80% or more.
      </p>
    </div>
  );
}
