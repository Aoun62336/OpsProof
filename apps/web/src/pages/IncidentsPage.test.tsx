import {
  describe,
  expect,
  it,
  vi,
} from "vitest";

import "@testing-library/jest-dom/vitest";

import {
  render,
  screen,
} from "@testing-library/react";

import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

import { IncidentsPage } from "./IncidentsPage";

vi.mock("../lib/api", () => ({
  getIncidents: vi.fn().mockResolvedValue([]),
  getIncidentEvents: vi.fn().mockResolvedValue([]),
}));


describe("Incident Registry", () => {
  it("shows an honest empty state", async () => {
    const client = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    render(
      <QueryClientProvider client={client}>
        <IncidentsPage />
      </QueryClientProvider>,
    );

    expect(
      screen.getByRole("heading", {
        name: "Incidents",
      }),
    ).toBeInTheDocument();

    expect(
      await screen.findByText(
        "No matching alert records",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /does not establish that every workload/i,
      ),
    ).toBeInTheDocument();
  });
});
