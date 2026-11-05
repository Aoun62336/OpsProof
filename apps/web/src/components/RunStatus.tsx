import {
  CheckCircle2,
  CircleDashed,
  CircleX,
  Clock3,
  ScanSearch,
} from "lucide-react";

import type {
  RunStatus as Status,
} from "../lib/types";

const STATUS = {
  queued: {
    label: "Queued",
    icon: Clock3,
  },
  running: {
    label: "Running",
    icon: CircleDashed,
  },
  verifying: {
    label: "Verifying",
    icon: ScanSearch,
  },
  succeeded: {
    label: "Succeeded",
    icon: CheckCircle2,
  },
  failed: {
    label: "Failed",
    icon: CircleX,
  },
} as const;

export function RunStatus({
  status,
}: {
  status: Status;
}) {
  const { label, icon: Icon } = STATUS[status];

  return (
    <span className={`run-status run-status--${status}`}>
      <Icon
        aria-hidden="true"
        size={15}
        strokeWidth={2}
      />
      {label}
    </span>
  );
}
