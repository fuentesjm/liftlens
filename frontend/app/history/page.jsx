"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Notice from "@/components/Notice";
import { getSessions } from "@/lib/api";
import { formatDate, loadText, percent } from "@/lib/format";

export default function HistoryPage() {
  const [sessions, setSessions] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getSessions().then(setSessions).catch((e) => setError(e.message));
  }, []);

  if (error) return <Notice kind="error">{error}</Notice>;
  if (!sessions) return <p className="muted">Loading…</p>;

  return (
    <div className="stack">
      <section className="section">
        <h1>History</h1>
        <p>Every set you've uploaded, newest first.</p>
      </section>

      {sessions.length === 0 ? (
        <section className="section">
          <p>No sets yet.</p>
          <p>
            <Link className="button" href="/record">
              Record a set
            </Link>
          </p>
        </section>
      ) : (
        <div className="table-wrap">
          <table className="sessions">
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Weight</th>
                <th scope="col">Reps</th>
                <th scope="col">Good form</th>
                <th scope="col">RPE</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.session_id}>
                  <td>
                    <Link href={`/sessions/${s.session_id}`}>{formatDate(s.created_at)}</Link>
                  </td>
                  <td>{loadText(s.workout?.load || 0, s.workout?.unit || "lb")}</td>
                  <td>
                    {s.rep_count}
                    {s.workout?.target_reps ? <span className="muted"> of {s.workout.target_reps}</span> : null}
                  </td>
                  <td className="score">{percent(s.form_score)}</td>
                  <td>{s.workout?.rpe ?? <span className="muted">–</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
