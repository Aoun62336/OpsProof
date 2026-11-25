import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  approveKubernetesRecovery,
  getKubernetesRecoveries,
  getKubernetesWorkloads,
  proposeKubernetesRecovery,
  type KubernetesObservation,
  type KubernetesRecovery,
} from "../lib/api";
import { KubernetesPage } from "./KubernetesPage";

vi.mock("../lib/api", async (original) => ({
  ...(await original<typeof import("../lib/api")>()),
  getKubernetesWorkloads: vi.fn(),
  getKubernetesRecoveries: vi.fn(),
  proposeKubernetesRecovery: vi.fn(),
  approveKubernetesRecovery: vi.fn(),
}));

function observation(): KubernetesObservation {
  return {
    name: "demo-worker",
    observed_at: new Date(Date.now() - 1000).toISOString(),
    resource: {
      metadata: {
        name: "demo-worker",
        namespace: "opsproof-demo",
        uid: "observed-worker-uid",
        resourceVersion: "12345",
      },
      spec: {
        replicas: 1,
        template: {
          spec: {
            containers: [
              {
                image: "opsproof-demo:observed-image",
                resources: {
                  requests: { cpu: "25m", memory: "72Mi" },
                  limits: { cpu: "350m", memory: "256Mi" },
                },
              },
            ],
          },
        },
      },
      status: { readyReplicas: 1 },
    },
    telemetry: {
      ready: true,
      queued: 0,
      sample_time: (Date.now() - 1000) / 1000,
    },
  };
}

function recovery(
  changes: Partial<KubernetesRecovery> = {},
): KubernetesRecovery {
  return {
    id: "recorded-recovery-id",
    status: "pending_approval",
    target_uid: "observed-worker-uid",
    target_image: "opsproof-demo:observed-image",
    error: null,
    expires_at: new Date(Date.now() + 120_000).toISOString(),
    created_at: new Date().toISOString(),
    ...changes,
  };
}

function mount(view: "Workloads" | "Deployments" | "Capacity" | "Runbooks") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <KubernetesPage view={view} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getKubernetesWorkloads).mockResolvedValue({
    enabled: true,
    observations: [observation()],
  });
  vi.mocked(getKubernetesRecoveries).mockResolvedValue([]);
  vi.mocked(proposeKubernetesRecovery).mockResolvedValue(recovery());
  vi.mocked(approveKubernetesRecovery).mockResolvedValue(
    recovery({ status: "approved" }),
  );
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe("operational Kubernetes cards", () => {
  it.each(["Workloads", "Deployments", "Capacity", "Runbooks"] as const)(
    "renders real observations for %s",
    async (view) => {
      mount(view);
      expect(
        await screen.findByRole("heading", {
          name: "demo-worker",
        }),
      ).toBeVisible();
      expect(screen.getByRole("heading", { name: view })).toBeVisible();
      expect(screen.getByText("Recent observation")).toBeVisible();
      expect(approveKubernetesRecovery).not.toHaveBeenCalled();
    },
  );
  it("uses configured request/limit ratios without claiming measured utilization", async () => {
    mount("Capacity");
    const cpu = await screen.findByRole("progressbar", {
      name: "Configured CPU request relative to limit",
    });
    expect(Number(cpu.getAttribute("value"))).toBeCloseTo(100 / 14);
    expect(
      screen.getByRole("progressbar", {
        name: "Configured Memory request relative to limit",
      }),
    ).toHaveAttribute("value", "28.125");
    expect(
      screen.getByText(/Measured CPU and memory consumption are unavailable/),
    ).toBeVisible();
  });
  it("exposes the actual deployment identity", async () => {
    mount("Deployments");
    expect(
      await screen.findByText("opsproof-demo:observed-image"),
    ).toBeVisible();
    fireEvent.click(
      screen.getByText("Workload identity and observation details"),
    );
    expect(screen.getByText("observed-worker-uid")).toBeVisible();
    expect(screen.getByText("12345")).toBeVisible();
  });
  it.each([Date.now() - 16_000, Date.now() + 60_000, NaN])(
    "does not claim health from an invalid observation clock",
    async (stamp) => {
      const value = observation();
      value.observed_at = Number.isFinite(stamp)
        ? new Date(stamp).toISOString()
        : "invalid";
      vi.mocked(getKubernetesWorkloads).mockResolvedValue({
        enabled: true,
        observations: [value],
      });
      mount("Workloads");
      expect(await screen.findByText("Current state unknown")).toBeVisible();
      expect(screen.queryByText("Recent observation")).not.toBeInTheDocument();
      expect(screen.getByText("Health unknown")).toBeVisible();
    },
  );
  it("marks old metrics unknown even when Kubernetes observations are fresh", async () => {
    const value = observation();
    value.telemetry.sample_time = (Date.now() - 31_000) / 1000;
    vi.mocked(getKubernetesWorkloads).mockResolvedValue({
      enabled: true,
      observations: [value],
    });
    mount("Capacity");
    const label = await screen.findByText("Dependencies", {
      selector: ".kube-metric__label",
    });
    expect(
      within(label.closest(".panel") as HTMLElement).getByText("Unknown"),
    ).toBeVisible();
  });
  it("distinguishes disabled, empty and failed observations", async () => {
    vi.mocked(getKubernetesWorkloads).mockResolvedValue({
      enabled: false,
      observations: [],
    });
    const mounted = mount("Runbooks");
    expect(await screen.findByText(/observation is disabled/)).toBeVisible();
    expect(
      screen.queryByLabelText("Incident fingerprint"),
    ).not.toBeInTheDocument();
    mounted.unmount();
    vi.mocked(getKubernetesWorkloads).mockResolvedValue({
      enabled: true,
      observations: [],
    });
    const empty = mount("Workloads");
    expect(
      await screen.findByText("Waiting for the first independent observation."),
    ).toBeVisible();
    empty.unmount();
    vi.mocked(getKubernetesWorkloads).mockRejectedValue(new Error("offline"));
    mount("Workloads");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Workload observations are unavailable.",
    );
  });
});

describe("explicit runbook approval", () => {
  it("records only the requested proposal and requires a separate approval click", async () => {
    vi.mocked(getKubernetesRecoveries).mockResolvedValue([recovery()]);
    mount("Runbooks");
    fireEvent.change(await screen.findByLabelText("Incident fingerprint"), {
      target: { value: "recorded-incident" },
    });
    fireEvent.change(screen.getByLabelText("Experiment ID"), {
      target: { value: "recorded-experiment" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Review recovery proposal" }),
    );
    expect(await screen.findByText(/Request recorded/)).toBeVisible();
    expect(proposeKubernetesRecovery).toHaveBeenCalledExactlyOnceWith(
      "recorded-incident",
      "recorded-experiment",
    );
    expect(approveKubernetesRecovery).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Approve restoring one demo worker" }),
    );
    expect(approveKubernetesRecovery).toHaveBeenCalledExactlyOnceWith(
      "recorded-recovery-id",
    );
  });
  it.each(["invalid", new Date(Date.now() - 1000).toISOString()])(
    "disables an expired or invalid approval",
    async (expires) => {
      vi.mocked(getKubernetesRecoveries).mockResolvedValue([
        recovery({ expires_at: expires }),
      ]);
      mount("Runbooks");
      expect(
        await screen.findByRole("button", {
          name: "Approve restoring one demo worker",
        }),
      ).toBeDisabled();
      expect(approveKubernetesRecovery).not.toHaveBeenCalled();
    },
  );
  it("disables an approval when its deadline passes without a navigation", async () => {
    vi.mocked(getKubernetesRecoveries).mockResolvedValue([
      recovery({ expires_at: new Date(Date.now() + 2000).toISOString() }),
    ]);
    mount("Runbooks");
    const button = await screen.findByRole("button", {
      name: "Approve restoring one demo worker",
    });
    expect(button).toBeEnabled();
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(Date.now() + 3000);
    await waitFor(() => expect(button).toBeDisabled(), { timeout: 1500 });
  });
  it("retains server rejections and uncertain outcomes", async () => {
    vi.mocked(proposeKubernetesRecovery).mockRejectedValue(
      new Error("Fresh independent Kubernetes observation required"),
    );
    vi.mocked(getKubernetesRecoveries).mockResolvedValue([
      recovery({ status: "indeterminate", error: "Worker interrupted" }),
    ]);
    mount("Runbooks");
    fireEvent.change(await screen.findByLabelText("Incident fingerprint"), {
      target: { value: "incident" },
    });
    fireEvent.change(screen.getByLabelText("Experiment ID"), {
      target: { value: "experiment" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Review recovery proposal" }),
    );
    expect(
      await screen.findByText(
        "Fresh independent Kubernetes observation required",
      ),
    ).toBeVisible();
    expect(screen.getByText("Worker interrupted")).toBeVisible();
    expect(screen.getByText(/Outcome is uncertain/)).toBeVisible();
    expect(
      screen.queryByRole("button", {
        name: "Approve restoring one demo worker",
      }),
    ).not.toBeInTheDocument();
  });
});


describe("temporary EKS observation permissions", () => {
  it("shows the actual cloud environment without implying measured costs", async () => {
    vi.mocked(getKubernetesWorkloads).mockResolvedValue({
      enabled: true, recovery_enabled: false, environment: "temporary-eks",
      environment_label: "Temporary EKS", observations: [observation()],
    });
    mount("Capacity");
    expect(await screen.findByText("TEMPORARY EKS")).toBeVisible();
    expect(screen.getByText(/Measured consumption and cloud cost estimates are unavailable/)).toBeVisible();
    expect(screen.queryByText(/Local sandbox/)).not.toBeInTheDocument();
  });

  it("retains recovery history while hiding all mutation controls", async () => {
    vi.mocked(getKubernetesWorkloads).mockResolvedValue({
      enabled: true, recovery_enabled: false, environment: "temporary-eks",
      observations: [observation()],
    });
    vi.mocked(getKubernetesRecoveries).mockResolvedValue([recovery()]);
    mount("Runbooks");
    expect(await screen.findByRole("heading", {name: "Recovery actions are disabled"})).toBeVisible();
    expect(await screen.findByText("recorded-recovery-id")).toBeInTheDocument();
    expect(screen.queryByLabelText("Incident fingerprint")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", {name: /Approve restoring/})).not.toBeInTheDocument();
    expect(proposeKubernetesRecovery).not.toHaveBeenCalled();
    expect(approveKubernetesRecovery).not.toHaveBeenCalled();
  });
});
