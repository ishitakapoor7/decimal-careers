import { useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, HeartOutline, UploadIconSmall } from "./icons";
import styles from "./Header.module.css";

function Logo() {
  return (
    <Link to="/" className={styles.brand} aria-label="decimal careers — home">
      <span className={styles.logoMark}>
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
          <path
            d="M8 13.3l-.9-.8C4 9.7 2 7.9 2 5.7 2 4 3.3 2.7 5 2.7c1 0 1.9.5 2.5 1.2l.5.6.5-.6c.6-.7 1.5-1.2 2.5-1.2 1.7 0 3 1.3 3 3 0 2.2-2 4-4.1 6.8l-.9.8z"
            fill="#fff"
          />
        </svg>
      </span>
      <span className={styles.wordmark}>decimal</span>
      <span className={styles.sub}>careers</span>
    </Link>
  );
}

// Browse-page header: brand + My Activity link + Upload résumé.
export function BrowseHeader({
  onUpload,
}: {
  onUpload: (file: File) => void;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  return (
    <header className={styles.bar}>
      <Logo />
      <div className={styles.actions}>
        <Link to="/activity" className={styles.navLink}>
          <HeartOutline width={15} height={15} />
          My Activity
        </Link>
        <button
          className={styles.uploadBtn}
          onClick={() => fileInput.current?.click()}
        >
          <UploadIconSmall />
          Upload resume
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".pdf,.docx,.doc,.txt"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            e.target.value = ""; // allow re-selecting the same file
          }}
        />
      </div>
    </header>
  );
}

// Activity-page header: brand + a single "Browse roles" button back to browse.
export function ActivityHeader() {
  const navigate = useNavigate();
  return (
    <header className={styles.bar}>
      <Logo />
      <button className={styles.uploadBtn} onClick={() => navigate("/")}>
        <ArrowLeft />
        Browse roles
      </button>
    </header>
  );
}
