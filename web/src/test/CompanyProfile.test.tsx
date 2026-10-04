import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { CompanyProfile } from "../api/types";
import { CompanyProfileSection } from "../components/CompanyProfile";

const profile: CompanyProfile = {
  status: "found",
  name: "Tindall Corporation",
  website: "tindallcorp.com",
  summary: "Precast concrete",
  note: null,
  built_at: "2026-10-04T12:00:00Z",
  locations: [
    { address: "5400 Olgers Road", city: "Petersburg", state: "VA", zip: "23803", kind: "plant",
      source_url: "https://tindallcorp.com/contact/", quote: "Virginia Division 5400 Olgers Road", own_site: true },
    { address: null, city: "San Antonio", state: "TX", zip: null, kind: "plant",
      source_url: "https://example.com/news", quote: "a plant in San Antonio, TX", own_site: false },
  ],
};

describe("Company profile", () => {
  it("lists the locations with the page each is quoted from", () => {
    render(<CompanyProfileSection profile={profile} canLookUp={false} busy={false} onLookUp={vi.fn()} />);
    expect(screen.getByRole("link", { name: "tindallcorp.com" })).toHaveAttribute("href", "https://tindallcorp.com");
    const list = screen.getByRole("list", { name: "Locations the company lists" });
    expect(list).toHaveTextContent("5400 Olgers Road, Petersburg VA · plant · company site");
    expect(list).toHaveTextContent("San Antonio TX · plant · source");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("offers a lookup for a sub without one", async () => {
    const user = userEvent.setup();
    const onLookUp = vi.fn();
    render(<CompanyProfileSection profile={null} canLookUp busy={false} onLookUp={onLookUp} />);
    await user.click(screen.getByRole("button", { name: "Look up this company" }));
    expect(onLookUp).toHaveBeenCalledOnce();
  });

  it("says when nothing was found", () => {
    render(
      <CompanyProfileSection
        profile={{ ...profile, status: "not_found", name: null, locations: [], note: "Several companies share the name." }}
        canLookUp={false}
        busy={false}
        onLookUp={vi.fn()}
      />,
    );
    expect(screen.getByText("No web profile found for this company. Several companies share the name.")).toBeInTheDocument();
  });
});
