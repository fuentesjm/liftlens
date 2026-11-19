import Link from "next/link";
import { DECISION_LABEL, formatNumber, recordHref } from "@/lib/format";

// The next set, written big: "95 lb × 11" or "Bodyweight × 12".
export default function Prescription({ decision, title = "Next squat set", showButton = true }) {
  const { next } = decision;
  return (
    <section className="prescription" aria-labelledby="next-set">
      <h2 id="next-set">{title}</h2>
      <p className="prescription-figure">
        {next.load > 0 ? (
          <>
            {formatNumber(next.load)}
            <span className="unit">{next.unit}</span>
          </>
        ) : (
          "Bodyweight"
        )}
        <span className="times">×</span>
        {next.target_reps}
      </p>
      <p>
        <span className={`decision ${decision.decision}`}>{DECISION_LABEL[decision.decision]}</span>{" "}
        {decision.reason}
      </p>
      {showButton && (
        <p>
          <Link className="button" href={recordHref(next)}>
            Record this set
          </Link>
        </p>
      )}
    </section>
  );
}
