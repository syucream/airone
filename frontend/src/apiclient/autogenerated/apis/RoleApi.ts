/* tslint:disable */
/* eslint-disable */
/**
 *
 * No description provided (generated by Openapi Generator https://github.com/openapitools/openapi-generator)
 *
 * The version of the OpenAPI document: 0.0.0
 *
 *
 * NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).
 * https://openapi-generator.tech
 * Do not edit the class manually.
 */

import * as runtime from "../runtime";
import type { Role, RoleCreateUpdate, RoleImportExportChild } from "../models";
import {
  RoleFromJSON,
  RoleToJSON,
  RoleCreateUpdateFromJSON,
  RoleCreateUpdateToJSON,
  RoleImportExportChildFromJSON,
  RoleImportExportChildToJSON,
} from "../models";

export interface RoleApiV2CreateRequest {
  roleCreateUpdate: RoleCreateUpdate;
}

export interface RoleApiV2DestroyRequest {
  id: number;
}

export interface RoleApiV2RetrieveRequest {
  id: number;
}

export interface RoleApiV2UpdateRequest {
  id: number;
  roleCreateUpdate: RoleCreateUpdate;
}

/**
 *
 */
export class RoleApi extends runtime.BaseAPI {
  /**
   *
   */
  async roleApiV2CreateRaw(
    requestParameters: RoleApiV2CreateRequest,
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<runtime.ApiResponse<RoleCreateUpdate>> {
    if (
      requestParameters.roleCreateUpdate === null ||
      requestParameters.roleCreateUpdate === undefined
    ) {
      throw new runtime.RequiredError(
        "roleCreateUpdate",
        "Required parameter requestParameters.roleCreateUpdate was null or undefined when calling roleApiV2Create."
      );
    }

    const queryParameters: any = {};

    const headerParameters: runtime.HTTPHeaders = {};

    headerParameters["Content-Type"] = "application/json";

    if (
      this.configuration &&
      (this.configuration.username !== undefined ||
        this.configuration.password !== undefined)
    ) {
      headerParameters["Authorization"] =
        "Basic " +
        btoa(this.configuration.username + ":" + this.configuration.password);
    }
    if (this.configuration && this.configuration.apiKey) {
      headerParameters["Authorization"] =
        this.configuration.apiKey("Authorization"); // tokenAuth authentication
    }

    const response = await this.request(
      {
        path: `/role/api/v2/`,
        method: "POST",
        headers: headerParameters,
        query: queryParameters,
        body: RoleCreateUpdateToJSON(requestParameters.roleCreateUpdate),
      },
      initOverrides
    );

    return new runtime.JSONApiResponse(response, (jsonValue) =>
      RoleCreateUpdateFromJSON(jsonValue)
    );
  }

  /**
   *
   */
  async roleApiV2Create(
    requestParameters: RoleApiV2CreateRequest,
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<RoleCreateUpdate> {
    const response = await this.roleApiV2CreateRaw(
      requestParameters,
      initOverrides
    );
    return await response.value();
  }

  /**
   *
   */
  async roleApiV2DestroyRaw(
    requestParameters: RoleApiV2DestroyRequest,
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<runtime.ApiResponse<void>> {
    if (requestParameters.id === null || requestParameters.id === undefined) {
      throw new runtime.RequiredError(
        "id",
        "Required parameter requestParameters.id was null or undefined when calling roleApiV2Destroy."
      );
    }

    const queryParameters: any = {};

    const headerParameters: runtime.HTTPHeaders = {};

    if (
      this.configuration &&
      (this.configuration.username !== undefined ||
        this.configuration.password !== undefined)
    ) {
      headerParameters["Authorization"] =
        "Basic " +
        btoa(this.configuration.username + ":" + this.configuration.password);
    }
    if (this.configuration && this.configuration.apiKey) {
      headerParameters["Authorization"] =
        this.configuration.apiKey("Authorization"); // tokenAuth authentication
    }

    const response = await this.request(
      {
        path: `/role/api/v2/{id}`.replace(
          `{${"id"}}`,
          encodeURIComponent(String(requestParameters.id))
        ),
        method: "DELETE",
        headers: headerParameters,
        query: queryParameters,
      },
      initOverrides
    );

    return new runtime.VoidApiResponse(response);
  }

  /**
   *
   */
  async roleApiV2Destroy(
    requestParameters: RoleApiV2DestroyRequest,
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<void> {
    await this.roleApiV2DestroyRaw(requestParameters, initOverrides);
  }

  /**
   *
   */
  async roleApiV2ExportListRaw(
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<runtime.ApiResponse<Array<RoleImportExportChild>>> {
    const queryParameters: any = {};

    const headerParameters: runtime.HTTPHeaders = {};

    if (
      this.configuration &&
      (this.configuration.username !== undefined ||
        this.configuration.password !== undefined)
    ) {
      headerParameters["Authorization"] =
        "Basic " +
        btoa(this.configuration.username + ":" + this.configuration.password);
    }
    if (this.configuration && this.configuration.apiKey) {
      headerParameters["Authorization"] =
        this.configuration.apiKey("Authorization"); // tokenAuth authentication
    }

    const response = await this.request(
      {
        path: `/role/api/v2/export`,
        method: "GET",
        headers: headerParameters,
        query: queryParameters,
      },
      initOverrides
    );

    return new runtime.JSONApiResponse(response, (jsonValue) =>
      jsonValue.map(RoleImportExportChildFromJSON)
    );
  }

  /**
   *
   */
  async roleApiV2ExportList(
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<Array<RoleImportExportChild>> {
    const response = await this.roleApiV2ExportListRaw(initOverrides);
    return await response.value();
  }

  /**
   *
   */
  async roleApiV2ImportCreateRaw(
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<runtime.ApiResponse<void>> {
    const queryParameters: any = {};

    const headerParameters: runtime.HTTPHeaders = {};

    if (
      this.configuration &&
      (this.configuration.username !== undefined ||
        this.configuration.password !== undefined)
    ) {
      headerParameters["Authorization"] =
        "Basic " +
        btoa(this.configuration.username + ":" + this.configuration.password);
    }
    if (this.configuration && this.configuration.apiKey) {
      headerParameters["Authorization"] =
        this.configuration.apiKey("Authorization"); // tokenAuth authentication
    }

    const response = await this.request(
      {
        path: `/role/api/v2/import`,
        method: "POST",
        headers: headerParameters,
        query: queryParameters,
      },
      initOverrides
    );

    return new runtime.VoidApiResponse(response);
  }

  /**
   *
   */
  async roleApiV2ImportCreate(
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<void> {
    await this.roleApiV2ImportCreateRaw(initOverrides);
  }

  /**
   *
   */
  async roleApiV2ListRaw(
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<runtime.ApiResponse<Array<Role>>> {
    const queryParameters: any = {};

    const headerParameters: runtime.HTTPHeaders = {};

    if (
      this.configuration &&
      (this.configuration.username !== undefined ||
        this.configuration.password !== undefined)
    ) {
      headerParameters["Authorization"] =
        "Basic " +
        btoa(this.configuration.username + ":" + this.configuration.password);
    }
    if (this.configuration && this.configuration.apiKey) {
      headerParameters["Authorization"] =
        this.configuration.apiKey("Authorization"); // tokenAuth authentication
    }

    const response = await this.request(
      {
        path: `/role/api/v2/`,
        method: "GET",
        headers: headerParameters,
        query: queryParameters,
      },
      initOverrides
    );

    return new runtime.JSONApiResponse(response, (jsonValue) =>
      jsonValue.map(RoleFromJSON)
    );
  }

  /**
   *
   */
  async roleApiV2List(
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<Array<Role>> {
    const response = await this.roleApiV2ListRaw(initOverrides);
    return await response.value();
  }

  /**
   *
   */
  async roleApiV2RetrieveRaw(
    requestParameters: RoleApiV2RetrieveRequest,
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<runtime.ApiResponse<Role>> {
    if (requestParameters.id === null || requestParameters.id === undefined) {
      throw new runtime.RequiredError(
        "id",
        "Required parameter requestParameters.id was null or undefined when calling roleApiV2Retrieve."
      );
    }

    const queryParameters: any = {};

    const headerParameters: runtime.HTTPHeaders = {};

    if (
      this.configuration &&
      (this.configuration.username !== undefined ||
        this.configuration.password !== undefined)
    ) {
      headerParameters["Authorization"] =
        "Basic " +
        btoa(this.configuration.username + ":" + this.configuration.password);
    }
    if (this.configuration && this.configuration.apiKey) {
      headerParameters["Authorization"] =
        this.configuration.apiKey("Authorization"); // tokenAuth authentication
    }

    const response = await this.request(
      {
        path: `/role/api/v2/{id}`.replace(
          `{${"id"}}`,
          encodeURIComponent(String(requestParameters.id))
        ),
        method: "GET",
        headers: headerParameters,
        query: queryParameters,
      },
      initOverrides
    );

    return new runtime.JSONApiResponse(response, (jsonValue) =>
      RoleFromJSON(jsonValue)
    );
  }

  /**
   *
   */
  async roleApiV2Retrieve(
    requestParameters: RoleApiV2RetrieveRequest,
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<Role> {
    const response = await this.roleApiV2RetrieveRaw(
      requestParameters,
      initOverrides
    );
    return await response.value();
  }

  /**
   *
   */
  async roleApiV2UpdateRaw(
    requestParameters: RoleApiV2UpdateRequest,
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<runtime.ApiResponse<RoleCreateUpdate>> {
    if (requestParameters.id === null || requestParameters.id === undefined) {
      throw new runtime.RequiredError(
        "id",
        "Required parameter requestParameters.id was null or undefined when calling roleApiV2Update."
      );
    }

    if (
      requestParameters.roleCreateUpdate === null ||
      requestParameters.roleCreateUpdate === undefined
    ) {
      throw new runtime.RequiredError(
        "roleCreateUpdate",
        "Required parameter requestParameters.roleCreateUpdate was null or undefined when calling roleApiV2Update."
      );
    }

    const queryParameters: any = {};

    const headerParameters: runtime.HTTPHeaders = {};

    headerParameters["Content-Type"] = "application/json";

    if (
      this.configuration &&
      (this.configuration.username !== undefined ||
        this.configuration.password !== undefined)
    ) {
      headerParameters["Authorization"] =
        "Basic " +
        btoa(this.configuration.username + ":" + this.configuration.password);
    }
    if (this.configuration && this.configuration.apiKey) {
      headerParameters["Authorization"] =
        this.configuration.apiKey("Authorization"); // tokenAuth authentication
    }

    const response = await this.request(
      {
        path: `/role/api/v2/{id}`.replace(
          `{${"id"}}`,
          encodeURIComponent(String(requestParameters.id))
        ),
        method: "PUT",
        headers: headerParameters,
        query: queryParameters,
        body: RoleCreateUpdateToJSON(requestParameters.roleCreateUpdate),
      },
      initOverrides
    );

    return new runtime.JSONApiResponse(response, (jsonValue) =>
      RoleCreateUpdateFromJSON(jsonValue)
    );
  }

  /**
   *
   */
  async roleApiV2Update(
    requestParameters: RoleApiV2UpdateRequest,
    initOverrides?: RequestInit | runtime.InitOverrideFunction
  ): Promise<RoleCreateUpdate> {
    const response = await this.roleApiV2UpdateRaw(
      requestParameters,
      initOverrides
    );
    return await response.value();
  }
}
