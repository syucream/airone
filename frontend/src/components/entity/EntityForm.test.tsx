/**
 * @jest-environment jsdom
 */

import { render } from "@testing-library/react";
import React, { FC } from "react";
import { useForm } from "react-hook-form";

import { Schema } from "./EntityFormSchema";

import { EntityForm } from "components/entity/EntityForm";
import { TestWrapper } from "TestWrapper";

test("should render a component with essential props", function () {
  const entity: Schema = {
    name: "hoge",
    note: "fuga",
    isToplevel: false,
    webhooks: [],
    attrs: [],
  };
  const Wrapper: FC = () => {
    const { control, setValue } = useForm<Schema>({
      defaultValues: entity,
    });
    return (
      <EntityForm control={control} setValue={setValue} referralEntities={[]} />
    );
  };

  expect(() =>
    render(<Wrapper />, {
      wrapper: TestWrapper,
    })
  ).not.toThrow();
});
