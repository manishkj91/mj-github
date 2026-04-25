import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Inter",
          "sans-serif",
        ],
        serif: ["ui-serif", "Georgia", "serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        ink: {
          50: "#f7f7f6",
          100: "#eeeeec",
          200: "#d9d9d4",
          300: "#b6b6ad",
          400: "#84847a",
          500: "#5d5d54",
          600: "#3f3f38",
          700: "#2a2a25",
          800: "#1c1c19",
          900: "#0f0f0d",
        },
        accent: {
          DEFAULT: "#3f6df0",
          soft: "#eaf0ff",
        },
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up": "fadeUp 220ms ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
