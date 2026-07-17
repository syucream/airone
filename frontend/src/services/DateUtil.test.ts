/**
 * @jest-environment jsdom
 */

import {
  formatDateTime,
  formatDate,
  parseLocalDate,
  setJSTdate,
  toLocalISODateString,
  toLocalISOString,
  DAY_OF_WEEK,
} from "./DateUtil";

describe("DateUtil", () => {
  describe("formatDateTime", () => {
    test("should format date with time correctly", () => {
      const date = new Date(2024, 0, 15, 14, 30, 45); // Jan 15, 2024, 14:30:45

      const result = formatDateTime(date);

      expect(result).toBe("2024/1/15 14:30:45");
    });

    test("should handle single digit month and day", () => {
      const date = new Date(2024, 0, 5, 9, 5, 3); // Jan 5, 2024, 09:05:03

      const result = formatDateTime(date);

      expect(result).toBe("2024/1/5 9:5:3");
    });

    test("should handle midnight", () => {
      const date = new Date(2024, 5, 20, 0, 0, 0); // Jun 20, 2024, 00:00:00

      const result = formatDateTime(date);

      expect(result).toBe("2024/6/20 0:0:0");
    });

    test("should handle end of day", () => {
      const date = new Date(2024, 11, 31, 23, 59, 59); // Dec 31, 2024, 23:59:59

      const result = formatDateTime(date);

      expect(result).toBe("2024/12/31 23:59:59");
    });
  });

  describe("formatDate", () => {
    test("should format date in Japanese locale with zero-padded values", () => {
      const date = new Date(2024, 0, 15); // Jan 15, 2024

      const result = formatDate(date);

      expect(result).toBe("2024/01/15");
    });

    test("should handle single digit month and day with zero padding", () => {
      const date = new Date(2024, 0, 5); // Jan 5, 2024

      const result = formatDate(date);

      expect(result).toBe("2024/01/05");
    });

    test("should handle December correctly", () => {
      const date = new Date(2024, 11, 25); // Dec 25, 2024

      const result = formatDate(date);

      expect(result).toBe("2024/12/25");
    });
  });

  describe("setJSTdate", () => {
    test("should set time to 9:00:00.000 (JST midnight in UTC)", () => {
      const date = new Date(2024, 0, 15, 14, 30, 45, 123);

      const result = setJSTdate(date);

      expect(result.getHours()).toBe(9);
      expect(result.getMinutes()).toBe(0);
      expect(result.getSeconds()).toBe(0);
      expect(result.getMilliseconds()).toBe(0);
    });

    test("should return the same date object (mutates in place)", () => {
      const date = new Date(2024, 0, 15, 14, 30, 45);

      const result = setJSTdate(date);

      expect(result).toBe(date);
    });

    test("should preserve year, month, and day", () => {
      const date = new Date(2024, 5, 20, 23, 59, 59);

      const result = setJSTdate(date);

      expect(result.getFullYear()).toBe(2024);
      expect(result.getMonth()).toBe(5); // June (0-indexed)
      expect(result.getDate()).toBe(20);
    });
  });

  describe("toLocalISOString / toLocalISODateString", () => {
    test("should format local wall-clock time as an ISO-like string", () => {
      const date = new Date(2024, 0, 5, 14, 30, 45); // local Jan 5, 2024, 14:30:45

      // Jest runs with TZ=UTC, so local time equals UTC here.
      expect(toLocalISOString(date)).toBe("2024-01-05T14:30:45.000Z");
      expect(toLocalISODateString(date)).toBe("2024-01-05");
    });
  });

  describe("parseLocalDate", () => {
    test("should parse a zero-padded date-only string as local time", () => {
      const result = parseLocalDate("2024-01-05");

      expect(result.getFullYear()).toBe(2024);
      expect(result.getMonth()).toBe(0);
      expect(result.getDate()).toBe(5);
      expect(result.getHours()).toBe(0);
    });

    test("should parse a non-padded date-only string as local time", () => {
      const result = parseLocalDate("2024-1-5");

      expect(result.getFullYear()).toBe(2024);
      expect(result.getMonth()).toBe(0);
      expect(result.getDate()).toBe(5);
    });

    test("should round-trip with toLocalISODateString", () => {
      const date = new Date(2024, 11, 31);

      expect(parseLocalDate(toLocalISODateString(date)).getTime()).toBe(
        date.getTime(),
      );
    });

    test("should fall back to new Date() parsing for datetime strings", () => {
      const result = parseLocalDate("2024-01-05T10:00:00.000Z");

      expect(result.getTime()).toBe(Date.parse("2024-01-05T10:00:00.000Z"));
    });
  });

  describe("DAY_OF_WEEK", () => {
    test("should have Japanese day names in correct order", () => {
      expect(DAY_OF_WEEK.jp).toEqual([
        "日",
        "月",
        "火",
        "水",
        "木",
        "金",
        "土",
      ]);
    });

    test("should have 7 days", () => {
      expect(DAY_OF_WEEK.jp.length).toBe(7);
    });

    test("should start with Sunday (日)", () => {
      expect(DAY_OF_WEEK.jp[0]).toBe("日");
    });

    test("should end with Saturday (土)", () => {
      expect(DAY_OF_WEEK.jp[6]).toBe("土");
    });
  });
});
