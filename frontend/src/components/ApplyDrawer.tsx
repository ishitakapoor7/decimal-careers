import { useMemo, useState } from "react";
import { ApiError } from "../api/client";
import { api } from "../api/client";
import type { Job } from "../api/types";
import { jobMeta } from "../lib/format";
import { useCandidate } from "../state/CandidateContext";
import {
  CheckCircle,
  CloseIcon,
  FileIcon,
  PlusIcon,
  UploadIconSmall,
} from "./icons";
import styles from "./ApplyDrawer.module.css";

// A pragmatic email shape check — not RFC-perfect, but rejects the common
// "jumbled letters" case (no @, no domain, spaces).
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Max length for the "why this company" blurb.
const WHY_MAX = 300;

// Parse a user-typed link into a URL, tolerating a missing scheme
// ("linkedin.com/in/you" → "https://linkedin.com/in/you"). Returns null when
// it doesn't resemble a real web address (no dotted host, spaces, etc.).
function normalizeUrl(value: string): URL | null {
  const v = value.trim();
  if (!v) return null;
  try {
    const url = new URL(v.includes("://") ? v : `https://${v}`);
    return url.hostname.includes(".") ? url : null;
  } catch {
    return null;
  }
}

// True when the URL's host is `host` or a subdomain of it.
function isHost(url: URL | null, host: string): boolean {
  if (!url) return false;
  return url.hostname === host || url.hostname.endsWith(`.${host}`);
}

// Next 12 months as {value: "2026-08", label: "August 2026"} for the start dropdown.
function startMonthOptions(): { value: string; label: string }[] {
  const out: { value: string; label: string }[] = [];
  const now = new Date();
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1);
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const label = d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
    out.push({ value, label });
  }
  return out;
}

type FieldErrors = Partial<
  Record<
    | "resume"
    | "name"
    | "email"
    | "earliestStart"
    | "linkedin"
    | "links"
    | "whyCompany",
    string
  >
>;

export function ApplyDrawer({
  job,
  onClose,
  onApplied,
}: {
  job: Job;
  onClose: () => void;
  onApplied: () => void;
}) {
  const { candidateId, resumeName: globalResume, markApplied } = useCandidate();
  const months = useMemo(startMonthOptions, []);

  // The application's résumé is scoped to THIS application: it defaults to the
  // personalization résumé's filename (if any) but "Replace"/"Upload" only
  // changes this local filename — it never re-uploads or re-ranks the global list.
  const [resumeName, setResumeName] = useState<string>(globalResume ?? "");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [earliestStart, setEarliestStart] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [github, setGithub] = useState("");
  const [otherLinks, setOtherLinks] = useState<string[]>([]);
  const [requiresVisa, setRequiresVisa] = useState(false);
  const [whyCompany, setWhyCompany] = useState("");

  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // Clear a single field's error as the user corrects it.
  const clearError = (key: keyof FieldErrors) =>
    setErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });

  const pickResume = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf,.docx,.doc,.txt";
    input.onchange = () => {
      const f = input.files?.[0];
      if (f) {
        setResumeName(f.name); // filename only — no upload, no global re-rank
        clearError("resume");
      }
    };
    input.click();
  };

  const validate = (): FieldErrors => {
    const e: FieldErrors = {};
    if (!resumeName) e.resume = "Please attach your résumé.";
    if (!name.trim()) e.name = "Your name is required.";
    if (!email.trim()) e.email = "Your email is required.";
    else if (!EMAIL_RE.test(email.trim()))
      e.email = "Enter a valid email address (e.g. you@example.com).";
    if (!earliestStart) e.earliestStart = "Select your earliest start date.";

    if (!linkedin.trim()) e.linkedin = "Your LinkedIn is required.";
    else if (!isHost(normalizeUrl(linkedin), "linkedin.com"))
      e.linkedin = "Enter a valid LinkedIn URL (e.g. linkedin.com/in/you).";

    // GitHub and the extra links are optional, but anything typed must be a
    // real URL (and GitHub must actually point at github.com).
    if (github.trim() && !isHost(normalizeUrl(github), "github.com"))
      e.links = "Enter a valid GitHub URL (e.g. github.com/you).";
    else if (otherLinks.some((l) => l.trim() && !normalizeUrl(l)))
      e.links = "Each additional link must be a valid URL (including https://).";

    if (!whyCompany.trim())
      e.whyCompany = `Tell ${job.company} why you want to work there.`;
    else if (whyCompany.trim().length > WHY_MAX)
      e.whyCompany = `Keep this under ${WHY_MAX} characters — you're at ${whyCompany.trim().length}.`;

    return e;
  };

  const submit = async () => {
    setSubmitError(null);
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    try {
      await api.apply({
        candidate_id: candidateId,
        job_id: job.id,
        name: name.trim(),
        email: email.trim(),
        earliest_start: earliestStart,
        linkedin: linkedin.trim(),
        github: github.trim(),
        other_links: otherLinks.map((l) => l.trim()).filter(Boolean),
        requires_visa: requiresVisa,
        why_company: whyCompany.trim(),
        resume_name: resumeName,
      });
      markApplied(job.id);
      setDone(true);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <aside
        className={styles.drawer}
        role="dialog"
        aria-modal="true"
        aria-label={`Apply to ${job.title}`}
        onClick={(e) => e.stopPropagation()}
      >
        {done ? (
          <div className={styles.successWrap}>
            <div className={styles.successIcon}>
              <CheckCircle width={26} height={26} />
            </div>
            <h2 className={styles.successTitle}>Application sent</h2>
            <p className={styles.successBody}>
              Your application to <strong>{job.title}</strong> at {job.company} is
              in. You can review what you submitted under My Activity.
            </p>
            <div className={styles.successActions}>
              <button className={styles.primary} onClick={onApplied}>
                View in My Activity
              </button>
              <button className={styles.ghost} onClick={onClose}>
                Keep browsing
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className={styles.header}>
              <div>
                <div className={styles.eyebrow}>Apply to</div>
                <h2 className={styles.headerTitle}>{job.title}</h2>
                <div className={styles.headerMeta}>{jobMeta(job)}</div>
              </div>
              <button className={styles.close} onClick={onClose} aria-label="Close">
                <CloseIcon />
              </button>
            </div>

            <div className={styles.body}>
              <Field label="Résumé" required error={errors.resume}>
                {resumeName ? (
                  <div className={styles.resumeRow}>
                    <span className={styles.resumeIcon}>
                      <FileIcon />
                    </span>
                    <div className={styles.resumeInfo}>
                      <div className={styles.resumeName}>{resumeName}</div>
                      <div className={styles.resumeState}>Attached to this application</div>
                    </div>
                    <button className={styles.replace} onClick={pickResume}>
                      Replace
                    </button>
                  </div>
                ) : (
                  <button className={styles.resumeDrop} onClick={pickResume}>
                    <UploadIconSmall />
                    Upload your résumé (PDF or DOCX)
                  </button>
                )}
              </Field>

              <Field label="Full name" required error={errors.name}>
                <input
                  className={inputClass(styles, errors.name)}
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    clearError("name");
                  }}
                  placeholder="Your name"
                />
              </Field>

              <Field label="Email" required error={errors.email}>
                <input
                  className={inputClass(styles, errors.email)}
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    clearError("email");
                  }}
                  placeholder="you@example.com"
                />
              </Field>

              <Field label="Earliest start date" required error={errors.earliestStart}>
                <select
                  className={inputClass(styles, errors.earliestStart)}
                  value={earliestStart}
                  onChange={(e) => {
                    setEarliestStart(e.target.value);
                    clearError("earliestStart");
                  }}
                >
                  <option value="">Select a month</option>
                  {months.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="LinkedIn" required error={errors.linkedin}>
                <input
                  className={inputClass(styles, errors.linkedin)}
                  value={linkedin}
                  onChange={(e) => {
                    setLinkedin(e.target.value);
                    clearError("linkedin");
                  }}
                  placeholder="linkedin.com/in/you"
                />
              </Field>

              <Field label="GitHub & other links" error={errors.links}>
                <input
                  className={inputClass(styles, errors.links)}
                  value={github}
                  onChange={(e) => {
                    setGithub(e.target.value);
                    clearError("links");
                  }}
                  placeholder="github.com/you"
                />
                {otherLinks.map((link, i) => (
                  <input
                    key={i}
                    className={styles.input}
                    value={link}
                    onChange={(e) => {
                      setOtherLinks((prev) =>
                        prev.map((l, idx) => (idx === i ? e.target.value : l)),
                      );
                      clearError("links");
                    }}
                    placeholder="https://"
                  />
                ))}
                <button
                  className={styles.addLink}
                  onClick={() => setOtherLinks((prev) => [...prev, ""])}
                >
                  <PlusIcon />
                  Add another link
                </button>
              </Field>

              <Field label="Do you require visa sponsorship?" required>
                <div className={styles.toggle}>
                  <button
                    className={`${styles.toggleBtn} ${!requiresVisa ? styles.toggleOn : ""}`}
                    onClick={() => setRequiresVisa(false)}
                  >
                    No
                  </button>
                  <button
                    className={`${styles.toggleBtn} ${requiresVisa ? styles.toggleOn : ""}`}
                    onClick={() => setRequiresVisa(true)}
                  >
                    Yes
                  </button>
                </div>
              </Field>

              <Field
                label={`Why do you want to work at ${job.company}?`}
                required
                error={errors.whyCompany}
              >
                <textarea
                  className={
                    errors.whyCompany
                      ? `${styles.textarea} ${styles.inputError}`
                      : styles.textarea
                  }
                  value={whyCompany}
                  onChange={(e) => {
                    setWhyCompany(e.target.value);
                    clearError("whyCompany");
                  }}
                  placeholder="Tell the team what draws you to this role…"
                  rows={4}
                />
                <div
                  className={`${styles.charCount} ${
                    whyCompany.trim().length > WHY_MAX ? styles.charCountOver : ""
                  }`}
                >
                  {whyCompany.trim().length}/{WHY_MAX}
                </div>
              </Field>

              {submitError && <div className={styles.error}>{submitError}</div>}
            </div>

            <div className={styles.footer}>
              <button className={styles.ghost} onClick={onClose}>
                Cancel
              </button>
              <button className={styles.primary} onClick={submit} disabled={submitting}>
                {submitting ? "Submitting…" : "Submit application"}
              </button>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}

function inputClass(s: typeof styles, error?: string): string {
  return error ? `${s.input} ${s.inputError}` : s.input;
}

function Field({
  label,
  required,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={styles.field}>
      <label className={styles.label}>
        {label}
        {required && <span className={styles.req}>*</span>}
      </label>
      {children}
      {error && <div className={styles.fieldError}>{error}</div>}
    </div>
  );
}
