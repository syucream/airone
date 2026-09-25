import { EntryAttributeTypeTypeEnum } from "@dmm-com/airone-apiclient-typescript-fetch";

import { Schema, schema, toRefCond } from "./TriggerFormSchema";

import { ACLType } from "services/ACLUtil";

describe("schema", () => {
  // A valid value
  const baseValue: Schema = {
    id: 1,
    entity: {
      id: 1,
      name: "entity1",
      isPublic: true,
      permission: ACLType.Full,
    },
    conditions: [
      {
        id: 1,
        attr: {
          id: 1,
          name: "attr1",
          type: EntryAttributeTypeTypeEnum.STRING,
        },
        strCond: "str cond",
        refCond: null,
      },
    ],
    actions: [
      {
        id: 1,
        attr: {
          id: 1,
          name: "attr1",
          type: EntryAttributeTypeTypeEnum.STRING,
        },
        values: [
          {
            id: 1,
            strCond: "str cond",
            refCond: null,
          },
        ],
      },
    ],
  };

  test("validation succeeds for a valid value", () => {
    const value = { ...baseValue };
    expect(schema.parse(value)).toEqual(value);
  });

  test("validation fails if it does not have an entity", () => {
    const value = {
      ...baseValue,
      entity: undefined,
    };

    expect(() => schema.parse(value)).toThrow();
  });

  test("validation fails if it does not have conditions", () => {
    const value = {
      ...baseValue,
      conditions: [],
    };

    expect(() => schema.parse(value)).toThrow();
  });

  test("validation fails if it has a condition without an attr", () => {
    const value = {
      ...baseValue,
      conditions: [
        {
          ...baseValue.conditions[0],
          attr: undefined,
        },
      ],
    };

    expect(() => schema.parse(value)).toThrow();
  });

  test("validation fails if it does not have actions", () => {
    const value = {
      ...baseValue,
      actions: [],
    };

    expect(() => schema.parse(value)).toThrow();
  });

  test("validation fails if it has an action without an attr", () => {
    const value = {
      ...baseValue,
      actions: [
        {
          ...baseValue.actions[0],
          attr: undefined,
        },
      ],
    };

    expect(() => schema.parse(value)).toThrow();
  });
});

describe("toRefCond", () => {
  test("should convert a selected referral", () => {
    expect(toRefCond({ id: 1, name: "entry1", displayLabel: null })).toEqual({
      id: 1,
      name: "entry1",
      schema: { id: 0, name: "" },
    });
  });

  test("should map a cleared selection to null", () => {
    expect(toRefCond(null)).toBeNull();
    expect(toRefCond([])).toBeNull();
  });
});
