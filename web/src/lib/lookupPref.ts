/** Whether "Look up each company on the web" is ticked when adding subs. Off by default (each lookup costs
 * web-search credits); the viewer's choice is kept per browser, like the theme. */
const KEY = "ssi-lookup-profiles";

export function savedLookup(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function saveLookup(on: boolean): void {
  try {
    window.localStorage.setItem(KEY, on ? "1" : "0");
  } catch {
    /* private mode: the choice lasts for this page only */
  }
}
