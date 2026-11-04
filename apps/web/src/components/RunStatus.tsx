import {
  CircleCheck,
  CircleDashed,
  CircleX,
  LoaderCircle,
  ScanSearch,
} from "lucide-react";

import type { RunStatus as RunStatusType } from "../lib/types";

const STATUS = {
  queued: {
    label: "Queued",
    icon: CircleDashed,
  },
  running: {
    label: "Running",
    icon: LoaderCircle,
  },
  verifying: {
    label: "Verifying",
    icon: ScanSearch,
  },
  succeeded: {
    label: "Succeeded",
    icon: CircleCheck,
  },
  failed: {
    label: "Failed",
    icon: CircleX,
  },
};

export function RunStatus({
  status,
}: {
  status: RunStatusType;
}) {
  const item = STATUS[status];
  const Icon = item.icon;

  return (
    <span className={`run-status run-status--${status}`}>
      <Icon size={14} aria-hidden="true" />
      {item.label}
    </span>
  );
}
