import type { Metadata, Viewport } from "next";
import { DM_Mono, Inter, Rajdhani } from "next/font/google";
import "./globals.css";

/* TASK-WEB-001 (2026-11-15) — type system for the from-scratch
   redesign: Rajdhani carries the display voice (wide, technical,
   cinematic — headings, the wordmark, navigation), Inter carries
   prose and FRIDAY's replies, DM Mono is reserved for numerals and
   machine readouts. */
const rajdhani = Rajdhani({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-rajdhani",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const dmMono = DM_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-dm-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FRIDAY",
  description:
    "Talk to FRIDAY. One voice line, one conversation, and a crew of ten specialist agents behind it.",
  applicationName: "FRIDAY",
};

export const viewport: Viewport = {
  themeColor: "#010204",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${rajdhani.variable} ${inter.variable} ${dmMono.variable}`}>{children}</body>
    </html>
  );
}
