export const dynamic = "force-dynamic";

// Server-side fetch: inside Docker this must be the service name (http://backend:8000),
// while NEXT_PUBLIC_API_URL is what the browser uses.
const API = process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default async function HealthPage() {
  let status = "unreachable";
  try {
    const res = await fetch(`${API}/health`, { cache: "no-store" });
    status = res.ok ? (await res.json()).status : `HTTP ${res.status}`;
  } catch {}

  return (
    <>
      <h1>Health</h1>
      <p>Backend: {status}</p>
    </>
  );
}
