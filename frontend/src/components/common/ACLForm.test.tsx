/**
 * @jest-environment jsdom
 */

import { render } from "@testing-library/react";
import React, { FC } from "react";
import { useForm } from "react-hook-form";

import { Schema } from "../acl/ACLFormSchema";

import { ACLForm } from "components/common/ACLForm";
import { TestWrapper } from "TestWrapper";

test("should render a component with essential props", function () {
  const Wrapper: FC = () => {
    const { control, watch } = useForm<Schema>({
      defaultValues: {
        isPublic: true,
        defaultPermission: 0,
        roles: [],
      },
    });

    return <ACLForm control={control} watch={watch} />;
  };

  expect(() =>
    render(<Wrapper />, {
      wrapper: TestWrapper,
    })
  ).not.toThrow();
});
