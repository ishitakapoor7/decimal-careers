import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { Job } from "../api/types";
import { ApplyDrawer } from "../components/ApplyDrawer";
import { BrowseHeader } from "../components/Header";
import { EMPTY_FILTERS, FilterBar, type FilterState } from "../components/FilterBar";
import { JobCard, type MatchInfo } from "../components/JobCard";
import type { Fit } from "../api/types";
import { JobDetail } from "../components/JobDetail";
import type { Option } from "../components/Dropdown";
import { Pagination } from "../components/Pagination";
import { PersonalizedBanner } from "../components/PersonalizedBanner";
import { UploadPrompt } from "../components/UploadPrompt";
import { useCandidate } from "../state/CandidateContext";
import styles from "./BrowsePage.module.css";

const LIMIT = 20;

// The backend now computes a calibrated fit tier per role (cosine × seniority ×
// education) and explains it. Map that tier to the card/detail label + tone, and
// carry the reasons/skills through for JobDetail to render.
const TIER_TO_MATCH: Record<string, { label: string; tone: MatchInfo["tone"] }> = {
  strong: { label: "Strong match", tone: "teal" },
  good: { label: "Good match", tone: "gold" },
  possible: { label: "Possible match", tone: "neutral" },
};

function matchFromFit(fit: Fit): MatchInfo {
  const base = TIER_TO_MATCH[fit.tier] ?? TIER_TO_MATCH.possible;
  return {
    ...base,
    reasons: fit.reasons,
    matchedRequired: fit.matched_required,
    matchedPreferred: fit.matched_preferred,
  };
}

// Fallback for a candidate that predates the stored profile (no per-role fit):
// label by position, since the ranking itself is still real.
function matchForRank(globalRank: number, total: number): MatchInfo | undefined {
  if (total <= 0) return undefined;
  const frac = globalRank / total;
  if (frac < 0.2) return { label: "Strong match", tone: "teal" };
  if (frac < 0.6) return { label: "Good match", tone: "gold" };
  return { label: "Possible match", tone: "neutral" };
}

// Prefer the backend's calibrated, explainable fit; fall back to position.
function matchFor(job: Job, globalRank: number, total: number): MatchInfo | undefined {
  return job.fit ? matchFromFit(job.fit) : matchForRank(globalRank, total);
}

export function BrowsePage() {
  const navigate = useNavigate();
  const {
    candidateId,
    personalized,
    resumeName,
    uploadResume,
    startOver,
    isSaved,
    toggleSave,
    isApplied,
  } = useCandidate();

  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [offset, setOffset] = useState(0);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [applyJob, setApplyJob] = useState<Job | null>(null);

  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Accumulate distinct locations across fetches to populate the Location filter.
  const [locationOptions, setLocationOptions] = useState<Option[]>([]);

  // Map the location filter ("city|state") back into the API's exact-match params.
  const apiFilters = useMemo(() => {
    const loc = filters.location[0];
    const [city, state] = loc ? loc.split("|") : [undefined, undefined];
    return {
      team: filters.team,
      seniority_level: filters.seniority_level,
      employment_type: filters.employment_type,
      work_mode: filters.work_mode,
      city,
      state_region: state,
    };
  }, [filters]);

  // Only rank against the résumé when personalization is on. "Start over" flips
  // this off without losing the candidate identity (saves/applications persist).
  const rankingId = personalized ? candidateId : null;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .listJobs({ filters: apiFilters, candidateId: rankingId, limit: LIMIT, offset })
      .then((page) => {
        if (cancelled) return;
        setJobs(page.items);
        setTotal(page.total);
        setSelectedId(page.items[0]?.id ?? null);
        setLocationOptions((prev) => {
          const seen = new Map(prev.map((o) => [o.value, o]));
          for (const j of page.items) {
            if (j.work_mode === "remote") continue;
            const value = `${j.city}|${j.state_region}`;
            if (!seen.has(value))
              seen.set(value, { value, label: `${j.city}, ${j.state_region}` });
          }
          return [...seen.values()].sort((a, b) => a.label.localeCompare(b.label));
        });
      })
      .catch((e) => {
        if (!cancelled)
          setError(e instanceof ApiError ? e.message : "Failed to load roles.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiFilters, rankingId, offset]);

  const handleUpload = async (file: File) => {
    setUploadBusy(true);
    setUploadError(null);
    try {
      await uploadResume(file);
      setOffset(0); // re-rank from the top
    } catch (e) {
      setUploadError(
        e instanceof ApiError ? e.message : "Couldn't read that file.",
      );
    } finally {
      setUploadBusy(false);
    }
  };

  const onFiltersChange = (next: FilterState) => {
    setFilters(next);
    setOffset(0);
  };

  const selected = jobs.find((j) => j.id === selectedId) ?? null;
  const selectedIndex = jobs.findIndex((j) => j.id === selectedId);
  const detailMatch =
    personalized && selected && selectedIndex >= 0
      ? matchFor(selected, offset + selectedIndex, total)
      : undefined;

  const totalLabel = `${total.toLocaleString()} role${total === 1 ? "" : "s"}`;

  return (
    <div className={styles.page}>
      <BrowseHeader onUpload={handleUpload} />
      <FilterBar
        filters={filters}
        onChange={onFiltersChange}
        locationOptions={locationOptions}
        totalLabel={totalLabel}
      />

      <div className={styles.split}>
        <div className={styles.left}>
          <div className={styles.list}>
            {personalized ? (
              <PersonalizedBanner
                resumeName={resumeName}
                total={total}
                onStartOver={startOver}
              />
            ) : (
              <UploadPrompt onUpload={handleUpload} busy={uploadBusy} />
            )}

            {uploadError && <div className={styles.inlineError}>{uploadError}</div>}

            {loading ? (
              <ListSkeleton />
            ) : error ? (
              <div className={styles.stateBox}>
                <p>{error}</p>
                <button
                  className={styles.retry}
                  onClick={() => setOffset((o) => o)}
                >
                  Retry
                </button>
              </div>
            ) : jobs.length === 0 ? (
              <div className={styles.stateBox}>
                <p className={styles.emptyTitle}>No roles match those filters</p>
                <p className={styles.emptySub}>
                  Try removing a filter to widen your search.
                </p>
                <button
                  className={styles.retry}
                  onClick={() => onFiltersChange(EMPTY_FILTERS)}
                >
                  Clear filters
                </button>
              </div>
            ) : (
              jobs.map((job, i) => (
                <JobCard
                  key={job.id}
                  job={job}
                  selected={job.id === selectedId}
                  saved={isSaved(job.id)}
                  match={
                    personalized ? matchFor(job, offset + i, total) : undefined
                  }
                  onSelect={() => setSelectedId(job.id)}
                  onToggleSave={() => toggleSave(job.id)}
                />
              ))
            )}
          </div>

          {!loading && !error && jobs.length > 0 && (
            <Pagination
              total={total}
              limit={LIMIT}
              offset={offset}
              onOffset={setOffset}
            />
          )}
        </div>

        {selected ? (
          <JobDetail
            job={selected}
            saved={isSaved(selected.id)}
            applied={isApplied(selected.id)}
            match={detailMatch}
            onApply={() => setApplyJob(selected)}
            onToggleSave={() => toggleSave(selected.id)}
          />
        ) : (
          <div className={styles.detailEmpty}>
            {loading ? "" : "Select a role to see the details."}
          </div>
        )}
      </div>

      {applyJob && (
        <ApplyDrawer
          job={applyJob}
          onClose={() => setApplyJob(null)}
          onApplied={() => {
            setApplyJob(null);
            navigate("/activity");
          }}
        />
      )}
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className={styles.skeletonWrap} aria-hidden>
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className={styles.skeleton} />
      ))}
    </div>
  );
}
