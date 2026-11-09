// The control-character class is intentional: URL parsing strips tab/newline.
/* eslint-disable no-control-regex */
export function safeNext(next: string | null): string {
  if (
    next &&
    next.startsWith("/") &&
    !next.startsWith("//") &&
    !/[\u0000-\u001f\u007f\\]/.test(next)
  ) {
    return next;
  }
  return "/sets";
}
