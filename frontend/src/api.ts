export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || "/api";
  const url = `${baseUrl.replace(/\/$/, "")}${path}`;
  let r!: Response;
  // Render's free instances can take about a minute to wake. During that
  // interval its temporary wake-up page is cross-origin, so browsers report a
  // network error rather than a usable HTTP response. Retry that short window.
  for (let attempt = 0; ; attempt += 1) {
    try {
      r = await fetch(url, init);
      break;
    } catch (error) {
      if (attempt >= 24) throw error;
      await new Promise((resolve) => window.setTimeout(resolve, 2500));
    }
  }
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
