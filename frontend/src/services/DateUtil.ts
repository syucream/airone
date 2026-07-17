export function formatDateTime(date: Date): string {
  return `${date.getFullYear()}/${
    date.getMonth() + 1
  }/${date.getDate()} ${date.getHours()}:${date.getMinutes()}:${date.getSeconds()}`;
}

export function formatDate(date: Date): string {
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

// Formats a Date as an ISO 8601 string representing local time
// (the timezone offset is subtracted so the local clock time appears in the output).
export function toLocalISOString(date: Date): string {
  return new Date(
    date.getTime() - date.getTimezoneOffset() * 60000,
  ).toISOString();
}

// Formats a Date as a local-time "YYYY-MM-DD" string (for API date values and search keywords).
export function toLocalISODateString(date: Date): string {
  return toLocalISOString(date).split("T")[0];
}

// Parses a date-only string ("YYYY-MM-DD", zero-padded or not) as LOCAL time.
// Note that new Date("YYYY-MM-DD") treats date-only ISO strings as UTC midnight,
// which shifts the displayed date back a day in negative-UTC-offset timezones.
// Non-date-only strings fall back to new Date() parsing.
export function parseLocalDate(value: string): Date {
  const m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(value);
  if (m) {
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }
  return new Date(value);
}

export function setJSTdate(date: Date): Date {
  date.setHours(9, 0, 0, 0);
  return date;
}

export const DAY_OF_WEEK = {
  jp: ["日", "月", "火", "水", "木", "金", "土"],
};
