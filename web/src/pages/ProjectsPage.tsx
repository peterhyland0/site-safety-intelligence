import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, errorMessage } from "../api/client";
import type { Project } from "../api/types";
import { useApi } from "../api/useApi";
import { IconChevronRight, IconPlus } from "../components/Icons";
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
    <div className="space-y-8">
      <section className="flex flex-col items-center gap-4 pt-4 text-center sm:pt-8" aria-labelledby="projects-title">
        <p className="eyebrow">OSHA history for every sub on your bid</p>
        <h1 id="projects-title" className="page-title max-w-2xl sm:text-[42px]">
          Know which subs to worry about <span className="text-gradient">before you sign</span>
        </h1>
        <p className="max-w-xl text-[15.5px] leading-relaxed text-muted">
          One project per bid. Paste the subs you're considering and get a ranked view of their OSHA safety history,
          with the inspections behind every flag. Your foreman can ask about them from the site.
        </p>
        <ul className="flex flex-wrap justify-center gap-2" aria-label="What you get">
          {[
            ["Ranked", "scorecard"],
            ["Evidence", "on every flag"],
            ["Foreman", "assistant"],
          ].map(([strong, rest]) => (
            <li
              key={strong}
              className="rounded-full bg-surface px-3.5 py-1.5 text-xs font-medium text-muted shadow-[var(--shadow-card)]"
            >
              <strong className="font-bold text-ink">{strong}</strong> {rest}
            </li>
          ))}
        </ul>
        {!formOpen ? (
          <button type="button" className="btn btn-primary mt-1 min-h-12 px-7" onClick={() => setShowForm(true)}>
            <IconPlus size={18} />
            New project
          </button>
        ) : null}
      </section>

      {formOpen ? <NewProjectForm onCancel={list.length ? () => setShowForm(false) : undefined} /> : null}

      {projects.loading ? (
        <Loading label="Loading projects…" />
      ) : projects.error ? (
        <ErrorBanner message={projects.error} status={projects.errorStatus} onRetry={projects.reload} />
      ) : list.length ? (
        <section aria-labelledby="your-projects" className="space-y-3">
          <h2 id="your-projects" className="eyebrow">
            Your projects
          </h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {list.map((p) => (
              <li key={p.project_id}>
                <ProjectRow project={p} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function ProjectRow({ project: p }: { project: Project }) {
  return (
    <Link
      to={`/projects/${encodeURIComponent(p.project_id)}`}
      className="card flex min-h-20 items-center gap-3 p-4 transition-shadow hover:border-line-strong hover:shadow-md"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate font-bold tracking-[-0.01em] text-ink">{p.name}</p>
        <p className="mt-0.5 text-sm text-muted">
          {[
            p.state ? (US_STATES[p.state] ?? p.state) : null,
            plural(p.sub_count, "sub"),
            `${p.lookback_years}-year lookback`,
          ]
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
      const p = await api.createProject({
        name: name.trim(),
        state: state || null,
        lookback_years: 5, // the usual prequalification window; changed on the scorecard
      });
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
