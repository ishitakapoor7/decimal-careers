import { ChevronPage } from "./icons";
import styles from "./LeftPane.module.css";

// Page numbers derived from total/limit/offset. Keeps a small window of pages.
export function Pagination({
  total,
  limit,
  offset,
  onOffset,
}: {
  total: number;
  limit: number;
  offset: number;
  onOffset: (next: number) => void;
}) {
  const pageCount = Math.max(1, Math.ceil(total / limit));
  const current = Math.floor(offset / limit); // 0-based
  if (pageCount <= 1) {
    return (
      <div className={styles.pagination}>
        <span className={styles.range}>
          Showing {total === 0 ? 0 : 1}–{total} of {total.toLocaleString()}
        </span>
      </div>
    );
  }

  // Window of up to 3 page buttons around the current page.
  const start = Math.max(0, Math.min(current - 1, pageCount - 3));
  const pages = Array.from({ length: Math.min(3, pageCount) }, (_, i) => start + i);

  const rangeStart = offset + 1;
  const rangeEnd = Math.min(offset + limit, total);

  return (
    <div className={styles.pagination}>
      <span className={styles.range}>
        Showing {rangeStart}–{rangeEnd} of {total.toLocaleString()}
      </span>
      <div className={styles.pageBtns}>
        <button
          className={styles.pageNav}
          disabled={current === 0}
          onClick={() => onOffset((current - 1) * limit)}
          aria-label="Previous page"
        >
          <ChevronPage dir="left" />
        </button>
        {pages.map((p) => (
          <button
            key={p}
            className={`${styles.pageNum} ${p === current ? styles.pageOn : ""}`}
            onClick={() => onOffset(p * limit)}
          >
            {p + 1}
          </button>
        ))}
        <button
          className={styles.pageNav}
          disabled={current >= pageCount - 1}
          onClick={() => onOffset((current + 1) * limit)}
          aria-label="Next page"
        >
          <ChevronPage dir="right" />
        </button>
      </div>
    </div>
  );
}
