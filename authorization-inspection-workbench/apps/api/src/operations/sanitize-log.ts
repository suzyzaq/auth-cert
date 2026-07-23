const SECRET_KEYS = /token|secret|authorization|password|cookie|signature/i;

export function sanitizeLog(value: unknown, key = ""): unknown {
  if (SECRET_KEYS.test(key)) return "[REDACTED]";
  if (Array.isArray(value)) return value.map((item) => sanitizeLog(item));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([entryKey, entryValue]) => [
        entryKey,
        sanitizeLog(entryValue, entryKey),
      ]),
    );
  }
  if (
    typeof value === "string" &&
    /^https?:\/\//i.test(value) &&
    value.includes("?")
  ) {
    try {
      const url = new URL(value);
      if ([...url.searchParams.keys()].some((name) => SECRET_KEYS.test(name))) {
        url.search = "";
        return url.toString();
      }
    } catch {
      return value;
    }
  }
  return value;
}

