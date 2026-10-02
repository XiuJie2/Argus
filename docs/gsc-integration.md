# Google Search Console 整合

## Google Cloud 設定

1. 在 Google Cloud 專案啟用 **Google Search Console API**。
2. 建立 OAuth 2.0 **Web application** client。
3. Authorized redirect URI 必須逐字設定為：

   ```text
   https://ars.clouda.dpdns.org/api/integrations/gsc/callback
   ```

   此 URI **沒有尾斜線**；Google Cloud Console 與 `GSC_OAUTH_REDIRECT_URI` 必須完全一致。
4. 將 Client ID／Secret 放進未追蹤的 `.env` 或 Kubernetes Secret：

   ```dotenv
   GSC_OAUTH_CLIENT_ID=...
   GSC_OAUTH_CLIENT_SECRET=...
   GSC_OAUTH_REDIRECT_URI=https://ars.clouda.dpdns.org/api/integrations/gsc/callback
   ```

`GSC_TOKEN_ENCRYPTION_KEY` 可留空，後端會以 `DJANGO_SECRET_KEY` 穩定衍生 Fernet key；若另外設定，必須使用合法 Fernet key，且上線後不可任意更換，否則既有連線必須重新授權。

## API 流程

| Method | Endpoint | 用途 |
|---|---|---|
| POST | `/api/integrations/gsc/authorize/` | 以 `project_id` 建立 10 分鐘、一次性 OAuth state，回傳 Google 授權網址 |
| GET | `/api/integrations/gsc/callback` | Google callback；交換 token、列出 properties 並導回專案設定頁 |
| GET | `/api/integrations/gsc/status/?project_id=...` | 查連線、properties、目前綁定與同步時間 |
| POST | `/api/integrations/gsc/property/` | 選擇涵蓋專案 hostname 的 property |
| POST | `/api/integrations/gsc/sync/` | 同步最多 91 天的日維度 Search Analytics |
| GET | `/api/integrations/gsc/metrics/` | 依日期區間讀取已同步資料 |
| DELETE | `/api/integrations/gsc/disconnect/?project_id=...` | 盡力撤銷 Google token 並刪除本地連線與指標 |

會員可在「網站專案 → 專案設定 → 網域驗證與 Search Console」直接查看目前網站的有效驗證、開始 Google 授權及選擇 property；若不使用 GSC，也可由同一區塊前往 DNS TXT／HTML 驗證，網域欄位與返回專案路徑會自動帶入。

所有會員端點均同時以登入會員與 `SiteProject` 歸屬查詢；callback 則以不可猜測、一次性且會到期的 state 還原脈絡。Access／refresh token 只保存密文，不出現在 serializer、API 回應或 log。

## 網域驗證邊界

- `siteOwner` 且 property 涵蓋專案 hostname：建立或續期 `VerifiedDomain(method=gsc)`，有效期沿用 90 天設定。
- `siteFullUser`／`siteRestrictedUser`：可讀 GSC 成效資料，但不是所有權證明。
- `siteUnverifiedUser` 或不涵蓋目前 hostname 的 property：不可綁定。
- GSC 驗證不取代掃描時的授權確認，也不把 GSC 指標混入 Argus 健康分數。

Domain property（`sc-domain:example.com`）可涵蓋相同網域及其子網域。URL-prefix property 可在 hostname 與專案精確相符時綁定資料，但只有根路徑 property（例如 `https://www.example.com/`）能驗證整個 hostname；`/blog/` 之類子路徑 property 不會取得主動掃描資格。

## 官方參考

- [Google OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Search Console API：Sites list](https://developers.google.com/webmaster-tools/v1/sites/list)
- [Search Console API：Search Analytics query](https://developers.google.com/webmaster-tools/v1/searchanalytics/query)
