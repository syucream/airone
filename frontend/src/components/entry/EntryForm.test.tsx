/**
 * @jest-environment jsdom
 */

import { render } from "@testing-library/react";
import React, { FC } from "react";
import { useForm } from "react-hook-form";

import { Schema } from "./entryForm/EntryFormSchema";

import { EntryForm } from "components/entry/EntryForm";
import { TestWrapper } from "TestWrapper";

test("should render a component with essential props", function () {
  const entryInfo = {
    name: "test entry",
    schema: { id: 0, name: "testEntity" },
    attrs: {},
  };
  const entity = {
    id: 2,
    name: "bbb",
    note: "",
    isToplevel: false,
    attrs: [],
    webhooks: [],
  };

  const setIsAnchorLink = () => {
    /* do nothing */
  };

  const Wrapper: FC = () => {
    const { control, setValue } = useForm<Schema>({
      defaultValues: entryInfo,
    });
    return (
      <EntryForm
        entity={entity}
        setIsAnchorLink={setIsAnchorLink}
        control={control}
        setValue={setValue}
      />
    );
  };

  expect(() =>
    render(<Wrapper />, {
      wrapper: TestWrapper,
    })
  ).not.toThrow();
});
