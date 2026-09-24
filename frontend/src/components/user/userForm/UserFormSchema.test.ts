import { Schema, schema } from "./UserFormSchema";

describe("schema", () => {
  // A valid value
  const baseValue: Schema = {
    username: "user1",
    email: "test@example.com",
    isSuperuser: false,
    password: "password",
  };

  test("validation succeeds for a valid value", () => {
    const value = { ...baseValue };
    expect(schema.parse(value)).toEqual(value);
  });

  test("validation fails if username is empty", () => {
    const value = {
      ...baseValue,
      username: "",
    };

    expect(() => schema.parse(value)).toThrow();
  });

  test("validation fails if email is invalid", () => {
    const value = {
      ...baseValue,
      email: "just_a_string",
    };

    expect(() => schema.parse(value)).toThrow();
  });

  test("validation fails if password is empty", () => {
    const value = {
      ...baseValue,
      password: "",
    };

    expect(() => schema.parse(value)).toThrow();
  });
});

describe("schema messages", () => {
  const baseValue: Schema = {
    username: "user1",
    email: "test@example.com",
    isSuperuser: false,
    password: "password",
  };

  test("japanese validation messages", () => {
    jest.isolateModules(() => {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const i18n = require("i18n/config").default;
      i18n.changeLanguage("ja");
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const { schema } = require("./UserFormSchema");
      const result = schema.safeParse({ ...baseValue, username: "" });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe("ユーザ名は必須です");
      }
    });
  });

  test("english validation messages", () => {
    jest.isolateModules(() => {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const i18n = require("i18n/config").default;
      i18n.changeLanguage("en");
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const { schema } = require("./UserFormSchema");
      const result = schema.safeParse({ ...baseValue, username: "" });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe("Username is required");
      }
    });
  });
});
