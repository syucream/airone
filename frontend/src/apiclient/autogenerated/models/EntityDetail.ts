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
  Webhook,
  WebhookFromJSON,
  WebhookFromJSONTyped,
  WebhookToJSON,
} from "./Webhook";

/**
 *
 * @export
 * @interface EntityDetail
 */
export interface EntityDetail {
  /**
   *
   * @type {number}
   * @memberof EntityDetail
   */
  readonly id: number;
  /**
   *
   * @type {string}
   * @memberof EntityDetail
   */
  name: string;
  /**
   *
   * @type {string}
   * @memberof EntityDetail
   */
  note: string;
  /**
   *
   * @type {number}
   * @memberof EntityDetail
   */
  status?: number;
  /**
   *
   * @type {boolean}
   * @memberof EntityDetail
   */
  readonly isToplevel: boolean;
  /**
   *
   * @type {Array<{ [key: string]: any; }>}
   * @memberof EntityDetail
   */
  readonly attrs: Array<{ [key: string]: any }>;
  /**
   *
   * @type {Array<Webhook>}
   * @memberof EntityDetail
   */
  webhooks: Array<Webhook>;
}

export function EntityDetailFromJSON(json: any): EntityDetail {
  return EntityDetailFromJSONTyped(json, false);
}

export function EntityDetailFromJSONTyped(
  json: any,
  ignoreDiscriminator: boolean
): EntityDetail {
  if (json === undefined || json === null) {
    return json;
  }
  return {
    id: json["id"],
    name: json["name"],
    note: json["note"],
    status: !exists(json, "status") ? undefined : json["status"],
    isToplevel: json["is_toplevel"],
    attrs: json["attrs"],
    webhooks: (json["webhooks"] as Array<any>).map(WebhookFromJSON),
  };
}

export function EntityDetailToJSON(value?: EntityDetail | null): any {
  if (value === undefined) {
    return undefined;
  }
  if (value === null) {
    return null;
  }
  return {
    name: value.name,
    note: value.note,
    status: value.status,
    webhooks: (value.webhooks as Array<any>).map(WebhookToJSON),
  };
}
