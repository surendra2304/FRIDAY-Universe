import type { Metadata, Viewport } from "next";
import { DM_Mono, Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

/* Reactor Deck edition (2026-11-14, rebuild #2): DM Mono is no longer
   just the numeral font — it is the console's display voice. Headings,
   labels, the wordmark and every readout speak in letterspaced mono
   over warm graphite; Inter carries prose and FRIDAY's replies. The
   Space Grotesk display face of the Aurora edition is gone. */
const dmMono = DM_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-dm-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FRIDAY — Reactor Deck",
  description:
    "Talk to FRIDAY continuously by voice, chat with the coordinator, and watch the ten-agent FRIDAY Universe fleet live.",
  applicationName: "FRIDAY",
};

export const viewport: Viewport = {
  themeColor: "#14100b",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${dmMono.variable}`}>{children}</body>
    </html>
  );
}
