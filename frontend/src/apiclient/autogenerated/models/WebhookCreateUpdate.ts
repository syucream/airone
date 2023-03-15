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
  WebhookHeaders,
  WebhookHeadersFromJSON,
  WebhookHeadersFromJSONTyped,
  WebhookHeadersToJSON,
} from "./WebhookHeaders";

/**
 *
 * @export
 * @interface WebhookCreateUpdate
 */
export interface WebhookCreateUpdate {
  /**
   *
   * @type {number}
   * @memberof WebhookCreateUpdate
   */
  id?: number;
  /**
   *
   * @type {string}
   * @memberof WebhookCreateUpdate
   */
  label?: string;
  /**
   *
   * @type {string}
   * @memberof WebhookCreateUpdate
   */
  url: string;
  /**
   *
   * @type {boolean}
   * @memberof WebhookCreateUpdate
   */
  isEnabled?: boolean;
  /**
   *
   * @type {boolean}
   * @memberof WebhookCreateUpdate
   */
  readonly isVerified: boolean;
  /**
   *
   * @type {Array<WebhookHeaders>}
   * @memberof WebhookCreateUpdate
   */
  headers?: Array<WebhookHeaders>;
  /**
   *
   * @type {boolean}
   * @memberof WebhookCreateUpdate
   */
  isDeleted?: boolean;
}

export function WebhookCreateUpdateFromJSON(json: any): WebhookCreateUpdate {
  return WebhookCreateUpdateFromJSONTyped(json, false);
}

export function WebhookCreateUpdateFromJSONTyped(
  json: any,
  ignoreDiscriminator: boolean
): WebhookCreateUpdate {
  if (json === undefined || json === null) {
    return json;
  }
  return {
    id: !exists(json, "id") ? undefined : json["id"],
    label: !exists(json, "label") ? undefined : json["label"],
    url: json["url"],
    isEnabled: !exists(json, "is_enabled") ? undefined : json["is_enabled"],
    isVerified: json["is_verified"],
    headers: !exists(json, "headers")
      ? undefined
      : (json["headers"] as Array<any>).map(WebhookHeadersFromJSON),
    isDeleted: !exists(json, "is_deleted") ? undefined : json["is_deleted"],
  };
}

export function WebhookCreateUpdateToJSON(
  value?: WebhookCreateUpdate | null
): any {
  if (value === undefined) {
    return undefined;
  }
  if (value === null) {
    return null;
  }
  return {
    id: value.id,
    label: value.label,
    url: value.url,
    is_enabled: value.isEnabled,
    headers:
      value.headers === undefined
        ? undefined
        : (value.headers as Array<any>).map(WebhookHeadersToJSON),
    is_deleted: value.isDeleted,
  };
}
