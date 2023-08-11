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
import type { ACLParent } from "./ACLParent";
import {
  ACLParentFromJSON,
  ACLParentFromJSONTyped,
  ACLParentToJSON,
} from "./ACLParent";
import type { ACLRole } from "./ACLRole";
import {
  ACLRoleFromJSON,
  ACLRoleFromJSONTyped,
  ACLRoleToJSON,
} from "./ACLRole";
import type { ACLSetting } from "./ACLSetting";
import {
  ACLSettingFromJSON,
  ACLSettingFromJSONTyped,
  ACLSettingToJSON,
} from "./ACLSetting";

/**
 *
 * @export
 * @interface ACL
 */
export interface ACL {
  /**
   *
   * @type {number}
   * @memberof ACL
   */
  readonly id: number;
  /**
   *
   * @type {string}
   * @memberof ACL
   */
  readonly name: string;
  /**
   *
   * @type {boolean}
   * @memberof ACL
   */
  isPublic?: boolean;
  /**
   *
   * @type {number}
   * @memberof ACL
   */
  defaultPermission?: number;
  /**
   *
   * @type {number}
   * @memberof ACL
   */
  readonly objtype: ACLObjtypeEnum;
  /**
   *
   * @type {Array<ACLSetting>}
   * @memberof ACL
   */
  aclSettings?: Array<ACLSetting>;
  /**
   *
   * @type {Array<ACLRole>}
   * @memberof ACL
   */
  readonly roles: Array<ACLRole>;
  /**
   *
   * @type {ACLParent}
   * @memberof ACL
   */
  parent: ACLParent | null;
}

/**
 * @export
 */
export const ACLObjtypeEnum = {
  Entity: 1,
  EntityAttr: 2,
  Entry: 4,
  EntryAttr: 8,
} as const;
export type ACLObjtypeEnum = typeof ACLObjtypeEnum[keyof typeof ACLObjtypeEnum];

/**
 * Check if a given object implements the ACL interface.
 */
export function instanceOfACL(value: object): boolean {
  let isInstance = true;
  isInstance = isInstance && "id" in value;
  isInstance = isInstance && "name" in value;
  isInstance = isInstance && "objtype" in value;
  isInstance = isInstance && "roles" in value;
  isInstance = isInstance && "parent" in value;

  return isInstance;
}

export function ACLFromJSON(json: any): ACL {
  return ACLFromJSONTyped(json, false);
}

export function ACLFromJSONTyped(json: any, ignoreDiscriminator: boolean): ACL {
  if (json === undefined || json === null) {
    return json;
  }
  return {
    id: json["id"],
    name: json["name"],
    isPublic: !exists(json, "is_public") ? undefined : json["is_public"],
    defaultPermission: !exists(json, "default_permission")
      ? undefined
      : json["default_permission"],
    objtype: json["objtype"],
    aclSettings: !exists(json, "acl_settings")
      ? undefined
      : (json["acl_settings"] as Array<any>).map(ACLSettingFromJSON),
    roles: (json["roles"] as Array<any>).map(ACLRoleFromJSON),
    parent: ACLParentFromJSON(json["parent"]),
  };
}

export function ACLToJSON(value?: ACL | null): any {
  if (value === undefined) {
    return undefined;
  }
  if (value === null) {
    return null;
  }
  return {
    is_public: value.isPublic,
    default_permission: value.defaultPermission,
    acl_settings:
      value.aclSettings === undefined
        ? undefined
        : (value.aclSettings as Array<any>).map(ACLSettingToJSON),
    parent: ACLParentToJSON(value.parent),
  };
}
