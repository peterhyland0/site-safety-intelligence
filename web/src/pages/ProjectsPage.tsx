import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, errorMessage } from "../api/client";
import type { LookbackYears, Project } from "../api/types";
import { useApi } from "../api/useApi";
import { IconChevronRight, IconPlus } from "../components/Icons";
import { LookbackToggle } from "../components/LookbackToggle";
import { ErrorBanner, InlineError, Loading } from "../components/ui";
import { formatDate, plural } from "../lib/format";
import { US_STATES } from "../lib/parseSubs";
import { useTitle } from "../lib/useTitle";

export function ProjectsPage() {
  useTitle("Projects");
  const projects = useApi(() => api.listProjects(), []);
  const [showForm, setShowForm] = useState(false);

  const list = projects.data ?? [];
  const formOpen = showForm || (!projects.loading && !projects.error && list.length === 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Projects</h1>
          <p className="mt-1 max-w-prose text-ink-2">
            One project per bid. Paste the subs you're considering and get a ranked view of their OSHA safety history,
            with the inspections behind every flag.
          </p>
        </div>
        {!formOpen ? (
          <button type="button" className="btn btn-primary" onClick={() => setShowForm(true)}>
            <IconPlus size={18} />
            New project
          </button>
        ) : null}
      </div>

      {formOpen ? (
        <NewProjectForm
          onCancel={list.length ? () => setShowForm(false) : undefined}
        />
      ) : null}

      {projects.loading ? (
        <Loading label="Loading projects…" />
      ) : projects.error ? (
        <ErrorBanner message={projects.error} status={projects.errorStatus} onRetry={projects.reload} />
      ) : list.length ? (
        <ul className="grid gap-3 sm:grid-cols-2" aria-label="Your projects">
          {list.map((p) => (
            <li key={p.project_id}>
              <ProjectRow project={p} />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function ProjectRow({ project: p }: { project: Project }) {
  return (
    <Link
      to={`/projects/${encodeURIComponent(p.project_id)}`}
      className="card flex min-h-20 items-center gap-3 p-4 hover:border-line-strong hover:bg-surface-2/40"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold text-ink">{p.name}</p>
        <p className="mt-0.5 text-sm text-muted">
          {[p.state ? US_STATES[p.state] ?? p.state : null, plural(p.sub_count, "sub"), `${p.lookback_years}-year lookback`]
            .filter(Boolean)
            .join(" · ")}
        </p>
        <p className="text-xs text-muted">Created {formatDate(p.created_at)}</p>
      </div>
      <IconChevronRight className="shrink-0 text-muted" />
    </Link>
  );
}

function NewProjectForm({ onCancel }: { onCancel?: () => void }) {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [state, setState] = useState("");
  const [lookback, setLookback] = useState<LookbackYears>(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("Give the project a name.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const p = await api.createProject({ name: name.trim(), state: state || null, lookback_years: lookback });
      navigate(`/projects/${encodeURIComponent(p.project_id)}`);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card space-y-4 p-4 sm:p-5" aria-labelledby="new-project-title" noValidate>
      <h2 id="new-project-title" className="section-title">
        New project
      </h2>
      <div className="grid gap-4 sm:grid-cols-[1fr_14rem]">
        <div>
          <label htmlFor="project-name" className="label">
            Project name
          </label>
          <input
            id="project-name"
            className="field"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Riverside Medical Office Building"
            autoComplete="off"
            required
            aria-invalid={error && !name.trim() ? true : undefined}
          />
        </div>
        <div>
          <label htmlFor="project-state" className="label">
            Job-site state
          </label>
          <select id="project-state" className="field" value={state} onChange={(e) => setState(e.target.value)}>
            <option value="">Not set</option>
            {Object.entries(US_STATES).map(([code, label]) => (
              <option key={code} value={code}>
                {label} ({code})
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-muted">Used as the default state for subs you paste without one.</p>
        </div>
      </div>
      <div>
        <LookbackToggle value={lookback} onChange={setLookback} label="Lookback" />
        <p className="mt-1 text-xs text-muted">
          Rates, trends and repeat violations use this window. Cited fatalities, willful violations and failures to abate
          are flagged whatever their age.
        </p>
      </div>
      <InlineError message={error} />
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? "Creating…" : "Create project"}
        </button>
        {onCancel ? (
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
        ) : null}
      </div>
    </form>
  );
}
