import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../api/client";
import { AddSubsBox } from "../components/AddSubsBox";

afterEach(() => vi.restoreAllMocks());

describe("Add subs", () => {
  it("highlights the rows the server says are already on the project, and adds nothing", async () => {
    const user = userEvent.setup();
    const onAdded = vi.fn();
    vi.spyOn(api, "addSubs").mockRejectedValue(
      new ApiError(409, "1 of these is already on this project.", {
        detail: {
          message: "1 of these is already on this project.",
          duplicates: [{ row: 1, name: "Colmex Contracting, LLC", message: 'Already on this project as "COLMEX CONTRACTING".' }],
        },
      }),
    );
    render(<AddSubsBox projectId="p1" defaultState="FL" onAdded={onAdded} />);

    await user.type(screen.getByLabelText(/Sub 1: Company name/), "Quality Roofing");
    await user.click(screen.getByRole("button", { name: /Add another sub/ }));
    await user.type(screen.getByLabelText(/Sub 2: Company name/), "Colmex Contracting, LLC");
    await user.click(screen.getByRole("button", { name: "Add 2 subs" }));

    expect(await screen.findByText('Already on this project as "COLMEX CONTRACTING".')).toBeInTheDocument();
    expect(screen.getByText("Fix 1 highlighted row first.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add 2 subs" })).toBeDisabled();
    expect(onAdded).not.toHaveBeenCalled();

    // removing the repeated row clears the error, and the rest can be added
    await user.click(screen.getAllByRole("button", { name: "Remove sub 2" })[0]); // phone and desktop copies
    expect(screen.queryByText(/Already on this project/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add 1 sub" })).toBeEnabled();
  });

  it("switches the project's automatic web check and auto-match, when the server can run the check", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { rerender } = render(<AddSubsBox projectId="p1" defaultState="TX" onAdded={() => {}} />);
    expect(screen.queryByRole("checkbox", { name: /automatically/ })).not.toBeInTheDocument();
    rerender(
      <AddSubsBox
        projectId="p1"
        defaultState="TX"
        onAdded={() => {}}
        webCheck={{ autoCheck: false, autoMatch: true, onChange }}
      />,
    );
    const check = screen.getByRole("checkbox", { name: "Check leftover records on the web automatically" });
    const match = screen.getByRole("checkbox", { name: "Auto-match from the web check" });
    expect(check).not.toBeChecked();
    expect(match).toBeChecked();
    expect(match).toHaveAccessibleDescription(/Records with red flags still come to you as a question/);
    await user.click(check);
    await user.click(match);
    expect(onChange.mock.calls).toEqual([[{ auto_web_check: true }], [{ auto_web_match: false }]]);
  });

  it("moves a city and state typed into the name into their own fields", async () => {
    const user = userEvent.setup();
    render(<AddSubsBox projectId="p1" defaultState="TN" onAdded={() => {}} />);
    await user.type(screen.getByLabelText(/Sub 1: Company name/), "COLMEX CONTRACTING LLC. BUNNELL FL");
    await user.click(screen.getByRole("button", { name: "Move “BUNNELL, FL” to city and state" }));
    expect(screen.getByLabelText(/Sub 1: Company name/)).toHaveValue("COLMEX CONTRACTING LLC.");
    expect(screen.getByLabelText(/Sub 1: City/)).toHaveValue("BUNNELL");
    expect(screen.getByLabelText(/Sub 1: State/)).toHaveValue("FL");
  });
});
