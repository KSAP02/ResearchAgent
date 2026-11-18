import type { RunStatus } from "../api/client";

const LABEL: Record<RunStatus, string> = {
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  interrupted: "Paused",
};

/** Status is always shown as text + a dot; colour is never the only signal. */
export default function StatusPill({ status }: { status: RunStatus }) {
  return (
    <span className={`pill pill-${status}`}>
      <span className="pill-dot" aria-hidden="true" />
      {LABEL[status] ?? status}
    </span>
  );
}
