import { CheckCircle } from "./icons";
import styles from "./LeftPane.module.css";

// The teal "Ranked for your résumé" banner shown once a résumé is uploaded.
export function PersonalizedBanner({
  resumeName,
  onStartOver,
}: {
  resumeName: string | null;
  onStartOver: () => void;
}) {
  return (
    <div className={styles.banner}>
      <div className={styles.bannerCheck}>
        <CheckCircle />
      </div>
      <div className={styles.bannerText}>
        <div className={styles.bannerTitle}>Ranked for your resume</div>
        {resumeName && <div className={styles.bannerSub}>{resumeName}</div>}
      </div>
      <button className={styles.startOver} onClick={onStartOver}>
        <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
          <path
            d="M3.5 8a4.5 4.5 0 104.5-4.5c-1.6 0-3 .8-3.8 2M4 3v2.5h2.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        Start over
      </button>
    </div>
  );
}
