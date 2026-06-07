import type { Config } from "tailwindcss"

const config: Config = {
  darkMode: ["class"],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        surface: "hsl(var(--surface))",
        "surface-2": "hsl(var(--surface-2))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
          glow: "hsl(var(--primary-glow))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        bull: {
          DEFAULT: "hsl(var(--bull))",
          muted: "hsl(var(--bull-muted))",
        },
        bear: {
          DEFAULT: "hsl(var(--bear))",
          muted: "hsl(var(--bear-muted))",
        },
        gold: {
          DEFAULT: "hsl(var(--gold))",
          muted: "hsl(var(--gold-muted))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      backgroundImage: {
        "gradient-primary": "var(--gradient-primary)",
        "gradient-surface": "var(--gradient-surface)",
        "gradient-card": "var(--gradient-card)",
        "gradient-bull": "var(--gradient-bull)",
        "gradient-bear": "var(--gradient-bear)",
      },
      boxShadow: {
        "card": "var(--shadow-card)",
        "glow": "var(--shadow-glow)",
        "glow-sm": "var(--shadow-glow-sm)",
        "gold": "var(--shadow-gold)",
      },
      keyframes: {
        "accordion-down": { from: { height: "0" }, to: { height: "var(--radix-accordion-content-height)" } },
        "accordion-up": { from: { height: "var(--radix-accordion-content-height)" }, to: { height: "0" } },
        "fade-in": { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        "fade-up": { from: { opacity: "0", transform: "translateY(12px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        "slide-in": { from: { opacity: "0", transform: "translateX(-12px)" }, to: { opacity: "1", transform: "translateX(0)" } },
        "pulse-dot": { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.4" } },
        "ticker": { from: { transform: "translateX(0)" }, to: { transform: "translateX(-50%)" } },
        "shimmer": { from: { backgroundPosition: "-200% 0" }, to: { backgroundPosition: "200% 0" } },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fade-in 0.4s ease-out",
        "fade-up": "fade-up 0.35s ease-out",
        "slide-in": "slide-in 0.3s ease-out",
        "pulse-dot": "pulse-dot 1.5s ease-in-out infinite",
        "ticker": "ticker 40s linear infinite",
        "shimmer": "shimmer 2s linear infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}

export default config
