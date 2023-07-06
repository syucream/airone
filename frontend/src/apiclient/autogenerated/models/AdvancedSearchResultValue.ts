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
import type { AdvancedSearchResultValueAttr } from "./AdvancedSearchResultValueAttr";
import {
  AdvancedSearchResultValueAttrFromJSON,
  AdvancedSearchResultValueAttrFromJSONTyped,
  AdvancedSearchResultValueAttrToJSON,
} from "./AdvancedSearchResultValueAttr";
import type { AdvancedSearchResultValueEntry } from "./AdvancedSearchResultValueEntry";
import {
  AdvancedSearchResultValueEntryFromJSON,
  AdvancedSearchResultValueEntryFromJSONTyped,
  AdvancedSearchResultValueEntryToJSON,
} from "./AdvancedSearchResultValueEntry";
import type { AdvancedSearchResultValueReferral } from "./AdvancedSearchResultValueReferral";
import {
  AdvancedSearchResultValueReferralFromJSON,
  AdvancedSearchResultValueReferralFromJSONTyped,
  AdvancedSearchResultValueReferralToJSON,
} from "./AdvancedSearchResultValueReferral";

/**
 *
 * @export
 * @interface AdvancedSearchResultValue
 */
export interface AdvancedSearchResultValue {
  /**
   *
   * @type {{ [key: string]: AdvancedSearchResultValueAttr; }}
   * @memberof AdvancedSearchResultValue
   */
  attrs: { [key: string]: AdvancedSearchResultValueAttr };
  /**
   *
   * @type {AdvancedSearchResultValueEntry}
   * @memberof AdvancedSearchResultValue
   */
  entry: AdvancedSearchResultValueEntry;
  /**
   *
   * @type {Array<AdvancedSearchResultValueReferral>}
   * @memberof AdvancedSearchResultValue
   */
  referrals?: Array<AdvancedSearchResultValueReferral>;
}

/**
 * Check if a given object implements the AdvancedSearchResultValue interface.
 */
export function instanceOfAdvancedSearchResultValue(value: object): boolean {
  let isInstance = true;
  isInstance = isInstance && "attrs" in value;
  isInstance = isInstance && "entry" in value;

  return isInstance;
}

export function AdvancedSearchResultValueFromJSON(
  json: any
): AdvancedSearchResultValue {
  return AdvancedSearchResultValueFromJSONTyped(json, false);
}

export function AdvancedSearchResultValueFromJSONTyped(
  json: any,
  ignoreDiscriminator: boolean
): AdvancedSearchResultValue {
  if (json === undefined || json === null) {
    return json;
  }
  return {
    attrs: mapValues(json["attrs"], AdvancedSearchResultValueAttrFromJSON),
    entry: AdvancedSearchResultValueEntryFromJSON(json["entry"]),
    referrals: !exists(json, "referrals")
      ? undefined
      : (json["referrals"] as Array<any>).map(
          AdvancedSearchResultValueReferralFromJSON
        ),
  };
}

export function AdvancedSearchResultValueToJSON(
  value?: AdvancedSearchResultValue | null
): any {
  if (value === undefined) {
    return undefined;
  }
  if (value === null) {
    return null;
  }
  return {
    attrs: mapValues(value.attrs, AdvancedSearchResultValueAttrToJSON),
    entry: AdvancedSearchResultValueEntryToJSON(value.entry),
    referrals:
      value.referrals === undefined
        ? undefined
        : (value.referrals as Array<any>).map(
            AdvancedSearchResultValueReferralToJSON
          ),
  };
}
