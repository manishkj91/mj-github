import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PM Interview Prep",
  description:
    "Behavioral-interview prep for Product Manager candidates at top companies. Resume-grounded questions, multi-turn interviewer, rubric-based feedback.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="border-b border-ink-100 bg-white/70 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
            <a href="/" className="flex items-center gap-2">
              <span className="grid h-7 w-7 place-items-center rounded-md bg-ink-900 text-sm font-semibold text-white">
                PM
              </span>
              <span className="font-semibold tracking-tight">
                Interview Prep
              </span>
            </a>
            <nav className="flex items-center gap-3 text-sm text-ink-500">
              <a
                href="https://github.com/manishkj91/mj-github/tree/main/pm-interview-prep"
                target="_blank"
                rel="noreferrer"
                className="hover:text-ink-800"
              >
                Source
              </a>
            </nav>
          </div>
        </header>

        <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>

        <footer className="mx-auto max-w-5xl px-6 py-10 text-xs text-ink-400">
          A sandbox project. Resumes are kept in process memory only and
          discarded when the server restarts.
        </footer>
      </body>
    </html>
  );
}
