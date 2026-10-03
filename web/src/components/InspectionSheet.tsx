import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api/client";
import { OSHA_SEARCH_PAGE, type InspectionDetail } from "../api/types";
import { formatDate } from "../lib/format";
import { IconSpinner } from "./Icons";
import { InspectionBadges, InspectionDetailView } from "./InspectionList";
import { InlineError } from "./ui";

/**
 * Tappable inspection number. Opens the inspection's record from our own data (citations, penalties,
 * accident narrative); the osha.gov page is a secondary link inside, because osha.gov puts a
 * human-verification check in front of it.
 */
export function EvidenceChip({ activityNr }: { activityNr: number }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        className="inline-flex min-h-8 items-center rounded-full border border-line-strong bg-surface px-2.5 text-xs font-medium text-accent tabular-nums hover:bg-accent-soft"
        aria-label={`Inspection ${activityNr}: show the record`}
      >
        {activityNr}
      </button>
      {open ? <InspectionSheet activityNr={activityNr} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

/** Modal sheet with one inspection's record: a bottom sheet on phones, a centred panel on wider screens. */
export function InspectionSheet({ activityNr, onClose }: { activityNr: number; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [detail, setDetail] = useState<InspectionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const titleId = `insp-sheet-${activityNr}`;
  const onCloseRef = useRef(onClose); // the parent's callback may change identity on every render
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    // Esc and close() both fire "close"; the browser returns focus to the chip.
    const closed = () => onCloseRef.current();
    d.addEventListener("close", closed);
    if (typeof d.showModal === "function") d.showModal();
    else d.setAttribute("open", ""); // jsdom
    return () => {
      d.removeEventListener("close", closed);
      if (d.open && typeof d.close === "function") d.close();
    };
  }, []);

  useEffect(() => {
    let live = true;
    api
      .getInspection(activityNr)
      .then((r) => live && setDetail(r))
      .catch((err) => live && setError(errorMessage(err)));
    return () => {
      live = false;
    };
  }, [activityNr]);

  function close() {
    const d = ref.current;
    if (d && typeof d.close === "function" && d.open) d.close();
    else onCloseRef.current();
  }

  const place = detail ? [detail.site_city, detail.site_state].filter(Boolean).join(", ") : "";
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClick={(e) => e.target === e.currentTarget && close()} // a tap on the backdrop closes
      className="mx-0 mt-auto mb-0 max-h-[85dvh] w-full max-w-full overflow-hidden rounded-t-2xl border border-line bg-surface p-0 text-ink backdrop:bg-black/50 sm:m-auto sm:max-w-xl sm:rounded-2xl"
    >
      <div className="flex max-h-[calc(85dvh-2px)] flex-col">
        <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0">
            <h2 id={titleId} className="section-title tabular-nums">
              Inspection {activityNr}
            </h2>
            {detail ? (
              <>
                <p className="text-sm text-ink-2">
                  {formatDate(detail.open_date)} · {detail.insp_type_label}
                  {place ? ` · ${place}` : ""}
                </p>
                <p className="text-xs text-muted">{detail.establishment_name}</p>
              </>
            ) : null}
          </div>
          <button type="button" className="btn btn-ghost btn-sm shrink-0" onClick={close}>
            Close
          </button>
        </div>
        <div className="overflow-y-auto px-4 py-3">
          {detail ? (
            <>
              <div className="mb-3">
                <InspectionBadges row={detail} />
              </div>
              <InspectionDetailView detail={detail} />
            </>
          ) : error ? (
            <div className="space-y-2 text-sm">
              <InlineError message={error} />
              <p>
                <a href={OSHA_SEARCH_PAGE} target="_blank" rel="noopener noreferrer" className="link">
                  Search OSHA's establishment records
                </a>
                <span className="text-muted"> instead.</span>
              </p>
            </div>
          ) : (
            <p role="status" className="flex items-center gap-2 text-sm text-muted">
              <IconSpinner size={16} /> Loading the record…
            </p>
          )}
        </div>
      </div>
    </dialog>
  );
}
