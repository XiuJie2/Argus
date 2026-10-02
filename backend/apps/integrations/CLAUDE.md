# integrations 模組規則

## 職責

- 管理 Google Search Console OAuth、property 綁定與 Search Analytics 日資料同步。
- 所有查詢必須同時限制 `request.user` 與 `SiteProject`，不得僅相信 `project_id`。
- OAuth callback 以一次性、10 分鐘到期的 `GSCOAuthState` 還原會員與專案脈絡，不依賴前端 JWT。

## 安全邊界

- Access／refresh token 只以 Fernet 密文保存，禁止寫入 API 回應、log 或錯誤訊息。
- GSC 唯讀 scope 固定為 `webmasters.readonly`；不得擴張為可寫入 scope。
- 只有 permission level 為 `siteOwner`，且 Domain property 涵蓋 hostname 或 URL-prefix property 是精確 host 根路徑時，才能建立或續期 `VerifiedDomain(method=gsc)`；子路徑 property 不能驗證整個 host。
- `siteFullUser` 與 `siteRestrictedUser` 可作為資料授權，但不是網域所有權證明。
- GSC 指標保留 Google 原始語意，不併入 Argus 健康分數，也不宣稱與診斷問題存在因果。
- `gsc/status/` 同時回傳目前專案 hostname 可用的有效網域驗證（包含涵蓋子網域的父網域）；會員操作入口在專案設定，不能只完成後端 endpoint 就宣稱整合可用。
