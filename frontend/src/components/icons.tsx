// Inline SVGs lifted from the Paper design so strokes/paths match exactly.
// All accept standard SVG props (size via width/height, color via stroke/fill).
import type { SVGProps } from "react";

export function HeartOutline(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" {...props}>
      <path
        d="M8 13.5l-1-.9C4 9.9 2 8.1 2 5.9 2 4.2 3.3 3 5 3c.9 0 1.8.4 2.4 1.1L8 4.8l.6-.7C9.2 3.4 10.1 3 11 3c1.7 0 3 1.2 3 2.9 0 2.2-2 4-5 6.7l-1 .9z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function HeartFilled(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" {...props}>
      <path
        d="M8 13.3l-.9-.8C4 9.7 2 7.9 2 5.7 2 4 3.3 2.7 5 2.7c1 0 1.9.5 2.5 1.2l.5.6.5-.6c.6-.7 1.5-1.2 2.5-1.2 1.7 0 3 1.3 3 3 0 2.2-2 4-4.1 6.8l-.9.8z"
        fill="currentColor"
      />
    </svg>
  );
}

export function UploadIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...props}>
      <path
        d="M12 15V4M12 4L8 8M12 4l4 4M5 16v2.5A1.5 1.5 0 006.5 20h11a1.5 1.5 0 001.5-1.5V16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function UploadIconSmall(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" {...props}>
      <path
        d="M8 10.5V2.5M8 2.5L5 5.5M8 2.5l3 3M3 11v1.5a1 1 0 001 1h8a1 1 0 001-1V11"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Chevron(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" {...props}>
      <path
        d="M3 4.5L6 7.5l3-3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ArrowLeft(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" {...props}>
      <path
        d="M10 3L5 8l5 5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ChevronPage({
  dir,
  ...props
}: { dir: "left" | "right" } & SVGProps<SVGSVGElement>) {
  return (
    <svg width="13" height="13" viewBox="0 0 12 12" {...props}>
      <path
        d={dir === "left" ? "M7.5 3L4.5 6l3 3" : "M4.5 3l3 3-3 3"}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function CheckCircle(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" {...props}>
      <path
        d="M4 8.2l2.5 2.4L12 5.3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function FileIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" {...props}>
      <path
        d="M5 2.5h6L15.5 7v9.5a1 1 0 01-1 1h-9a1 1 0 01-1-1v-13a1 1 0 011-1z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path
        d="M11 2.5V7h4.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function CloseIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" {...props}>
      <path
        d="M4 4l8 8M12 4l-8 8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function PlusIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" {...props}>
      <path
        d="M7 2.5v9M2.5 7h9"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}
