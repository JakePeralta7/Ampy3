/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          app: "hsl(var(--bg-app) / <alpha-value>)",
          surface: "hsl(var(--bg-surface) / <alpha-value>)",
          muted: "hsl(var(--bg-muted) / <alpha-value>)",
          inset: "hsl(var(--bg-inset) / <alpha-value>)",
        },
        fg: {
          DEFAULT: "hsl(var(--fg-default) / <alpha-value>)",
          muted: "hsl(var(--fg-muted) / <alpha-value>)",
          subtle: "hsl(var(--fg-subtle) / <alpha-value>)",
          "on-accent": "hsl(var(--fg-on-accent) / <alpha-value>)",
        },
        border: {
          DEFAULT: "hsl(var(--border-default) / <alpha-value>)",
          strong: "hsl(var(--border-strong) / <alpha-value>)",
          focus: "hsl(var(--border-focus) / <alpha-value>)",
        },
        accent: {
          50: "hsl(var(--accent-50) / <alpha-value>)",
          100: "hsl(var(--accent-100) / <alpha-value>)",
          500: "hsl(var(--accent-500) / <alpha-value>)",
          600: "hsl(var(--accent-600) / <alpha-value>)",
          700: "hsl(var(--accent-700) / <alpha-value>)",
          fg: "hsl(var(--accent-fg) / <alpha-value>)",
        },
        danger: {
          500: "hsl(var(--danger-500) / <alpha-value>)",
          fg: "hsl(var(--danger-fg) / <alpha-value>)",
        },
        success: { 500: "hsl(var(--success-500) / <alpha-value>)" },
        warn: { 500: "hsl(var(--warn-500) / <alpha-value>)" },
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      transitionDuration: {
        fast: "var(--motion-fast)",
        base: "var(--motion-base)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
