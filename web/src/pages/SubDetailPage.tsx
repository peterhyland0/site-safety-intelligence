import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import { api, errorMessage } from "../api/client";
import type { Bucket, SubDetail } from "../api/types";
import { useApi } from "../api/useApi";
import { AskForemanButton } from "../components/AskForemanButton";
import { CompanyProfileSection } from "../components/CompanyProfile";
import { HazardBreakdown, InjuryRates, LicenceCard, QuestionCard, RedFlagsTable } from "../components/EvidenceSections";
import { IconInfo, IconSpinner, IconTrash, IconTriangleAlert } from "../components/Icons";
import { InspectionBadges, InspectionList } from "../components/InspectionList";
import { MatchBuckets } from "../components/MatchBuckets";
import { ReasonLine } from "../components/SubCard";
import { TrendChart } from "../components/TrendChart";
import { EvidenceChip } from "../components/InspectionSheet";
import { BackLink, ErrorBanner, InlineError, Loading, Section } from "../components/ui";
import { VerdictChip } from "../components/VerdictChip";
import { formatDate, formatMoney, formatRate, plural, yearRange } from "../lib/format";
import { useAdjudication } from "../lib/useAdjudication";
import { useTitle } from "../lib/useTitle";
import { rateComparison, VERDICTS } from "../lib/verdict";

export function SubDetailPage() {
  const { projectId = "", subId = "" } = useParams();
  const detail = useApi((signal) => api.getSub(projectId, subId, signal), [projectId, subId]);
  const [busyQuestion, setBusyQuestion] = useState<string | null>(null);
  const [busyEst, setBusyEst] = useState<string | null>(null);
  const [lookingUp, setLookingUp] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const location = useLocation();
  useTitle(detail.data?.card.entered_name ?? "Sub");

  const cards = useMemo(() => (detail.data ? [detail.data.card] : undefined), [detail.data]);
  const adjudication = useAdjudication(projectId, cards, () => {}, () => void detail.reload());

  // Honour #questions (and other section anchors) once content is first on screen. Only once per
  // hash, so later reloads (after answering a question) don't yank the page.
  const scrolledFor = useRef<string | null>(null);
  const hasData = !!detail.data;
  useEffect(() => {
    if (!hasData || !location.hash || scrolledFor.current === location.hash) return;
    scrolledFor.current = location.hash;
    const id = location.hash.slice(1);
    const t = window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ block: "start" }), 50);
    return () => window.clearTimeout(t);
  }, [hasData, location.hash]);

  const scorecardHref = `/projects/${encodeURIComponent(projectId)}`;

  if (detail.loading) return <Loading label="Loading sub…" />;
  if (detail.error || !detail.data) {
    return (
      <div className="space-y-4">
        <BackLink to={scorecardHref}>Scorecard</BackLink>
        <ErrorBanner message={detail.error ?? "Sub not found."} status={detail.errorStatus} onRetry={detail.reload} />
      </div>
    );
  }

  const d: SubDetail = detail.data;
  const c = d.card;

  async function answer(questionId: string, value: "yes" | "no") {
    setBusyQuestion(questionId);
    setActionError(null);
    try {
      await api.answerQuestion(questionId, value);
      await detail.reload();
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusyQuestion(null);
    }
  }

  async function lookUp() {
    setLookingUp(true);
    setActionError(null);
    try {
      await api.lookupProfile(projectId, subId);
      await detail.reload();
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setLookingUp(false);
    }
  }

  async function move(key: string, bucket: Bucket) {
    setBusyEst(key);
    setActionError(null);
    try {
      await api.overrideMatch(projectId, subId, key, bucket);
      await detail.reload();
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusyEst(null);
    }
  }

  const where = [c.entered_city, c.entered_state].filter(Boolean).join(", ");
  const cmp = rateComparison(c);
  const asOfYear = Number(d.coverage.as_of.slice(0, 4)) || new Date().getFullYear();
  const hasHistory = c.matched_inspections > 0;
  // subs added before profiles (or whose lookup failed) can be looked up, once they're resolved and have records to ask about
  const canLookUp =
    (c.profile_status == null || c.profile_status === "error") &&
    c.match_status !== "needs_adjudication" &&
    d.possible.length + d.excluded.length > 0;
  const showProfile = !!d.profile || canLookUp;
  const fromProfile = d.questions.some((q) => q.kind === "profile");
  const nav = [
    d.questions.length ? ["questions", "Questions"] : null,
    ["reasons", "Why"],
    hasHistory ? ["red-flags", "Red flags"] : null,
    hasHistory ? ["trend", "Trend"] : null,
    hasHistory ? ["hazards", "Hazards"] : null,
    d.injury_rates.length || d.licences.length ? ["rates", "Rates & licence"] : null,
    showProfile ? ["profile", "Company"] : null,
    ["matches", "Matches"],
    hasHistory ? ["inspections", "Inspections"] : null,
  ].filter((x): x is string[] => !!x);

  return (
    <div className={`space-y-4 ${detail.refreshing ? "opacity-70 transition-opacity" : ""}`}>
      <div>
        <BackLink to={scorecardHref}>Scorecard</BackLink>
        <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="page-title break-words">{c.entered_name}</h1>
            <p className="text-sm text-muted">{[where, c.trade_label ?? c.trade].filter(Boolean).join(" · ")}</p>
            {c.display_name ? <p className="text-sm text-muted">OSHA name: {c.display_name}</p> : null}
          </div>
          <VerdictChip verdict={c.verdict} label={c.verdict_label} size="lg" />
        </div>
        <p className="mt-2 text-sm text-ink-2">{VERDICTS[c.verdict].meaning}</p>
        <p className="mt-3 rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm text-ink-2">{d.coverage.sentence}</p>
        {c.same_records_as?.length ? (
          <div className="mt-3 flex gap-2 rounded-xl border border-review-line bg-review-bg px-3.5 py-2.5 text-sm text-review-fg">
            <IconTriangleAlert size={16} className="mt-0.5 shrink-0" />
            <p>
              Matched to the same OSHA record as{" "}
              {c.same_records_as.map((s, i) => (
                <Fragment key={s.sub_id}>
                  {i ? ", " : ""}
                  <Link
                    to={`/projects/${encodeURIComponent(projectId)}/subs/${encodeURIComponent(s.sub_id)}`}
                    className="font-semibold underline underline-offset-2"
                  >
                    {s.name}
                  </Link>
                </Fragment>
              ))}
              , also on this project. If it's the same company,{" "}
              <a href="#remove" className="font-semibold underline underline-offset-2">
                remove one
              </a>
              .
            </p>
          </div>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-2">
          <AskForemanButton projectId={projectId} label="Ask about this sub" className="btn btn-secondary btn-sm" />
        </div>
      </div>

      {c.match_status === "needs_adjudication" ? (
        adjudication.errors[c.sub_id] ? (
          <div role="alert" className="card flex flex-wrap items-center gap-2 p-3 text-sm text-ink-2">
            <span className="flex-1">Couldn't resolve the uncertain records yet. {adjudication.errors[c.sub_id]}</span>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => adjudication.retry(c.sub_id)}>
              Try again
            </button>
          </div>
        ) : (
          <p role="status" className="card flex items-center gap-2 p-3 text-sm text-ink-2">
            <IconSpinner size={16} />{" "}
            {c.profile_status === "pending" ? "Looking up the company on the web, then resolving" : "Resolving"} uncertain
            records… The verdict may change when this finishes.
          </p>
        )
      ) : null}

      <nav aria-label="Sections" className="no-scrollbar -mx-4 overflow-x-auto px-4">
        <ul className="flex gap-2 pb-1">
          {nav.map(([id, label]) => (
            <li key={id}>
              <a href={`#${id}`} className="pill min-h-8 border-line-strong bg-surface px-3 whitespace-nowrap text-ink-2 hover:bg-surface-2">
                {label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <InlineError message={actionError} />

      {d.questions.length ? (
        <Section id="questions" title={`${plural(d.questions.length, "question")} about matching`} className="scroll-mt-20">
          <p className="mb-3 text-sm text-ink-2">
            {fromProfile
              ? "These records might belong to this sub. Your answer decides whether they count."
              : "These records might belong to this sub and carry red flags. Your answer decides whether they count."}
          </p>
          <ul className="space-y-3">
            {d.questions.map((q) => (
              <QuestionCard
                key={q.question_id}
                question={q}
                establishments={[...d.possible, ...d.matched, ...d.excluded]}
                busy={busyQuestion === q.question_id || busyEst !== null}
                onAnswer={(a) => answer(q.question_id, a)}
                onRecord={(key, bucket) => void move(key, bucket)}
              />
            ))}
          </ul>
        </Section>
      ) : null}

      <Section id="reasons" title="Why this verdict" className="scroll-mt-20">
        {d.reasons.length ? (
          <ul className="space-y-3">
            {d.reasons.map((r) => (
              <li key={`${r.code}-${r.label}`} className="text-[15px] text-ink">
                <ReasonLine reason={r} />
                {r.evidence.length ? (
                  <div className="mt-1.5 flex flex-wrap gap-1.5 pl-6" aria-label="Evidence inspections">
                    {r.evidence.slice(0, 12).map((nr) => (
                      <EvidenceChip key={nr} activityNr={nr} />
                    ))}
                    {r.evidence.length > 12 ? <span className="text-xs text-muted">+{r.evidence.length - 12} more</span> : null}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-2">
            {c.verdict === "no_record"
              ? "No OSHA inspections matched this name. Unknown is not clean: ask the sub for TRIR, EMR and their safety program."
              : "Nothing in the OSHA record met a concern rule."}
          </p>
        )}
        {hasHistory ? (
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-line pt-3 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs text-muted">Serious+ per inspection ({c.window_years} yr)</dt>
              <dd className="font-semibold text-ink tabular-nums">
                {formatRate(c.serious_plus_rate)}
                {c.trade_p50 != null ? <span className="font-normal text-muted"> vs {formatRate(c.trade_p50)} median</span> : null}
              </dd>
              {cmp ? <dd className="text-xs text-muted">{cmp}{c.trade_p75 != null ? ` (75th pct ${formatRate(c.trade_p75)})` : ""}</dd> : null}
            </div>
            <div>
              <dt className="text-xs text-muted">Inspections, last {c.window_years} yr</dt>
              <dd className="font-semibold text-ink tabular-nums">{c.inspections_in_window}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">All matched inspections</dt>
              <dd className="font-semibold text-ink tabular-nums">
                {c.matched_inspections}
                <span className="font-normal text-muted"> · {plural(c.matched_establishments, "establishment")}</span>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Active</dt>
              <dd className="text-ink">
                {yearRange(c.first_year, c.last_year) ?? "—"}
                {c.states.length ? <span className="text-muted"> · {c.states.join(", ")}</span> : null}
              </dd>
            </div>
          </dl>
        ) : null}
      </Section>

      {hasHistory ? (
        <Section
          id="red-flags"
          title="Red flags"
          aside={`all years · ${plural(d.red_flags.filter((f) => f.bucket === "matched").length, "counted")}`}
          className="scroll-mt-20"
        >
          <RedFlagsTable flags={d.red_flags} />
        </Section>
      ) : null}

      {hasHistory && d.trend.length ? (
        <Section id="trend" title="Inspections and citations per year" className="scroll-mt-20">
          <TrendChart rows={d.trend} windowYears={c.window_years} asOfYear={asOfYear} />
        </Section>
      ) : null}

      {hasHistory ? (
        <Section id="hazards" title="Citations by hazard" aside="all years, deleted citations excluded" className="scroll-mt-20">
          <HazardBreakdown hazards={d.hazards} />
        </Section>
      ) : null}

      {d.open_cases.length ? (
        <Section id="open-cases" title={`Open cases (${d.open_cases.length})`} className="scroll-mt-20">
          <p className="mb-2 text-sm text-ink-2">
            Provisional: citations and penalties on open cases often change after settlement or contest.
          </p>
          <ul className="divide-y divide-line">
            {d.open_cases.map((o) => (
              <li key={o.activity_nr} className="py-2 text-sm">
                <p className="font-medium text-ink">
                  Opened {formatDate(o.open_date)} · {o.insp_type_label}
                  {o.site_city ? <span className="font-normal text-ink-2"> · {[o.site_city, o.site_state].filter(Boolean).join(", ")}</span> : null}
                </p>
                <p className="text-ink-2">
                  {plural(o.citations, "citation")} so far ({o.serious_plus} serious+) · proposed penalties {formatMoney(o.penalty_initial)}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <InspectionBadges row={o} />
                  <EvidenceChip activityNr={o.activity_nr} />
                </div>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {d.injury_rates.length || d.licences.length ? (
        <Section id="rates" title="Injury rates and licence" className="scroll-mt-20">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
            {d.injury_rates.length ? (
              <InjuryRates rows={d.injury_rates} />
            ) : (
              <p className="text-sm text-muted">
                No OSHA injury-rate filings linked. Firms under 20 employees don't file Form 300A; ask the sub for TRIR and EMR.
              </p>
            )}
            {d.licences.length ? (
              <div className="space-y-2">
                {d.licences.map((l) => (
                  <LicenceCard key={`${l.source}-${l.number}`} licence={l} />
                ))}
              </div>
            ) : null}
          </div>
        </Section>
      ) : null}

      {showProfile ? (
        <Section id="profile" title="Company profile" className="scroll-mt-20">
          <CompanyProfileSection profile={d.profile} canLookUp={canLookUp} busy={lookingUp} onLookUp={() => void lookUp()} />
        </Section>
      ) : null}

      <Section id="matches" title="How we found this company in OSHA's records" className="scroll-mt-20">
        <MatchBuckets
          matched={d.matched}
          possible={d.possible}
          excluded={d.excluded}
          onMove={move}
          busyKey={busyEst}
          asOf={d.coverage.as_of}
        />
      </Section>

      {hasHistory ? (
        <Section id="inspections" title="All matched inspections" aside="newest first" className="scroll-mt-20">
          <InspectionList
            key={`${subId}-${c.matched_inspections}-${d.inspections[0]?.activity_nr ?? 0}`}
            projectId={projectId}
            subId={subId}
            initial={d.inspections}
            total={d.coverage.inspections_all_time}
          />
        </Section>
      ) : null}

      {d.dq_warnings.length ? (
        <Section id="data-quality" title="Data-quality notes">
          <ul className="space-y-2 text-sm text-ink-2">
            {d.dq_warnings.map((w) => (
              <li key={w} className="flex gap-2">
                <IconInfo size={16} className="mt-0.5 shrink-0 text-muted" />
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      <RemoveSub projectId={projectId} subId={subId} name={c.entered_name} />
    </div>
  );
}

function RemoveSub({ projectId, subId, name }: { projectId: string; subId: string; name: string }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function remove() {
    if (!window.confirm(`Remove ${name} from this project? Match decisions for this sub will be lost.`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteSub(projectId, subId);
      navigate(`/projects/${encodeURIComponent(projectId)}`);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }
  return (
    <div id="remove" className="scroll-mt-20 pt-2">
      <InlineError message={error} />
      <button type="button" className="btn btn-ghost btn-sm text-high-fg" onClick={remove} disabled={busy}>
        <IconTrash size={16} />
        {busy ? "Removing…" : "Remove from project"}
      </button>
    </div>
  );
}
