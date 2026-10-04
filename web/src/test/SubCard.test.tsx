import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { SubCard } from "../components/SubCard";
import { toProjectDetail } from "../mock/derive";
import { seedProjects } from "../mock/fixtures";

const card = () => toProjectDetail(structuredClone(seedProjects()[0])).subs[0];

describe("Sub card", () => {
  it("says when another sub on the project matched the same OSHA record", () => {
    render(
      <MemoryRouter>
        <SubCard card={{ ...card(), same_records_as: [{ sub_id: "s2", name: "COLMEX CONTRACTING" }] }} projectId="p1" />
      </MemoryRouter>,
    );
    expect(screen.getByText("Same OSHA record as COLMEX CONTRACTING. Same company? Remove one.")).toBeInTheDocument();
  });

  it("says nothing when no other sub shares a record", () => {
    render(
      <MemoryRouter>
        <SubCard card={{ ...card(), same_records_as: [] }} projectId="p1" />
      </MemoryRouter>,
    );
    expect(screen.queryByText(/Same OSHA record/)).not.toBeInTheDocument();
  });

  it("says it's looking the company up while a new sub resolves", () => {
    render(
      <MemoryRouter>
        <SubCard card={{ ...card(), match_status: "needs_adjudication", profile_status: "pending", possible_inspections: 7 }} projectId="p1" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Looking up the company, then resolving 7 uncertain records…");
  });
});
