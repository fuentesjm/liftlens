"use client";

import { useEffect, useState } from "react";
import Notice from "@/components/Notice";
import { createPlan, getPlan } from "@/lib/api";
import { formatDate } from "@/lib/format";

const OPTIONS = {
  goal: [
    ["strength", "Get stronger"],
    ["muscle", "Build muscle"],
    ["general_fitness", "General fitness"],
  ],
  experience: [
    ["beginner", "New to lifting"],
    ["intermediate", "Lifting 1+ year"],
  ],
  equipment: [
    ["bodyweight", "No equipment"],
    ["dumbbells", "Dumbbells"],
    ["full_gym", "Full gym"],
  ],
  days_per_week: [2, 3, 4, 5].map((d) => [d, `${d} days`]),
};

function Choice({ name, legend, value, onChange }) {
  return (
    <fieldset className="choices">
      <legend>{legend}</legend>
      {OPTIONS[name].map(([v, label]) => (
        <label key={v}>
          <input type="radio" name={name} value={v} checked={value === v} onChange={() => onChange(v)} />
          <span>{label}</span>
        </label>
      ))}
    </fieldset>
  );
}

export default function PlanPage() {
  const [plan, setPlan] = useState(undefined); // undefined = loading, null = none yet
  const [profile, setProfile] = useState({
    goal: "general_fitness",
    experience: "beginner",
    days_per_week: 3,
    equipment: "bodyweight",
    session_minutes: 45,
  });
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getPlan()
      .then((p) => {
        setPlan(p);
        if (p) setProfile(p.profile);
      })
      .catch((e) => setError(e.message));
  }, []);

  const set = (key) => (v) => setProfile((p) => ({ ...p, [key]: v }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setPlan(await createPlan(profile));
      setEditing(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (plan === undefined && !error) return <p className="muted">Loading…</p>;
  const showForm = !plan || editing;

  return (
    <div className="stack">
      {showForm && (
        <form className="form-grid" onSubmit={submit}>
          <div className="section">
            <h1>{plan ? "Change your plan" : "Get a weekly plan"}</h1>
            <p>Answer five questions. Squats are always included so you can film them for form review.</p>
          </div>
          <Choice name="goal" legend="Goal" value={profile.goal} onChange={set("goal")} />
          <Choice name="experience" legend="Experience" value={profile.experience} onChange={set("experience")} />
          <Choice name="equipment" legend="Equipment" value={profile.equipment} onChange={set("equipment")} />
          <Choice name="days_per_week" legend="Training days per week" value={profile.days_per_week} onChange={set("days_per_week")} />
          <label className="field" style={{ maxWidth: 240 }}>
            <span>Minutes per session</span>
            <input
              type="number"
              min="20"
              max="90"
              step="5"
              value={profile.session_minutes}
              onChange={(e) => set("session_minutes")(Number(e.target.value))}
            />
          </label>
          {error && <Notice kind="error">{error}</Notice>}
          <p style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button className="button" type="submit" disabled={busy}>
              {busy ? "Creating plan…" : "Create plan"}
            </button>
            {plan && (
              <button className="button quiet" type="button" onClick={() => setEditing(false)} disabled={busy}>
                Keep current plan
              </button>
            )}
          </p>
        </form>
      )}

      {plan && !editing && <PlanView plan={plan} onEdit={() => setEditing(true)} />}
    </div>
  );
}

function PlanView({ plan, onEdit }) {
  const { profile } = plan;
  const label = (key) => OPTIONS[key].find(([v]) => v === profile[key])?.[1];
  return (
    <>
      <section className="section">
        <h1>Your week</h1>
        <p>
          {label("goal")}, {label("experience").toLowerCase()}, {label("equipment").toLowerCase()},{" "}
          {profile.days_per_week} days of about {profile.session_minutes} minutes.
        </p>
        <p>
          <button className="button quiet" type="button" onClick={onEdit}>
            Change plan
          </button>
        </p>
      </section>

      <div className="week">
        {plan.plan.days.map((d) => (
          <section key={d.day} className="day" aria-labelledby={`day-${d.day}`}>
            <h3 id={`day-${d.day}`}>Day {d.day}</h3>
            <p className="muted small">{d.focus}</p>
            <ul className="exercises">
              {d.exercises.map((e, i) => (
                <li key={i}>
                  <strong>{e.name}</strong>
                  {e.form_check && (
                    <span className="tag" title="Film this one for per-rep form feedback">
                      Video check
                    </span>
                  )}
                  <br />
                  <span className="dose">
                    {e.sets} sets of {e.reps}, rest {e.rest_seconds >= 120 ? `${e.rest_seconds / 60} min` : `${e.rest_seconds} s`}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <section className="section">
        <h2>Why this plan</h2>
        <p>{plan.plan.rationale}</p>
        <p className="muted small">
          {plan.source === "llm"
            ? `Written by AI (${plan.model.replace("gemini:", "Gemini ")}) and checked against LiftLens safety limits: allowed exercises only, 1–5 sets, 5–20 reps, and a daily set cap.`
            : `Standard plan (AI planner unavailable: ${plan.fallback_reason}).`}{" "}
          Created {formatDate(plan.created_at)}. Not medical advice.
        </p>
      </section>
    </>
  );
}
