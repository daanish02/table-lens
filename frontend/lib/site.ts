// Single source of truth for author identity shown in the UI (footer, etc.)
// — change here, not at each usage site.
export const AUTHOR_HANDLE = "daanish02";
export const AUTHOR_GITHUB_URL = `https://github.com/${AUTHOR_HANDLE}`;
// Split so the full address never appears as one scrapable string in
// source or server-rendered HTML — joined only at runtime, client-side.
const AUTHOR_EMAIL_LOCAL = "ahmed.daanish02";
const AUTHOR_EMAIL_DOMAIN = "gmail.com";
export function getAuthorEmail(): string {
  return `${AUTHOR_EMAIL_LOCAL}@${AUTHOR_EMAIL_DOMAIN}`;
}
