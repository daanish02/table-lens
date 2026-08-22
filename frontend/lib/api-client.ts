import { logger } from "./logger";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  logger.debug("api.request", { path });
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok) {
    logger.error("api.error", { path, status: response.status });
    throw new Error(`API request to ${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

// Reads a server-sent-events response (one JSON object per `data: ` line,
// events separated by a blank line) and calls onEvent for each as it
// arrives. Used instead of EventSource because EventSource only supports
// GET, and this needs a JSON POST body.
async function streamPost<TEvent>(path: string, body: unknown, onEvent: (event: TEvent) => void): Promise<void> {
  logger.debug("api.streamRequest", { path });
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    logger.error("api.error", { path, status: response.status });
    throw new Error(`API request to ${path} failed with ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const line = block.trim();
      if (!line.startsWith("data: ")) continue;
      onEvent(JSON.parse(line.slice("data: ".length)) as TEvent);
    }
  }
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  streamPost,
};
