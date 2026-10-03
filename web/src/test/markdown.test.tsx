import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown } from "../lib/markdown";

describe("Markdown", () => {
  it("renders bold, lists and tables as elements", () => {
    const { container } = render(
      <Markdown text={"**Summit Ridge Roofing**: High concern.\n- Fatality (2022)\n- 1 open case\n\n| Sub | Rate |\n|---|---|\n| A | 1.20 |"} />,
    );
    expect(screen.getByText("Summit Ridge Roofing").tagName).toBe("STRONG");
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "1.20" })).toBeInTheDocument();
  });

  it("never injects HTML and only links http(s) or relative URLs", () => {
    const { container } = render(
      <Markdown text={'<img src=x onerror="alert(1)"> [osha](https://www.osha.gov/x) [bad](javascript:alert(1))'} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img src=x");
    const links = container.querySelectorAll("a");
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("href")).toBe("https://www.osha.gov/x");
    expect(links[0].getAttribute("rel")).toContain("noopener");
  });

  it("leaves snake_case identifiers alone", () => {
    const { container } = render(<Markdown text="uses fall_protection_hazard code" />);
    expect(container.querySelector("em")).toBeNull();
  });
});
