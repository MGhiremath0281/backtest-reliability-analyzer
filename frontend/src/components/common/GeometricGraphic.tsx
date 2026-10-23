import React from 'react';

interface GeometricGraphicProps {
  className?: string;
}

export const GeometricGraphic: React.FC<GeometricGraphicProps> = ({ className = '' }) => {
  return (
    <div className={`relative overflow-hidden border border-black bg-white flex items-center justify-center ${className}`}>
      <svg
        viewBox="0 0 400 480"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full object-cover select-none"
      >
        {/* Soft decorative background cloud curves */}
        <path
          d="M260 20C340 40 400 120 390 220C380 320 320 380 330 460L400 480V0H260V20Z"
          fill="#eaf4f7"
        />
        <path
          d="M0 240C20 280 40 320 50 380C60 440 20 470 0 480V240Z"
          fill="#ff3b30"
          fillOpacity="0.85"
        />

        {/* Top Wireframe Network: Connecting Lines */}
        <path
          d="M80 60 C120 30 180 80 240 40 C280 20 320 70 340 120"
          stroke="#000000"
          strokeWidth="1.5"
          fill="none"
        />
        <path
          d="M100 120 C160 140 220 90 260 160 C290 200 320 180 360 210"
          stroke="#000000"
          strokeWidth="1.5"
          fill="none"
        />
        <path
          d="M190 60 L190 140"
          stroke="#000000"
          strokeWidth="1.5"
        />

        {/* Network Nodes (Black Rounded Rectangles) */}
        <rect x="70" y="45" width="30" height="30" rx="6" fill="#09090b" transform="rotate(15 70 45)" />
        <rect x="180" y="25" width="28" height="28" rx="6" fill="#09090b" transform="rotate(-10 180 25)" />
        <rect x="290" y="55" width="28" height="28" rx="6" fill="#09090b" transform="rotate(20 290 55)" />
        <rect x="110" y="115" width="32" height="32" rx="6" fill="#09090b" transform="rotate(-15 110 115)" />
        <rect x="235" y="110" width="30" height="30" rx="6" fill="#09090b" transform="rotate(12 235 110)" />

        {/* Devlab Iconic Red Triangle */}
        <polygon
          points="160,50 220,50 190,115"
          fill="#ff3b30"
        />
        {/* Subtle noise/texture overlay on triangle */}
        <polygon
          points="160,50 220,50 190,115"
          fill="url(#stipple-pattern)"
          opacity="0.35"
        />

        {/* Devlab Muted Blue Pill Toggle */}
        <g transform="translate(60, 180) rotate(-15)">
          <rect
            x="0"
            y="0"
            width="220"
            height="85"
            rx="42.5"
            fill="#4a8b9f"
          />
          {/* White circular toggle button */}
          <circle cx="165" cy="42.5" r="28" fill="#ffffff" />
          {/* Stipple texture on blue pill */}
          <rect
            x="0"
            y="0"
            width="220"
            height="85"
            rx="42.5"
            fill="url(#stipple-pattern)"
            opacity="0.25"
          />
        </g>

        {/* Devlab Big Black Arrow (pointing upward/forward) */}
        <g transform="translate(140, 270)">
          <path
            d="M50 0 L110 100 L75 90 L75 160 L25 160 L25 90 L-10 100 Z"
            fill="#09090b"
          />
          {/* Arrow subtle texture */}
          <path
            d="M50 0 L110 100 L75 90 L75 160 L25 160 L25 90 L-10 100 Z"
            fill="url(#stipple-pattern)"
            opacity="0.2"
          />
        </g>

        {/* Starburst Geometric Shapes (bottom right) */}
        <g transform="translate(320, 320)" opacity="0.6">
          {[0, 30, 60, 90, 120, 150].map((deg) => (
            <line
              key={deg}
              x1="0"
              y1="-18"
              x2="0"
              y2="18"
              stroke="#4a8b9f"
              strokeWidth="4"
              strokeLinecap="round"
              transform={`rotate(${deg})`}
            />
          ))}
        </g>
        <g transform="translate(350, 380)" opacity="0.45">
          {[0, 30, 60, 90, 120, 150].map((deg) => (
            <line
              key={deg}
              x1="0"
              y1="-14"
              x2="0"
              y2="14"
              stroke="#4a8b9f"
              strokeWidth="3.5"
              strokeLinecap="round"
              transform={`rotate(${deg})`}
            />
          ))}
        </g>

        {/* Pattern Definition for subtle grain/texture */}
        <defs>
          <pattern id="stipple-pattern" width="6" height="6" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="0.8" fill="#ffffff" />
            <circle cx="4" cy="4" r="0.8" fill="#ffffff" />
            <circle cx="4" cy="1" r="0.5" fill="#000000" opacity="0.2" />
          </pattern>
        </defs>
      </svg>
    </div>
  );
};
