import { useCallback, useState } from "react";
import { Link, useParams } from "react-router";
import { api, errorMessage, MOCK_MODE } from "../api/client";
import type { LookbackYears, ProjectDetail, SubCard as SubCardT, Verdict } from "../api/types";
import { useApi } from "../api/useApi";
import { AddSubsBox } from "../components/AddSubsBox";
import { IconChat, IconDownload, IconPlus } from "../components/Icons";
import { LookbackToggle } from "../components/LookbackToggle";
import { SubCard } from "../components/SubCard";
import { BackLink, ErrorBanner, InlineError, Loading } from "../components/ui";
import { VerdictIcon } from "../components/VerdictChip";
import { formatDate, plural } from "../lib/format";
import { US_STATES } from "../lib/parseSubs";
import { useAdjudication } from "../lib/useAdjudication";
import { useTitle } from "../lib/useTitle";
import { VERDICT_ORDER, VERDICTS } from "../lib/verdict";

export function ProjectPage() {
  const { projectId = "" } = useParams();
  const detail = useApi((signal) => api.getProject(projectId, signal), [projectId]);
  const [adding, setAdding] = useState(false);
  const [lookbackError, setLookbackError] = useState<string | null>(null);
  const [savingLookback, setSavingLookback] = useState(false);
  useTitle(detail.data?.project.name ?? "Project");

  const { setData, reload } = detail;
  const applyCard = useCallback(
    (card: SubCardT) =>
      setData((prev) =>
        prev ? { ...prev, subs: prev.subs.map((s) => (s.sub_id === card.sub_id ? card : s)) } : prev,
      ),
    [setData],
  );
  const adjudication = useAdjudication(projectId, detail.data?.subs, applyCard, () => void reload());

  async function changeLookback(years: LookbackYears) {
    if (!detail.data) return;
    const previous = detail.data.project.lookback_years;
    setLookbackError(null);
    setSavingLookback(true);
    setData((prev) => (prev ? { ...prev, project: { ...prev.project, lookback_years: years } } : prev));
    try {
      await api.updateProject(projectId, { lookback_years: years });
      await reload();
    } catch (err) {
      setData((prev) => (prev ? { ...prev, project: { ...prev.project, lookback_years: previous } } : prev));
      setLookbackError(errorMessage(err));
    } finally {
      setSavingLookback(false);
    }
  }

  if (detail.loading) return <Loading label="Loading scorecard…" />;
  if (detail.error || !detail.data) {
    return (
      <div className="space-y-4">
        <BackLink to="/">All projects</BackLink>
        <ErrorBanner message={detail.error ?? "Project not found."} status={detail.errorStatus} onRetry={reload} />
      </div>
    );
  }

  const { project, subs, data_as_of } = detail.data;
  const showAdd = adding || subs.length === 0;
  const askHref = `/projects/${encodeURIComponent(project.project_id)}/ask`;

  return (
    <div className="space-y-5">
      <div>
        <BackLink to="/">All projects</BackLink>
        <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight text-ink">{project.name}</h1>
            <p className="mt-0.5 text-sm text-muted">
              {[project.state ? `Job site: ${US_STATES[project.state] ?? project.state}` : null, plural(project.sub_count || subs.length, "sub")]
                .filter(Boolean)
                .join(" · ")}
              {" · "}OSHA data as of {formatDate(data_as_of)}
            </p>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-3">
          <LookbackToggle value={project.lookback_years} onChange={changeLookback} disabled={savingLookback} />
          <div className="flex flex-wrap gap-2">
            <Link to={askHref} className="btn btn-primary btn-sm">
              <IconChat size={16} />
              Ask the foreman assistant
            </Link>
            <ExportLink projectId={project.project_id} disabled={!subs.length} />
          </div>
        </div>
        <InlineError message={lookbackError} />
      </div>

      {subs.length ? <VerdictSummary subs={subs} /> : null}

      {showAdd ? (
        <AddSubsBox
          projectId={project.project_id}
          defaultState={project.state}
          onAdded={() => {
            setAdding(false);
            void reload();
          }}
          onCancel={subs.length ? () => setAdding(false) : undefined}
        />
      ) : null}

      {subs.length ? (
        <section aria-labelledby="scorecard-title" className={detail.refreshing ? "opacity-60 transition-opacity" : ""}>
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="scorecard-title" className="section-title">
              Scorecard <span className="font-normal text-muted">· most concern first</span>
            </h2>
            {!showAdd ? (
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setAdding(true)}>
                <IconPlus size={16} />
                Add subs
              </button>
            ) : null}
          </div>
          <ol className="space-y-3" aria-busy={detail.refreshing || undefined}>
            {subs.map((card) => (
              <li key={card.sub_id}>
                <SubCard
                  card={card}
                  projectId={project.project_id}
                  resolveError={adjudication.errors[card.sub_id]}
                  onRetryResolve={() => adjudication.retry(card.sub_id)}
                />
              </li>
            ))}
          </ol>
          <p className="mt-4 text-sm text-muted">
            Verdicts come from fixed rules over OSHA inspection records; see{" "}
            <Link to="/methodology" className="link">
              how verdicts work
            </Link>
            . "No OSHA record" means unknown, not clean.
          </p>
        </section>
      ) : null}
    </div>
  );
}

function VerdictSummary({ subs }: { subs: ProjectDetail["subs"] }) {
  const counts = new Map<Verdict, number>();
  for (const s of subs) counts.set(s.verdict, (counts.get(s.verdict) ?? 0) + 1);
  const pending = subs.reduce((a, s) => a + s.pending_questions, 0);
  return (
    <div className="card p-3">
      <h2 className="sr-only">Summary</h2>
      <ul className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
        {VERDICT_ORDER.filter((v) => counts.get(v)).map((v) => (
          <li key={v} className={`flex items-center gap-1.5 ${toneText(v)}`}>
            <VerdictIcon verdict={v} size={16} />
            <span className="font-semibold tabular-nums">{counts.get(v)}</span>
            <span className="text-ink-2">{VERDICTS[v].label}</span>
          </li>
        ))}
        {pending ? (
          <li className="flex items-center gap-1.5 text-accent">
            <span className="font-semibold tabular-nums">{pending}</span>
            <span className="text-ink-2">{pending === 1 ? "match question" : "match questions"} waiting</span>
          </li>
        ) : null}
      </ul>
    </div>
  );
}

function toneText(v: Verdict) {
  return v === "high"
    ? "text-high-fg"
    : v === "review"
      ? "text-review-fg"
      : v === "no_record"
        ? "text-unknown-fg"
        : v === "no_recent"
          ? "text-recent-fg"
          : "text-clear-fg";
}

function ExportLink({ projectId, disabled }: { projectId: string; disabled: boolean }) {
  const cls = `btn btn-secondary btn-sm ${disabled ? "pointer-events-none opacity-60" : ""}`;
  if (MOCK_MODE) {
    // The mock backend has no file endpoint: build the CSV in the browser.
    const download = async () => {
      const { exportCsv } = await import("../mock/handlers");
      const blob = new Blob([exportCsv(projectId)], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `scorecard-${projectId}.csv`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
    return (
      <button type="button" className={cls} onClick={download} disabled={disabled}>
        <IconDownload size={16} />
        Export CSV
      </button>
    );
  }
  return (
    <a href={api.exportCsvUrl(projectId)} className={cls} download aria-disabled={disabled || undefined}>
      <IconDownload size={16} />
      Export CSV
    </a>
  );
}
