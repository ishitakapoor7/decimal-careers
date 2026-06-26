import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { Application, Job } from "../api/types";
import { ApplyDrawer } from "../components/ApplyDrawer";
import { ActivityHeader } from "../components/Header";
import { Tag } from "../components/Tag";
import { HeartFilled } from "../components/icons";
import {
  humanize,
  initial,
  jobMeta,
  salaryRange,
  shortDate,
  workModeLabel,
  workModeTone,
} from "../lib/format";
import { useCandidate } from "../state/CandidateContext";
import styles from "./MyActivityPage.module.css";

type TabKey = "applications" | "saved";

export function MyActivityPage() {
  const navigate = useNavigate();
  const { candidateId, activityVersion, toggleSave, notifyActivityChanged } =
    useCandidate();

  const [tab, setTab] = useState<TabKey>("applications");
  const [applications, setApplications] = useState<Application[]>([]);
  const [jobsById, setJobsById] = useState<Record<string, Job>>({});
  const [saved, setSaved] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [applyJob, setApplyJob] = useState<Job | null>(null);

  useEffect(() => {
    if (!candidateId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      api.listApplications(candidateId),
      api.listSaved(candidateId),
    ])
      .then(async ([appsRes, savedRes]) => {
        if (cancelled) return;
        setApplications(appsRes.items);
        setSaved(savedRes.items);
        setExpanded(appsRes.items[0]?.id ?? null);
        // Applications only carry a job_id; fetch the jobs to show title/company.
        const ids = [...new Set(appsRes.items.map((a) => a.job_id))];
        const jobs = await Promise.all(
          ids.map((id) => api.getJob(id).catch(() => null)),
        );
        if (cancelled) return;
        const map: Record<string, Job> = {};
        for (const j of jobs) if (j) map[j.id] = j;
        setJobsById(map);
      })
      .catch((e) => {
        if (!cancelled)
          setError(e instanceof ApiError ? e.message : "Failed to load activity.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [candidateId, activityVersion]);

  const handleUnsave = async (jobId: string) => {
    setSaved((prev) => prev.filter((j) => j.id !== jobId));
    await toggleSave(jobId);
  };

  return (
    <div className={styles.page}>
      <ActivityHeader />
      <main className={styles.main}>
        <h1 className={styles.title}>My Activity</h1>

        <div className={styles.tabs}>
          <button
            className={`${styles.tab} ${tab === "applications" ? styles.tabOn : ""}`}
            onClick={() => setTab("applications")}
          >
            Applications
            <span className={styles.badge}>{applications.length}</span>
          </button>
          <button
            className={`${styles.tab} ${tab === "saved" ? styles.tabOn : ""}`}
            onClick={() => setTab("saved")}
          >
            Saved
            <span className={styles.badge}>{saved.length}</span>
          </button>
        </div>

        {!candidateId ? (
          <EmptyState
            title="Nothing here yet"
            sub="Upload your résumé and start applying to see your activity."
            cta="Browse roles"
            onCta={() => navigate("/")}
          />
        ) : loading ? (
          <div className={styles.loading}>Loading…</div>
        ) : error ? (
          <EmptyState title="Couldn't load activity" sub={error} cta="Retry" onCta={notifyActivityChanged} />
        ) : tab === "applications" ? (
          applications.length === 0 ? (
            <EmptyState
              title="No applications yet"
              sub="When you apply to a role, it'll show up here with what you submitted."
              cta="Browse roles"
              onCta={() => navigate("/")}
            />
          ) : (
            <div className={styles.list}>
              {applications.map((app) => (
                <ApplicationCard
                  key={app.id}
                  app={app}
                  job={jobsById[app.job_id]}
                  open={expanded === app.id}
                  onToggle={() =>
                    setExpanded((cur) => (cur === app.id ? null : app.id))
                  }
                />
              ))}
            </div>
          )
        ) : saved.length === 0 ? (
          <EmptyState
            title="No saved roles"
            sub="Tap the heart on any role to keep it here for later."
            cta="Browse roles"
            onCta={() => navigate("/")}
          />
        ) : (
          <div className={styles.list}>
            {saved.map((job) => (
              <SavedCard
                key={job.id}
                job={job}
                onUnsave={() => handleUnsave(job.id)}
                onApply={() => setApplyJob(job)}
              />
            ))}
          </div>
        )}
      </main>

      {applyJob && (
        <ApplyDrawer
          job={applyJob}
          onClose={() => setApplyJob(null)}
          onApplied={() => {
            setApplyJob(null);
            setTab("applications");
            notifyActivityChanged();
          }}
        />
      )}
    </div>
  );
}

function ApplicationCard({
  app,
  job,
  open,
  onToggle,
}: {
  app: Application;
  job?: Job;
  open: boolean;
  onToggle: () => void;
}) {
  const title = job?.title ?? "Role";
  const meta = job ? jobMeta(job) : app.job_id;
  const links = [app.linkedin, app.github, ...app.other_links].filter(Boolean);

  return (
    <div className={styles.appCard}>
      <button className={styles.appHead} onClick={onToggle} aria-expanded={open}>
        <div className={styles.appLeft}>
          <div className={styles.avatar}>{initial(job?.company ?? "?")}</div>
          <div>
            <div className={styles.appTitle}>{title}</div>
            <div className={styles.appMeta}>{meta}</div>
          </div>
        </div>
        <div className={styles.appRight}>
          <Tag tone="teal">{humanize(app.status)}</Tag>
          <span className={styles.appDate}>Applied {shortDate(app.created_at)}</span>
          <span className={`${styles.caret} ${open ? styles.caretOpen : ""}`}>
            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden>
              <path
                d="M3 4.5L6 7.5l3-3"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
        </div>
      </button>

      {open && (
        <div className={styles.submitted}>
          <div className={styles.submittedLabel}>What you submitted</div>
          <dl className={styles.detailGrid}>
            <Detail term="Name" value={app.name} />
            <Detail term="Email" value={app.email} />
            {app.earliest_start && (
              <Detail term="Earliest start" value={prettyMonth(app.earliest_start)} />
            )}
            {links.length > 0 && (
              <Detail term="Links" value={links.join(" · ")} />
            )}
            <Detail
              term="Visa sponsorship"
              value={app.requires_visa ? "Required" : "Not required"}
            />
            {app.resume_name && (
              <Detail term="Applied with" value={app.resume_name} />
            )}
          </dl>
          {app.why_company && job && (
            <div className={styles.why}>
              <div className={styles.whyLabel}>Why {job.company}</div>
              <p className={styles.whyText}>{app.why_company}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SavedCard({
  job,
  onUnsave,
  onApply,
}: {
  job: Job;
  onUnsave: () => void;
  onApply: () => void;
}) {
  return (
    <div className={styles.savedCard}>
      <div className={styles.savedTop}>
        <div>
          <div className={styles.savedTitle}>{job.title}</div>
          <div className={styles.savedMeta}>{jobMeta(job)}</div>
          <div className={styles.savedTags}>
            <span className={styles.savedSalary}>
              {salaryRange(job.salary_min, job.salary_max)}
            </span>
            <Tag tone={workModeTone(job.work_mode)}>
              {workModeLabel(job.work_mode)}
            </Tag>
          </div>
        </div>
        <button
          className={styles.savedHeart}
          onClick={onUnsave}
          aria-label="Remove from saved"
        >
          <HeartFilled width={18} height={18} />
        </button>
      </div>
      <div className={styles.savedFoot}>
        <span className={styles.savedDate} />
        <button className={styles.applyBtn} onClick={onApply}>
          Apply
        </button>
      </div>
    </div>
  );
}

function Detail({ term, value }: { term: string; value: string }) {
  return (
    <>
      <dt className={styles.dt}>{term}</dt>
      <dd className={styles.dd}>{value}</dd>
    </>
  );
}

function EmptyState({
  title,
  sub,
  cta,
  onCta,
}: {
  title: string;
  sub: string;
  cta: string;
  onCta: () => void;
}) {
  return (
    <div className={styles.empty}>
      <p className={styles.emptyTitle}>{title}</p>
      <p className={styles.emptySub}>{sub}</p>
      <button className={styles.emptyCta} onClick={onCta}>
        {cta}
      </button>
    </div>
  );
}

// "2026-08" → "August 2026"
function prettyMonth(value: string): string {
  const [y, m] = value.split("-").map(Number);
  if (!y || !m) return value;
  return new Date(y, m - 1, 1).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });
}
