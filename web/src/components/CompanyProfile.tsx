import type { CompanyProfile } from "../api/types";
import { formatDate } from "../lib/format";
import { IconSpinner } from "./Icons";

function siteHref(website: string): string {
  return /^https?:\/\//i.test(website) ? website : `https://${website}`;
}

function siteLabel(website: string): string {
  return website.replace(/^https?:\/\/(www\.)?/i, "").replace(/\/$/, "");
}

/**
 * The company profile on a sub's page: who the sub is and the locations it lists, each linked to the page it's
 * quoted from. It never matches records by itself; records at these locations are asked about in the questions.
 * For subs added before profiles, a button looks the company up.
 */
export function CompanyProfileSection({
  profile,
  canLookUp,
  busy,
  onLookUp,
}: {
  profile: CompanyProfile | null | undefined;
  canLookUp: boolean;
  busy: boolean;
  onLookUp: () => void;
}) {
  const button = canLookUp ? (
    <button type="button" className="btn btn-secondary btn-sm mt-3" disabled={busy} onClick={onLookUp}>
      {busy ? (
        <>
          <IconSpinner size={14} /> Looking up…
        </>
      ) : profile ? (
        "Look up again"
      ) : (
        "Look up this company"
      )}
    </button>
  ) : null;

  if (!profile) {
    return (
      <div>
        <p className="text-sm text-ink-2">
          Look the company up on the web to see the locations it lists. OSHA records at those locations come back as a
          question for you; nothing is counted without your answer.
        </p>
        {button}
      </div>
    );
  }
  if (profile.status === "not_found" || !profile.name) {
    return (
      <div>
        <p className="text-sm text-ink-2">No web profile found for this company.{profile.note ? ` ${profile.note}` : ""}</p>
        {button}
      </div>
    );
  }
  return (
    <div>
      <p className="text-[15px] text-ink">
        <span className="font-semibold">{profile.name}</span>
        {profile.website ? (
          <>
            {" · "}
            <a href={siteHref(profile.website)} target="_blank" rel="noreferrer" className="underline underline-offset-2">
              {siteLabel(profile.website)}
            </a>
          </>
        ) : null}
        {profile.summary ? <span className="text-ink-2"> · {profile.summary}</span> : null}
      </p>
      {profile.locations.length ? (
        <ul className="mt-2 space-y-1.5 text-sm text-ink-2" aria-label="Locations the company lists">
          {profile.locations.map((l) => (
            <li key={`${l.address ?? ""}-${l.city}-${l.state}`} className="min-w-0">
              {[l.address, `${l.city} ${l.state}`].filter(Boolean).join(", ")}
              <span className="text-muted"> · {l.kind}</span>
              {" · "}
              <a href={l.source_url} target="_blank" rel="noreferrer" className="underline underline-offset-2" title={l.quote}>
                {l.own_site ? "company site" : "source"}
              </a>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-ink-2">It doesn't list any locations we could check.</p>
      )}
      <p className="mt-2 text-xs text-muted">
        From the web{profile.built_at ? `, ${formatDate(profile.built_at.slice(0, 10))}` : ""}. Only locations quoted from a
        page are kept, and the profile never matches records by itself.
      </p>
      {button}
    </div>
  );
}
