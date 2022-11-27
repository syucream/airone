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
import {
  EntityAttributeType,
  EntityAttributeTypeFromJSON,
  EntityAttributeTypeFromJSONTyped,
  EntityAttributeTypeToJSON,
} from "./EntityAttributeType";

/**
 *
 * @export
 * @interface EntryAttributeValueObject
 */
export interface EntryAttributeValueObject {
  /**
   *
   * @type {number}
   * @memberof EntryAttributeValueObject
   */
  id: number;
  /**
   *
   * @type {string}
   * @memberof EntryAttributeValueObject
   */
  name: string;
  /**
   *
   * @type {EntityAttributeType}
   * @memberof EntryAttributeValueObject
   */
  schema: EntityAttributeType;
  /**
   *
   * @type {boolean}
   * @memberof EntryAttributeValueObject
   */
  _boolean: boolean;
}

export function EntryAttributeValueObjectFromJSON(
  json: any
): EntryAttributeValueObject {
  return EntryAttributeValueObjectFromJSONTyped(json, false);
}

export function EntryAttributeValueObjectFromJSONTyped(
  json: any,
  ignoreDiscriminator: boolean
): EntryAttributeValueObject {
  if (json === undefined || json === null) {
    return json;
  }
  return {
    id: json["id"],
    name: json["name"],
    schema: EntityAttributeTypeFromJSON(json["schema"]),
    _boolean: json["boolean"],
  };
}

export function EntryAttributeValueObjectToJSON(
  value?: EntryAttributeValueObject | null
): any {
  if (value === undefined) {
    return undefined;
  }
  if (value === null) {
    return null;
  }
  return {
    id: value.id,
    name: value.name,
    schema: EntityAttributeTypeToJSON(value.schema),
    boolean: value._boolean,
  };
}
