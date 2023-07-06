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
/**
 *
 * @export
 * @interface EntityHistory
 */
export interface EntityHistory {
  /**
   *
   * @type {number}
   * @memberof EntityHistory
   */
  readonly operation: number;
  /**
   *
   * @type {Date}
   * @memberof EntityHistory
   */
  readonly time: Date;
  /**
   *
   * @type {string}
   * @memberof EntityHistory
   */
  readonly username: string;
  /**
   *
   * @type {string}
   * @memberof EntityHistory
   */
  readonly text: string;
  /**
   *
   * @type {string}
   * @memberof EntityHistory
   */
  targetObj: string;
  /**
   *
   * @type {boolean}
   * @memberof EntityHistory
   */
  readonly isDetail: boolean;
}

/**
 * Check if a given object implements the EntityHistory interface.
 */
export function instanceOfEntityHistory(value: object): boolean {
  let isInstance = true;
  isInstance = isInstance && "operation" in value;
  isInstance = isInstance && "time" in value;
  isInstance = isInstance && "username" in value;
  isInstance = isInstance && "text" in value;
  isInstance = isInstance && "targetObj" in value;
  isInstance = isInstance && "isDetail" in value;

  return isInstance;
}

export function EntityHistoryFromJSON(json: any): EntityHistory {
  return EntityHistoryFromJSONTyped(json, false);
}

export function EntityHistoryFromJSONTyped(
  json: any,
  ignoreDiscriminator: boolean
): EntityHistory {
  if (json === undefined || json === null) {
    return json;
  }
  return {
    operation: json["operation"],
    time: new Date(json["time"]),
    username: json["username"],
    text: json["text"],
    targetObj: json["target_obj"],
    isDetail: json["is_detail"],
  };
}

export function EntityHistoryToJSON(value?: EntityHistory | null): any {
  if (value === undefined) {
    return undefined;
  }
  if (value === null) {
    return null;
  }
  return {
    target_obj: value.targetObj,
  };
}
