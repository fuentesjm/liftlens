"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Notice from "@/components/Notice";
import Prescription from "@/components/Prescription";
import { getHealth, getNextWorkout, getPlan, getSessions } from "@/lib/api";
import { formatDate, loadText, percent } from "@/lib/format";

export default function Today() {
  const [state, setState] = useState({ loading: true });

  useEffect(() => {
    Promise.all([getHealth(), getNextWorkout(), getPlan(), getSessions()])
      .then(([health, next, plan, sessions]) => setState({ health, next, plan, sessions }))
      .catch((error) => setState({ error }));
  }, []);

  if (state.loading) return <p className="muted">Loading…</p>;
  if (state.error) return <Notice kind="error" title="LiftLens server not reachable">{state.error.message}</Notice>;

  const { health, next, plan, sessions } = state;
  const firstDay = plan?.plan.days[0];

  return (
    <div className="stack">
      {!health.model_ready && (
        <Notice title="Pose model missing">
          Videos can't be analyzed until the model is downloaded: python scripts/download_model.py
        </Notice>
      )}

      {next ? (
        <Prescription decision={next} />
      ) : (
        <section className="section">
          <h1>Record your first set</h1>
          <p>
            Film one set of squats from the side and upload it. LiftLens checks every rep and sets the
            weight and reps for your next session.
          </p>
          <p>
            <Link className="button" href="/record">
              Record a set
            </Link>
          </p>
        </section>
      )}

      <div className="split">
        <section className="section" aria-labelledby="recent">
          <h2 id="recent">Recent sets</h2>
          {sessions.length === 0 ? (
            <p className="muted">Sets you upload will show up here.</p>
          ) : (
            <ul className="recent">
              {sessions.slice(0, 4).map((s) => (
                <li key={s.session_id}>
                  <span>
                    <Link href={`/sessions/${s.session_id}`}>
                      <strong>
                        {loadText(s.workout?.load || 0, s.workout?.unit || "lb")} for {s.rep_count} reps
                      </strong>
                    </Link>
                    <br />
                    <span className="muted small">{formatDate(s.created_at)}</span>
                  </span>
                  <span className="metric">
                    <strong>{percent(s.form_score)}</strong> <span className="muted small">good form</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {sessions.length > 4 && <Link href="/history">See all {sessions.length} sets</Link>}
        </section>

        <section className="section" aria-labelledby="week">
          <h2 id="week">This week</h2>
          {plan ? (
            <>
              <p>
                {plan.plan.days.length} training days. Day 1: {firstDay.focus}, starting with{" "}
                {firstDay.exercises[0].name.toLowerCase()}.
              </p>
              <Link href="/plan">Open your plan</Link>
            </>
          ) : (
            <>
              <p className="muted">No plan yet. Tell LiftLens your goal and equipment to get a weekly plan.</p>
              <Link className="button quiet" href="/plan">
                Create a plan
              </Link>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
