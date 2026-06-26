import { useRef } from "react";
import { UploadIcon } from "./icons";
import styles from "./LeftPane.module.css";

// The dashed coral hero card inviting a résumé upload (browse, pre-personalized).
export function UploadPrompt({
  onUpload,
  busy,
}: {
  onUpload: (file: File) => void;
  busy: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className={styles.uploadCard}>
      <div className={styles.uploadIcon}>
        <UploadIcon />
      </div>
      <div className={styles.uploadText}>
        <div className={styles.uploadTitle}>Find roles made for you</div>
        <div className={styles.uploadSub}>
          Drop your résumé and we'll surface your strongest matches first.
        </div>
      </div>
      <button
        className={styles.chooseFile}
        onClick={() => input.current?.click()}
        disabled={busy}
      >
        {busy ? "Reading…" : "Choose file"}
      </button>
      <input
        ref={input}
        type="file"
        accept=".pdf,.docx,.doc,.txt"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUpload(f);
          e.target.value = "";
        }}
      />
    </div>
  );
}
