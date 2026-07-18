/**
 * @jest-environment jsdom
 */

import {
  EntryAttributeTypeTypeEnum,
  PaginatedGroupList,
} from "@dmm-com/airone-apiclient-typescript-fetch";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
  within,
} from "@testing-library/react";
import { useForm } from "react-hook-form";

import { aironeApiClient } from "../../../repository/AironeApiClient";

import { schema, Schema } from "./EntryFormSchema";
import { GroupAttributeValueField } from "./GroupAttributeValueField";

import { TestWrapper } from "TestWrapper";

import "@testing-library/jest-dom";

describe("GroupAttributeValueField", () => {
  const defaultValues: Schema = {
    name: "entry",
    schema: {
      id: 1,
      name: "entity",
    },
    attrs: {
      "0": {
        type: EntryAttributeTypeTypeEnum.GROUP,
        index: 0,
        isMandatory: false,
        schema: {
          id: 1,
          name: "group",
        },
        value: {
          asGroup: { id: 1, name: "group1" },
        },
      },
      "1": {
        type: EntryAttributeTypeTypeEnum.ARRAY_GROUP,
        index: 1,
        isMandatory: false,
        schema: {
          id: 2,
          name: "array-group",
        },
        value: {
          asArrayGroup: [
            {
              id: 1,
              name: "group1",
            },
          ],
        },
      },
    },
  };

  const groups: PaginatedGroupList = {
    count: 0,
    results: [
      {
        id: 1,
        name: "group1",
        members: [],
      },
      {
        id: 2,
        name: "group2",
        members: [],
      },
    ],
  };

  test("should provide group value editor", async () => {
    const {
      result: {
        current: { control, setValue, getValues },
      },
    } = renderHook(() =>
      useForm<Schema>({
        resolver: zodResolver(schema),
        mode: "onBlur",
        defaultValues,
      }),
    );

    let resolveGroups!: (value: PaginatedGroupList) => void;
    jest.spyOn(aironeApiClient, "getGroups").mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveGroups = resolve;
        }),
    );

    render(
      <GroupAttributeValueField
        attrId={0}
        control={control}
        setValue={setValue}
      />,
      { wrapper: TestWrapper },
    );
    await act(async () => {
      resolveGroups(groups);
    });

    expect(screen.getByRole("combobox")).toHaveValue("group1");
    expect(getValues("attrs.0.value.asGroup")).toEqual({
      id: 1,
      name: "group1",
    });

    // Open the select options
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    // Select "group2" element
    fireEvent.click(
      await within(screen.getByRole("presentation")).findByText("group2"),
    );

    expect(screen.getByRole("combobox")).toHaveValue("group2");
    expect(getValues("attrs.0.value.asGroup")).toEqual({
      id: 2,
      name: "group2",
    });
  });

  test("should provide array-group value editor", async () => {
    const {
      result: {
        current: { control, setValue, getValues },
      },
    } = renderHook(() =>
      useForm<Schema>({
        resolver: zodResolver(schema),
        mode: "onBlur",
        defaultValues,
      }),
    );

    let resolveGroups!: (value: PaginatedGroupList) => void;
    jest.spyOn(aironeApiClient, "getGroups").mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveGroups = resolve;
        }),
    );

    render(
      <GroupAttributeValueField
        attrId={1}
        control={control}
        setValue={setValue}
        multiple
      />,
      { wrapper: TestWrapper },
    );
    await act(async () => {
      resolveGroups(groups);
    });

    expect(screen.getByRole("button", { name: "group1" })).toBeInTheDocument();
    expect(getValues("attrs.1.value.asArrayGroup")).toEqual([
      { id: 1, name: "group1" },
    ]);

    // Open the select options
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    // Select "group2" element
    fireEvent.click(
      await within(screen.getByRole("presentation")).findByText("group2"),
    );

    expect(screen.getByRole("button", { name: "group1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "group2" })).toBeInTheDocument();
    expect(getValues("attrs.1.value.asArrayGroup")).toEqual([
      { id: 1, name: "group1" },
      { id: 2, name: "group2" },
    ]);
  });
});
