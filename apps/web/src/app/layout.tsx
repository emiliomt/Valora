import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Valora — Investment Research & Valuation Platform",
  description: "A traceable underwriting workspace: upload financials, build a DCF, export Excel & PowerPoint.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <div className="mx-auto max-w-6xl px-4 py-6">{children}</div>
        <footer className="mx-auto max-w-6xl px-4 pb-8 pt-12 text-xs text-[var(--muted)]">
          Valora provides research, modeling, and analytical support. It does not provide personalized investment
          advice, a recommendation to buy or sell securities, legal advice, tax advice, or accounting advice.
          Independently verify all data, assumptions, and model outputs before use in any investment decision.
        </footer>
      </body>
    </html>
  );
}
