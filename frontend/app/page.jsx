"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import FormHistory from "@/components/FormHistory";
import MiniTrace, { sampleSet } from "@/components/MiniTrace";
import Notice from "@/components/Notice";
import Prescription from "@/components/Prescription";
import { getHealth, getNextWorkout, getPlan, getSession, getSessions } from "@/lib/api";
import { formatDate } from "@/lib/format";

export default function Today() {
  const [state, setState] = useState({ loading: true });

  useEffect(() => {
    Promise.all([getHealth(), getNextWorkout(), getPlan(), getSessions()])
      .then(async ([health, next, plan, sessions]) => {
        const last = sessions.length ? await getSession(sessions[0].session_id) : null;
        setState({ health, next, plan, sessions, last });
      })
      .catch((error) => setState({ error }));
  }, []);

  if (state.loading) return <p className="muted">Loading…</p>;
  if (state.error) return <Notice kind="error" title="LiftLens server not reachable">{state.error.message}</Notice>;

  const { health, next, plan, sessions, last } = state;

  return (
    <div className="stack">
      {!health.model_ready && (
        <Notice title="Pose model missing">
          Videos can't be analyzed until the model is downloaded: python scripts/download_model.py
        </Notice>
      )}
      {next && last ? <ReturningHero next={next} last={last} /> : <FirstVisitHero hasPlan={!!plan} />}

      {sessions.length > 0 ? (
        <div className="split">
          <section className="section" aria-labelledby="form-h">
            <h2 id="form-h">Form over time</h2>
            <FormHistory sessions={sessions} />
            <Link href="/history">All {sessions.length} {sessions.length === 1 ? "set" : "sets"}</Link>
          </section>
          <WeekSummary plan={plan} />
        </div>
      ) : (
        <div className="split">
          <HowItWorks />
          <WeekSummary plan={plan} />
        </div>
      )}
    </div>
  );
}

function ReturningHero({ next, last }) {
  const r = last.report;
  const verdict =
    r.reps_passed === r.rep_count ? `All ${r.rep_count} reps passed` : `${r.reps_passed} of ${r.rep_count} reps passed`;
  return (
    <section className="hero">
      <Prescription decision={next} />
      <div className="hero-side">
        <h2 className="hero-side-title">Last set: {verdict.toLowerCase()}</h2>
        <p className="muted small">{formatDate(last.created_at)}</p>
        <MiniTrace
          trace={r.trace}
          reps={r.reps}
          depth={r.thresholds.max_bottom_knee_angle}
          label={`Knee angle during your last set. ${verdict}.`}
        />
        <Link href={`/sessions/${last.session_id}`}>See every rep</Link>
      </div>
    </section>
  );
}

function FirstVisitHero({ hasPlan }) {
  const sample = sampleSet();
  return (
    <section className="hero">
      <div className="section">
        <h1 className="hero-title">Film a set. See every rep.</h1>
        <p>
          Upload a side-view video of your squats. LiftLens checks the depth and torso angle of each rep, then sets the
          weight and reps for your next session.
        </p>
        <p className="actions">
          <Link className="button" href="/record">
            Record your first set
          </Link>
          {!hasPlan && (
            <Link className="button quiet" href="/plan">
              Create a plan
            </Link>
          )}
        </p>
      </div>
      <div className="hero-side">
        <h2 className="hero-side-title">What you'll get back</h2>
        <MiniTrace
          trace={sample.trace}
          reps={sample.reps}
          depth={100}
          label="Example result: three reps, the second one too shallow."
        />
        <p className="muted small">
          An example set. Each dip is a rep: green reps reached the dashed depth line, the red one stopped short.
        </p>
      </div>
    </section>
  );
}

const STEPS = [
  ["Plan your week", "Pick your goal, equipment, and training days. Squats are always in the plan."],
  ["Film a set from the side", "Prop your phone at hip height with your whole body in frame."],
  ["See every rep", "Each rep is checked for depth and forward lean, with notes on what to fix."],
  ["Your next set adjusts", "Good form adds reps or weight. Form breakdown holds or backs off."],
];

function HowItWorks() {
  return (
    <section className="section" aria-labelledby="how-h">
      <h2 id="how-h">How it works</h2>
      <ol className="steps">
        {STEPS.map(([title, text]) => (
          <li key={title}>
            <strong>{title}</strong>
            <span className="muted">{text}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function WeekSummary({ plan }) {
  return (
    <section className="section" aria-labelledby="week-h">
      <h2 id="week-h">Your week</h2>
      {plan ? (
        <>
          <ul className="week-strip">
            {plan.plan.days.map((d) => (
              <li key={d.day}>
                <strong>Day {d.day}</strong>
                <span className="muted small">
                  {d.focus}, {d.exercises.length} exercises
                </span>
                {d.exercises.some((e) => e.form_check) && <span className="tag">Video check</span>}
              </li>
            ))}
          </ul>
          <Link href="/plan">Open your plan</Link>
        </>
      ) : (
        <>
          <p className="muted">No plan yet. Tell LiftLens your goal and equipment to get a weekly plan.</p>
          <p>
            <Link className="button quiet" href="/plan">
              Create a plan
            </Link>
          </p>
        </>
      )}
    </section>
  );
}
