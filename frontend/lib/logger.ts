type LogLevel = "debug" | "info" | "warn" | "error";

function shouldLog(level: LogLevel): boolean {
  if (level === "debug") return process.env.NODE_ENV !== "production";
  return true;
}

function log(level: LogLevel, message: string, ...meta: unknown[]): void {
  if (!shouldLog(level)) return;
  const consoleFn = console[level] ?? console.log;
  consoleFn(`[${level}]`, message, ...meta);
}

export const logger = {
  debug: (message: string, ...meta: unknown[]) => log("debug", message, ...meta),
  info: (message: string, ...meta: unknown[]) => log("info", message, ...meta),
  warn: (message: string, ...meta: unknown[]) => log("warn", message, ...meta),
  error: (message: string, ...meta: unknown[]) => log("error", message, ...meta),
};
