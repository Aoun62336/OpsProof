import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { InvestigationPage } from "./InvestigationPage";

vi.mock("../lib/api", () => ({
  getCapabilities: vi.fn().mockResolvedValue({ environment: "temporary-eks", environment_label: "Temporary EKS", ai_enabled: false }),
  listInvestigations: vi.fn().mockResolvedValue([]),
  getExperiments: vi.fn().mockResolvedValue([]),
  listRecoveries: vi.fn().mockResolvedValue([]),
  getRecoveryEvents: vi.fn().mockResolvedValue([]),
  approveRecovery: vi.fn(), proposeRecovery: vi.fn(), rejectRecovery: vi.fn(),
  requestAiEvaluation: vi.fn(), requestInvestigation: vi.fn(),
}));

describe("Investigation environment", () => {
  it("uses trusted environment identity and provider-neutral disabled wording", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/incidents/aaaaaaaaaaaaaaaa/investigate"]}>
      <Routes><Route path="/incidents/:fingerprint/investigate" element={<InvestigationPage />} /></Routes>
    </MemoryRouter></QueryClientProvider>);
    expect(await screen.findByText("INCIDENT INVESTIGATION / Temporary EKS")).toBeInTheDocument();
    expect(screen.getByText("Model evaluation is disabled.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Evaluate model once" })).not.toBeInTheDocument();
  });
});
