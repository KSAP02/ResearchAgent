// Minimal stroke icons (24x24 grid), no icon library needed.
import type { SVGProps } from "react";

function Svg(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={18}
      height={18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    />
  );
}

export const HomeIcon = () => (
  <Svg>
    <path d="M3 10.5 12 3l9 7.5" />
    <path d="M5 9.5V20h14V9.5" />
  </Svg>
);

export const SlidersIcon = () => (
  <Svg>
    <path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" />
    <circle cx="16" cy="6" r="2" />
    <circle cx="10" cy="12" r="2" />
    <circle cx="18" cy="18" r="2" />
  </Svg>
);

export const AdminIcon = () => (
  <Svg>
    <path d="M12 3 4.5 6v5.5c0 4.3 3.1 8.2 7.5 9.5 4.4-1.3 7.5-5.2 7.5-9.5V6L12 3Z" />
    <path d="M9.5 12l1.8 1.8 3.4-3.6" />
  </Svg>
);

export const PanelIcon = () => (
  <Svg>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2.5" />
    <path d="M9 4.5v15" />
  </Svg>
);

export const RunsIcon = () => (
  <Svg>
    <path d="M4 6h16M4 12h10M4 18h13" />
    <circle cx="19" cy="12" r="1.6" />
  </Svg>
);

export const ArrowUpIcon = () => (
  <Svg>
    <path d="M12 19V5M6 11l6-6 6 6" />
  </Svg>
);
