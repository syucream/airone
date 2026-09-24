import { defineMessages } from "../defineMessages";

// Shared vocabulary and messages used across domains.
// Prefer reusing these keys over adding a domain-specific duplicate.
export const commonMessages = defineMessages({
  ja: {
    // Generic actions
    "common.cancel": "キャンセル",
    "common.submit": "送信",
    "common.apply": "適用",
    "common.save": "保存",
    "common.create": "作成",
    "common.update": "更新",
    "common.edit": "編集",
    "common.delete": "削除",
    "common.copy": "コピー",
    "common.restore": "復旧",
    "common.import": "インポート",
    "common.export": "エクスポート",
    "common.download": "ダウンロード",
    "common.details": "詳細",
    "common.close": "閉じる",
    "common.search": "検索",
    "common.name": "名前",
    "common.unknown": "不明",
    "common.backToTop": "トップページへ",

    // Object type names (used as targetName in notifications)
    "common.target.entity": "モデル",
    "common.target.entry": "アイテム",
    "common.target.alias": "エイリアス",
    "common.target.user": "ユーザ",
    "common.target.group": "グループ",
    "common.target.role": "ロール",
    "common.target.category": "カテゴリ",
    "common.target.trigger": "トリガー",

    // Notifications
    "notification.jobRegistered": "{{operationName}}のジョブ登録に成功しました",
    "notification.jobRegistrationFailed":
      "{{operationName}}のジョブ登録に失敗しました",
    "notification.jobCompleted": "{{label}}が完了しました",
    "notification.jobFailed": "{{label}}が失敗しました",
    "notification.jobTimedOut": "{{label}}がタイムアウトしました",
    "notification.operationCompleted":
      "{{targetName}}の{{operationName}}が完了しました。",
    "notification.operationFailed":
      "{{targetName}}の{{operationName}}が失敗しました。",
    "notification.exportReady": "{{targetName}}のエクスポートが完了しました",
    "notification.uploadFailed": "ファイルのアップロードに失敗しました",
    "notification.uploadFailedWithDetail":
      "ファイルのアップロードに失敗しました: {{detail}}",

    // ACL types
    "acl.type.nothing": "権限なし",
    "acl.type.readable": "閲覧",
    "acl.type.writable": "閲覧・編集",
    "acl.type.full": "閲覧・編集・削除",

    // API errors
    "apiError.AE-122000": "入力データが大きすぎます",
    "apiError.AE-210000": "操作に必要な権限が不足しています",
    "apiError.AE-220000": "入力データが既存のデータと重複しています",
    "apiError.AE-260000":
      "短期間に同じターゲットに対してインポートが発生しました",

    // Error handler
    "errorHandler.title": "エラーが発生しました",
    "errorHandler.unknownError":
      "不明なエラーが発生しました。トップページに戻って操作し直してください",
    "errorHandler.contactAdmin":
      "エラーが繰り返し発生する場合は管理者にお問い合わせください",
    "errorHandler.detail": "エラー詳細",
    "errorHandler.backToTop": "トップページに戻る",
    "errorHandler.reload": "リロードする",

    // Error pages
    "errorPage.notFound.description":
      "アクセスしたページは削除、変更されたか、現在利用できない可能性があります。",
    "errorPage.forbidden.title": "権限がありません… (|| ﾟДﾟ)",
    "errorPage.forbidden.description1":
      "あなたはこのページを閲覧する権限を持っていません。",
    "errorPage.forbidden.description2":
      "ページの管理者がアクセス権を付与できる可能性があります。",
    "errorPage.unavailable.title": "利用できません:;(∩´﹏`∩);:",
    "errorPage.unavailable.description1":
      "このページは現在、利用ができません。",
    "errorPage.unavailable.description2":
      "管理者からのお知らせをご覧いただくか、お問合せください。",

    // Common components
    "dateRangePicker.startDate": "開始日",
    "dateRangePicker.endDate": "終了日",
    "dateRangePicker.startDateTime": "開始日時",
    "dateRangePicker.endDateTime": "終了日時",
    "dateRangePicker.invalidDateRange": "終了日は開始日以降を指定してください",
    "dateRangePicker.invalidDateTimeRange":
      "終了日時は開始日時以降を指定してください",
    "clipboard.copied": "名前をコピーしました",
    "clipboard.copyName": "名前をコピーする",
    "importForm.permissionDenied": "この操作を行う権限がありません。",
    "importForm.uploadFailed": "ファイルのアップロードに失敗しました。",
    "pageHeader.staleData":
      "未処理の変更があります。現在表示されているデータは最新でない可能性があります。",
    "pagination.range": "{{from}} - {{to}} / {{count}} 件",
  },
  en: {
    // Generic actions
    "common.cancel": "Cancel",
    "common.submit": "Submit",
    "common.apply": "Apply",
    "common.save": "Save",
    "common.create": "Create",
    "common.update": "Update",
    "common.edit": "Edit",
    "common.delete": "Delete",
    "common.copy": "Copy",
    "common.restore": "Restore",
    "common.import": "Import",
    "common.export": "Export",
    "common.download": "Download",
    "common.details": "Details",
    "common.close": "Close",
    "common.search": "Search",
    "common.name": "Name",
    "common.unknown": "Unknown",
    "common.backToTop": "Back to top",

    // Object type names (used as targetName in notifications)
    "common.target.entity": "Entity",
    "common.target.entry": "Entry",
    "common.target.alias": "Alias",
    "common.target.user": "User",
    "common.target.group": "Group",
    "common.target.role": "Role",
    "common.target.category": "Category",
    "common.target.trigger": "Trigger",

    // Notifications
    "notification.jobRegistered":
      "Successfully registered the {{operationName}} job",
    "notification.jobRegistrationFailed":
      "Failed to register the {{operationName}} job",
    "notification.jobCompleted": "{{label}} completed",
    "notification.jobFailed": "{{label}} failed",
    "notification.jobTimedOut": "{{label}} timed out",
    "notification.operationCompleted":
      "{{operationName}} {{targetName}} completed.",
    "notification.operationFailed": "{{operationName}} {{targetName}} failed.",
    "notification.exportReady": "Export of {{targetName}} completed",
    "notification.uploadFailed": "Failed to upload the file",
    "notification.uploadFailedWithDetail":
      "Failed to upload the file: {{detail}}",

    // ACL types
    "acl.type.nothing": "No permission",
    "acl.type.readable": "Read",
    "acl.type.writable": "Read / Write",
    "acl.type.full": "Read / Write / Delete",

    // API errors
    "apiError.AE-122000": "The input data is too large",
    "apiError.AE-210000": "You do not have permission for this operation",
    "apiError.AE-220000": "The input data duplicates existing data",
    "apiError.AE-260000":
      "Another import for the same target was performed a short time ago",

    // Error handler
    "errorHandler.title": "An error occurred",
    "errorHandler.unknownError":
      "An unknown error occurred. Please go back to the top page and try again",
    "errorHandler.contactAdmin":
      "If the error persists, please contact your administrator",
    "errorHandler.detail": "Error details",
    "errorHandler.backToTop": "Back to top page",
    "errorHandler.reload": "Reload",

    // Error pages
    "errorPage.notFound.description":
      "The page you are looking for may have been removed, changed, or is temporarily unavailable.",
    "errorPage.forbidden.title": "Forbidden… (|| ﾟДﾟ)",
    "errorPage.forbidden.description1":
      "You do not have permission to view this page.",
    "errorPage.forbidden.description2":
      "The page administrator may be able to grant you access.",
    "errorPage.unavailable.title": "Unavailable:;(∩´﹏`∩);:",
    "errorPage.unavailable.description1": "This page is currently unavailable.",
    "errorPage.unavailable.description2":
      "Please check announcements from your administrator or contact them.",

    // Common components
    "dateRangePicker.startDate": "Start date",
    "dateRangePicker.endDate": "End date",
    "dateRangePicker.startDateTime": "Start date/time",
    "dateRangePicker.endDateTime": "End date/time",
    "dateRangePicker.invalidDateRange":
      "The end date must be on or after the start date",
    "dateRangePicker.invalidDateTimeRange":
      "The end date/time must be on or after the start date/time",
    "clipboard.copied": "Copied the name",
    "clipboard.copyName": "Copy the name",
    "importForm.permissionDenied":
      "You do not have permission to perform this operation.",
    "importForm.uploadFailed": "Failed to upload the file.",
    "pageHeader.staleData":
      "There are pending changes. The data currently displayed may be out of date.",
    "pagination.range": "{{from}} - {{to}} of {{count}}",
  },
});
