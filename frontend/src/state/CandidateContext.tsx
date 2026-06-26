import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api/client";
import {
  getOrCreateCandidateId,
  getPersonalized,
  getResumeName,
  setPersonalized as persistPersonalized,
  setResumeName as persistResumeName,
} from "../lib/candidate";

interface CandidateState {
  /** Durable identity — always present; the key for saves and applications. */
  candidateId: string;
  /** Whether the browse list is ranked against an uploaded résumé. */
  personalized: boolean;
  resumeName: string | null;
  savedIds: Set<string>;
  appliedIds: Set<string>;
  /** Upload (or replace) the personalization résumé; turns on ranking. */
  uploadResume: (file: File) => Promise<void>;
  /** Stop résumé ranking. Keeps identity, saves, and applications intact. */
  startOver: () => void;
  isSaved: (jobId: string) => boolean;
  toggleSave: (jobId: string) => Promise<void>;
  isApplied: (jobId: string) => boolean;
  markApplied: (jobId: string) => void;
  /** Bump when applications/saves change so views can refetch. */
  activityVersion: number;
  notifyActivityChanged: () => void;
}

const Ctx = createContext<CandidateState | null>(null);

export function CandidateProvider({ children }: { children: ReactNode }) {
  // Identity is minted once and never changes for the life of the browser
  // profile, so saves/applies always have a stable key — even before (and
  // after) any résumé upload.
  const [candidateId] = useState<string>(() => getOrCreateCandidateId());
  const [personalized, setPers] = useState<boolean>(() => getPersonalized());
  const [resumeName, setName] = useState<string | null>(() => getResumeName());
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [appliedIds, setAppliedIds] = useState<Set<string>>(new Set());
  const [activityVersion, setActivityVersion] = useState(0);

  // Hydrate the saved + applied sets for this identity so hearts and "Applied"
  // states render correctly. Keyed on the stable candidateId, so this survives
  // "Start over" (which only toggles personalization, not identity).
  useEffect(() => {
    let cancelled = false;
    api
      .listSaved(candidateId)
      .then((res) => {
        if (!cancelled) setSavedIds(new Set(res.items.map((j) => j.id)));
      })
      .catch(() => {
        /* a failed hydrate just leaves hearts empty; not fatal */
      });
    api
      .listApplications(candidateId)
      .then((res) => {
        if (!cancelled) setAppliedIds(new Set(res.items.map((a) => a.job_id)));
      })
      .catch(() => {
        /* non-fatal */
      });
    return () => {
      cancelled = true;
    };
  }, [candidateId, activityVersion]);

  const uploadResume = useCallback(
    async (file: File) => {
      // Reuse the durable id so personalization attaches to this same identity.
      await api.uploadResume(file, candidateId);
      persistResumeName(file.name);
      persistPersonalized(true);
      setName(file.name);
      setPers(true);
    },
    [candidateId],
  );

  // "Start over" turns OFF résumé ranking but preserves identity, saves, and
  // applications. We simply stop sending candidate_id to /jobs (see BrowsePage);
  // the résumé still exists server-side but no longer drives the browse list.
  const startOver = useCallback(() => {
    persistPersonalized(false);
    persistResumeName(null);
    setPers(false);
    setName(null);
  }, []);

  const isSaved = useCallback((jobId: string) => savedIds.has(jobId), [savedIds]);

  const toggleSave = useCallback(
    async (jobId: string) => {
      const currentlySaved = savedIds.has(jobId);
      // Optimistic flip; revert if the request fails.
      setSavedIds((prev) => {
        const next = new Set(prev);
        if (currentlySaved) next.delete(jobId);
        else next.add(jobId);
        return next;
      });
      try {
        if (currentlySaved) await api.unsaveJob(candidateId, jobId);
        else await api.saveJob(candidateId, jobId);
        setActivityVersion((v) => v + 1);
      } catch {
        setSavedIds((prev) => {
          const next = new Set(prev);
          if (currentlySaved) next.add(jobId);
          else next.delete(jobId);
          return next;
        });
      }
    },
    [candidateId, savedIds],
  );

  const isApplied = useCallback(
    (jobId: string) => appliedIds.has(jobId),
    [appliedIds],
  );

  const markApplied = useCallback((jobId: string) => {
    setAppliedIds((prev) => new Set(prev).add(jobId));
    setActivityVersion((v) => v + 1);
  }, []);

  const notifyActivityChanged = useCallback(
    () => setActivityVersion((v) => v + 1),
    [],
  );

  const value = useMemo<CandidateState>(
    () => ({
      candidateId,
      personalized,
      resumeName,
      savedIds,
      appliedIds,
      uploadResume,
      startOver,
      isSaved,
      toggleSave,
      isApplied,
      markApplied,
      activityVersion,
      notifyActivityChanged,
    }),
    [
      candidateId,
      personalized,
      resumeName,
      savedIds,
      appliedIds,
      uploadResume,
      startOver,
      isSaved,
      toggleSave,
      isApplied,
      markApplied,
      activityVersion,
      notifyActivityChanged,
    ],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCandidate(): CandidateState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCandidate must be used within CandidateProvider");
  return ctx;
}
