export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || "/api";
  const r = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, init);
  if (!r.ok) {
    let message;
    try {
      const d = await r.json();
      message =
        typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
    } catch {
      message = r.statusText;
    }
    throw new Error(message || "Request failed");
  }
  return r.json();
}
export const json = (body: unknown) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
