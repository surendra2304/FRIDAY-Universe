import type { Metadata, Viewport } from "next";
import { DM_Mono, Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const grotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-grotesk",
  display: "swap",
});

/* DM Mono carries every numeral, clock and micro-label in the console
   (design system: monospace for data — tabular, unambiguous). */
const dmMono = DM_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-dm-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FRIDAY — Your Personal Jarvis",
  description:
    "Talk to FRIDAY continuously by voice, chat with the coordinator, and watch the ten-agent FRIDAY Universe fleet live.",
  applicationName: "FRIDAY",
};

export const viewport: Viewport = {
  themeColor: "#05070c",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${grotesk.variable} ${dmMono.variable}`}>{children}</body>
    </html>
  );
}
