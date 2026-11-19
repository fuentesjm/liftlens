"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import KneeTrace from "@/components/KneeTrace";
import Notice from "@/components/Notice";
import Prescription from "@/components/Prescription";
import { getSession, getSessions } from "@/lib/api";
import { ERROR_LABEL, formatDate, loadText } from "@/lib/format";
import { videoFor } from "@/lib/videoStore";

export default function SessionPage() {
  const { id } = useParams();
  const [state, setState] = useState({ loading: true });
  const [time, setTime] = useState(null);
  const video = useRef(null);

  useEffect(() => {
    Promise.all([getSession(id), getSessions()])
      .then(([session, all]) => setState({ session, isLatest: all[0]?.session_id === id }))
      .catch((error) => setState({ error }));
  }, [id]);

  if (state.loading) return <p className="muted">Loading…</p>;
  if (state.error)
    return (
      <Notice kind="error" title={state.error.status === 404 ? "Set not found" : "Couldn't load this set"}>
        {state.error.status === 404 ? "This set may have been deleted. Go to History to see your sets." : state.error.message}
      </Notice>
    );

  const { session, isLatest } = state;
  const { report, workout = {} } = session;
  const videoUrl = videoFor(id);
  const fb = session.feedback; // sessions saved before feedback existed don't have it
  const decision = session.next_workout;

  function seek(t) {
    if (!video.current) return;
    video.current.currentTime = Math.max(0, t - 0.3);
    video.current.play();
  }

  const verdict =
    report.rep_count === 0
      ? "No reps found"
      : report.reps_passed === report.rep_count
        ? `All ${report.rep_count} reps passed`
        : `${report.reps_passed} of ${report.rep_count} reps passed`;

  return (
    <div className="stack">
      <section className="section">
        <p className="muted">
          <Link href="/history">All sets</Link>
        </p>
        <h1 className="verdict-title">{verdict}</h1>
        <p className="muted">
          Squat, {loadText(workout.load || 0, workout.unit || "lb")}
          {workout.target_reps ? `, target ${workout.target_reps} reps` : ""}
          {workout.rpe ? `, RPE ${workout.rpe}` : ""}. Recorded {formatDate(session.created_at)}.
        </p>
      </section>

      {report.warnings.map((w) => (
        <Notice key={w}>{w}</Notice>
      ))}

      <section className="section" aria-labelledby="trace-h">
        <h2 id="trace-h">Every rep</h2>
        <KneeTrace report={report} currentTime={videoUrl ? time : null} onSeek={videoUrl ? seek : undefined} />
        <div className={videoUrl ? "replay" : "section"}>
          {videoUrl ? (
            <video
              ref={video}
              className="video"
              src={videoUrl}
              controls
              muted
              playsInline
              onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
            />
          ) : (
            <p className="muted small">
              The video isn't kept after analysis, so replay is only available right after you upload.
            </p>
          )}
          {report.reps.length > 0 && (
            <ul className="reps">
              {report.reps.map((r) => {
                const shallow = r.errors.includes("shallow_depth");
                const lean = r.errors.includes("forward_lean");
                return (
                  <li key={r.number} className={`rep${r.passed ? "" : " fail"}`}>
                    <span className="rep-number">Rep {r.number}</span>
                    <span className={`metric${shallow ? " bad" : ""}`}>
                      <strong>{Math.round(r.bottom_knee_angle)}°</strong>{" "}
                      <span className="muted small">knee at the bottom</span>
                    </span>
                    <span className={`metric${lean ? " bad" : ""}`}>
                      <strong>{Math.round(r.torso_lean_at_bottom)}°</strong>{" "}
                      <span className="muted small">torso lean</span>
                    </span>
                    <span className="rep-verdict">
                      {r.passed ? "Passed" : r.errors.map((e) => ERROR_LABEL[e] || e).join(", ")}
                      {videoUrl && (
                        <>
                          {" "}
                          <button type="button" onClick={() => seek(r.start_time)}>
                            Replay
                          </button>
                        </>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <p className="muted small">
          A rep passes when the knee bends to {report.thresholds.max_bottom_knee_angle}° or less (thighs about
          parallel) and the torso leans no more than {report.thresholds.max_torso_lean}° from upright.
        </p>
      </section>

      <div className="split">
        <section className="section" aria-labelledby="coach-h">
          <h2 id="coach-h">Coach notes</h2>
          {fb ? (
            <>
              <p>{fb.summary}</p>
              {fb.tips.length > 0 && (
                <ul className="checklist">
                  {fb.tips.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              )}
              <p>{fb.next_session}</p>
              <p className="muted small">
                {fb.source === "llm"
                  ? `Written by AI (${fb.model.replace("gemini:", "Gemini ")}) from the measurements above.`
                  : `Standard feedback text (AI writer unavailable: ${fb.fallback_reason}).`}
              </p>
            </>
          ) : report.cues.length ? (
            <ul className="checklist">
              {report.cues.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          ) : (
            <p>Every rep met the depth and torso checks. Keep the same controlled pace.</p>
          )}
        </section>

        <section className="section">
          {decision ? (
            <Prescription
              decision={decision}
              title={isLatest ? "Your next set" : "Next set, as decided after this one"}
              showButton={isLatest}
            />
          ) : (
            <>
              <h2>Next set</h2>
              <p className="muted">Today shows what to do next.</p>
              <Link href="/">Go to Today</Link>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
