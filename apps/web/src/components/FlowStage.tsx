import type { ReactNode } from "react";

type FlowStageProps = {
  title: string;
  statusLabel: string;
  hint?: string;
  guideId?: string;
  active?: boolean;
  done?: boolean;
  right?: ReactNode;
  children: ReactNode;
};

export function FlowStage({
  title,
  statusLabel,
  hint,
  guideId,
  active = false,
  done = false,
  right,
  children
}: FlowStageProps) {
  return (
    <div
      className={`card flow-stage${active ? " stage-active" : ""}${done ? " stage-done" : ""}`}
      data-guide-id={guideId}
    >
      <div className="hd">
        <div style={{ display: "grid", gap: 4, minWidth: 0 }}>
          <h2>{title}</h2>
          {hint ? <div className="muted flow-hint">{hint}</div> : null}
        </div>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <span className="pill">{statusLabel}</span>
          {right}
        </div>
      </div>
      <div className="bd">{children}</div>
    </div>
  );
}
