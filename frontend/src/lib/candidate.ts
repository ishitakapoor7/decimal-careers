// The candidate identity is an opaque UUID. It is the durable key for a
// visitor's saves and applications, so it persists for the life of the browser
// profile and is NOT cleared by "Start over". Personalization (résumé-based
// ranking) is a separate, toggleable layer on top of this identity.
const ID_KEY = "decimal.candidate_id";
const RESUME_KEY = "decimal.resume_name";
const PERSONALIZED_KEY = "decimal.personalized";

// Return the stored candidate id, minting and persisting one on first use.
// The server also accepts this id on /upload-resume, so the same identity
// carries through to personalization.
export function getOrCreateCandidateId(): string {
  try {
    const existing = localStorage.getItem(ID_KEY);
    if (existing) return existing;
    const id = crypto.randomUUID();
    localStorage.setItem(ID_KEY, id);
    return id;
  } catch {
    // Storage unavailable (private mode): fall back to an in-memory id for this
    // session so saves/applies still function, just without persistence.
    return crypto.randomUUID();
  }
}

// Whether the browse list is currently ranked against an uploaded résumé.
export function getPersonalized(): boolean {
  try {
    return localStorage.getItem(PERSONALIZED_KEY) === "1";
  } catch {
    return false;
  }
}

export function setPersonalized(on: boolean): void {
  try {
    if (on) localStorage.setItem(PERSONALIZED_KEY, "1");
    else localStorage.removeItem(PERSONALIZED_KEY);
  } catch {
    /* ignore */
  }
}

// Remember the uploaded file's name purely for display ("backend_engineer.pdf
// · re-sorted by fit"). The résumé text itself lives server-side.
export function getResumeName(): string | null {
  try {
    return localStorage.getItem(RESUME_KEY);
  } catch {
    return null;
  }
}

export function setResumeName(name: string | null): void {
  try {
    if (name) localStorage.setItem(RESUME_KEY, name);
    else localStorage.removeItem(RESUME_KEY);
  } catch {
    /* ignore */
  }
}
