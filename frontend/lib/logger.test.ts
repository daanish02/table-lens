import { describe, it, expect, vi, beforeEach } from "vitest";
import { logger } from "./logger";

describe("logger", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("logs info messages via console.info with a level prefix", () => {
    const spy = vi.spyOn(console, "info").mockImplementation(() => {});
    logger.info("hello", { key: "value" });
    expect(spy).toHaveBeenCalledWith("[info]", "hello", { key: "value" });
  });

  it("suppresses debug logs when NODE_ENV is production", () => {
    vi.stubEnv("NODE_ENV", "production");
    const spy = vi.spyOn(console, "debug").mockImplementation(() => {});
    logger.debug("verbose detail");
    expect(spy).not.toHaveBeenCalled();
    vi.unstubAllEnvs();
  });
});
