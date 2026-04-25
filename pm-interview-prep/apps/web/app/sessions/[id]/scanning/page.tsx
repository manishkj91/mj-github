"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function ScanningPage({
  params,
}: {
  params: { id: string };
}) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    (async () => {
      try {
        await api.scan(params.id);
        router.replace(`/sessions/${params.id}/plan`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Scan failed.");
      }
    })();
  }, [params.id, router]);

  return (
    <div className="mx-auto max-w-md py-20 text-center animate-fade-up">
      <div className="mx-auto mb-6 grid h-12 w-12 place-items-center rounded-full bg-ink-100">
        <span className="block h-3 w-3 animate-pulse rounded-full bg-ink-700" />
      </div>
      <h1 className="text-xl font-semibold tracking-tight">
        Reading your resume…
      </h1>
      <p className="mt-2 text-sm text-ink-500">
        The scanner is extracting roles, scope, and metrics, then drafting a
        question plan.
      </p>
      {error && (
        <div className="mt-6 rounded-md bg-red-50 p-3 text-left text-sm text-red-700">
          {error}
          <div className="mt-2">
            <a className="underline" href="/">
              Try again
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
