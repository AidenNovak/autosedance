import type { ReactNode } from "react";

type FocusGuideProps = {
  id: string;
  activeId: string | null;
  children: ReactNode;
};

export function FocusGuide({ id, activeId, children }: FocusGuideProps) {
  const active = id === activeId;
  return (
    <div data-guide-id={id} data-guide-active={active ? "1" : "0"} className={active ? "guide-target-active" : undefined}>
      {children}
    </div>
  );
}
