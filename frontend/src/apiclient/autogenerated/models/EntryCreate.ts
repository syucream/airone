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

import { exists, mapValues } from "../runtime";
import type { AttributeData } from "./AttributeData";
import {
  AttributeDataFromJSON,
  AttributeDataFromJSONTyped,
  AttributeDataToJSON,
} from "./AttributeData";

/**
 *
 * @export
 * @interface EntryCreate
 */
export interface EntryCreate {
  /**
   *
   * @type {number}
   * @memberof EntryCreate
   */
  readonly id: number;
  /**
   *
   * @type {string}
   * @memberof EntryCreate
   */
  name: string;
  /**
   *
   * @type {Array<AttributeData>}
   * @memberof EntryCreate
   */
  attrs?: Array<AttributeData>;
}

/**
 * Check if a given object implements the EntryCreate interface.
 */
export function instanceOfEntryCreate(value: object): boolean {
  let isInstance = true;
  isInstance = isInstance && "id" in value;
  isInstance = isInstance && "name" in value;

  return isInstance;
}

export function EntryCreateFromJSON(json: any): EntryCreate {
  return EntryCreateFromJSONTyped(json, false);
}

export function EntryCreateFromJSONTyped(
  json: any,
  ignoreDiscriminator: boolean
): EntryCreate {
  if (json === undefined || json === null) {
    return json;
  }
  return {
    id: json["id"],
    name: json["name"],
    attrs: !exists(json, "attrs")
      ? undefined
      : (json["attrs"] as Array<any>).map(AttributeDataFromJSON),
  };
}

export function EntryCreateToJSON(value?: EntryCreate | null): any {
  if (value === undefined) {
    return undefined;
  }
  if (value === null) {
    return null;
  }
  return {
    name: value.name,
    attrs:
      value.attrs === undefined
        ? undefined
        : (value.attrs as Array<any>).map(AttributeDataToJSON),
  };
}
