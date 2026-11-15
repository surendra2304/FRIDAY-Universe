import type { Metadata, Viewport } from "next";
import { JetBrains_Mono, Manrope, Space_Grotesk } from "next/font/google";
import "./globals.css";

/* TASK-WEB-002 (2026-11-15) — the Halo console's type system.
   Space Grotesk is the voice of the room (wordmark, headings,
   commands); Manrope carries conversation and prose; JetBrains
   Mono is kept for numbers and machine readouts only. */
const grotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-grotesk",
  display: "swap",
});

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FRIDAY",
  description: "One room, one voice, one conversation — and ten specialists listening behind the light.",
  applicationName: "FRIDAY",
};

export const viewport: Viewport = {
  themeColor: "#030409",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${grotesk.variable} ${manrope.variable} ${jetbrains.variable}`}>{children}</body>
    </html>
  );
}
