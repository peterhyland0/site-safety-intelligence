import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  try {
    sessionStorage.clear();
  } catch {
    /* ignore */
  }
});

// jsdom lacks these; the chat scrolls its log and the chart measures itself.
if (!Element.prototype.scrollTo) {
  Element.prototype.scrollTo = function scrollTo() {} as typeof Element.prototype.scrollTo;
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {};
}
