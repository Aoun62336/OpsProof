import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError, getM6TrialArtifacts, getM6TrialEvents, getM6Trials, getM6Verifications } from "../lib/api";
import { M6TrialsPage } from "./M6TrialsPage";

vi.mock("../lib/api", async (original) => ({
  ...await original<typeof import("../lib/api")>(),
  getM6Trials: vi.fn(), getM6TrialEvents: vi.fn(), getM6TrialArtifacts: vi.fn(),
  getM6Verifications: vi.fn(),
}));
const trial = {
  id: "00000000-0000-0000-0000-000000000001", scenario: "worker_failure",
  target: "opsproof-demo/Deployment/demo-worker", phase: "indeterminate",
  source_revision: "38b3a46", approved_test_scope: true, injection_acknowledged: false,
  independent_verified: false, cleanup_verified: false, abort_requested: true,
  created_at: "2026-11-14T07:00:00Z", updated_at: "2026-11-14T07:00:01Z",
  error: "Actuator acknowledgment unavailable; target retained",
};
function mount() {
  const client = new QueryClient({defaultOptions: {queries: {retry: false, gcTime: 0}}});
  return render(<QueryClientProvider client={client}><M6TrialsPage /></QueryClientProvider>);
}
beforeEach(() => {
  vi.mocked(getM6Trials).mockResolvedValue([]);
  vi.mocked(getM6TrialEvents).mockResolvedValue([]);
  vi.mocked(getM6TrialArtifacts).mockResolvedValue([]);
  vi.mocked(getM6Verifications).mockResolvedValue([]);
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("M6 trial inspection", () => {
  it("shows the disabled state separately from empty records", async () => {
    vi.mocked(getM6Trials).mockRejectedValue(new ApiError(404, "M6 ledger is disabled"));
    mount();
    expect(await screen.findByText("Trial ledger is disabled")).toBeVisible();
    expect(screen.queryByText("No M6 trials have been recorded.")).not.toBeInTheDocument();
  });
  it("shows loading and then the honest empty state", async () => {
    mount();
    expect(screen.getByText("Loading trial records...")).toBeVisible();
    expect(await screen.findByText("No M6 trials have been recorded.")).toBeVisible();
  });
  it.each([401, 403, 404, 500])("handles HTTP %s without inventing records", async (status) => {
    vi.mocked(getM6Trials).mockRejectedValue(new ApiError(status, "Request rejected"));
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load trials");
    expect(screen.queryByText("Recorded trials")).not.toBeInTheDocument();
  });
  it("inspects uncertainty, actual event details and artifact identities", async () => {
    vi.mocked(getM6Trials).mockResolvedValue([trial]);
    vi.mocked(getM6TrialEvents).mockResolvedValue([{
      id: 2, kind: "dispatch_intent", details: {target_uid: "observed-worker-uid"},
      created_at: trial.created_at,
    }]);
    vi.mocked(getM6TrialArtifacts).mockResolvedValue([{
      id: 3, kind: "cleanup", relative_path: ".runtime/m6/test/cleanup.json",
      sha256: "a".repeat(64), created_at: trial.created_at,
    }]);
    mount();
    fireEvent.click(await screen.findByRole("button", {name: "worker failure"}));
    expect(await screen.findByText(/dispatch_intent/)).toBeVisible();
    expect(await screen.findByText(".runtime/m6/test/cleanup.json")).toBeVisible();
    expect(screen.getByText(/Cleanup: Not established/)).toBeVisible();
    expect(screen.queryByRole("button", {name: /approve|inject|succeed/i})).not.toBeInTheDocument();
    expect(getM6TrialEvents).toHaveBeenCalledWith(trial.id);
    expect(getM6TrialArtifacts).toHaveBeenCalledWith(trial.id);
  });
  it("reports event and artifact errors", async () => {
    vi.mocked(getM6Trials).mockResolvedValue([trial]);
    vi.mocked(getM6TrialEvents).mockRejectedValue(new Error("offline"));
    vi.mocked(getM6TrialArtifacts).mockRejectedValue(new Error("offline"));
    mount();
    fireEvent.click(await screen.findByRole("button", {name: "worker failure"}));
    expect(await screen.findByText("Could not read event history.")).toBeVisible();
    expect(await screen.findByText("Could not read evidence references.")).toBeVisible();
  });
  it("shows recorded observations and independently verified outcomes", async () => {
    vi.mocked(getM6Trials).mockResolvedValue([trial]);
    vi.mocked(getM6TrialArtifacts).mockResolvedValue([{
      id: 5, kind: "cleanup", relative_path: ".runtime/m6/test/verified.json",
      sha256: "b".repeat(64), created_at: trial.created_at,
      observations: {prometheus: {fresh: true}, durable_jobs: [{status: "completed"}]},
    }]);
    vi.mocked(getM6Verifications).mockResolvedValue([{
      observer_id: trial.id, dispatch_id: "dispatch-from-real-ledger",
      target_uid: "observed-worker-uid", verified_at: trial.created_at,
      cleanup_verified: true, hypothesis_verified: false,
      report_sha256: "c".repeat(64), observer_sha256: "d".repeat(64),
      checks: {current_health: true},
    }]);
    mount();
    fireEvent.click(await screen.findByRole("button", {name: "worker failure"}));
    expect(await screen.findByText("Observed data")).toBeVisible();
    expect(await screen.findByText(/Fault hypothesis: Not established/)).toBeVisible();
    expect(screen.getByText("dispatch-from-real-ledger")).toBeVisible();
    expect(getM6Verifications).toHaveBeenCalledWith(trial.id);
  });
});
