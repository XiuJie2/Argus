# Argus 會員區「網站專案工作區」修訂實作規劃

**日期**：2026-09-29
**狀態**：網站專案核心工作區已於 2026-09-30 實作；DNS 與外部整合仍依後續 release 規劃
**審查基準**：目前分支 `work`、提交 `29dfde9`

## 1. 範圍、目標與非目標

### 1.1 產品目標

把會員長期工作的主體由「散落的掃描任務」改成「網站專案」，讓主要路徑成為：

> 選擇網站專案 → 查看可比較的變化 → 檢視有證據的問題 → 修復 → 再掃描驗證

每次掃描仍是不可竄改的時間點快照；網站專案只負責歸屬、導覽、預設值與跨掃描聚合，不改寫歷史掃描內容。

### 1.2 第一版成功條件

1. 既有掃描與報告遷移後仍可由原連結存取。
2. 每筆新掃描明確隸屬一個網站專案，所有查詢同時檢查使用者與專案歸屬。
3. 建立／編輯／封存專案不扣點；只有沿用既有掃描建立流程時才預扣點數。
4. 使用者可以在專案內完成建立掃描、看最新結果與歷史比較的垂直流程。
5. DNS 是帶來源與時間的外部觀測，不是所有權證明，也不影響主掃描完成。
6. 不把 Argus、Search Console、GA4 或 Cloudflare 訊號合成單一健康分數。

### 1.3 明確非目標

- 第一版不做多人組織、專案成員或角色權限；目前資料仍以單一 `User` 擁有。
- 不讀取會員 Cloudflare 帳戶、WAF 事件或私人 zone 設定。
- 不把 Cloudflare URL Scanner 設成一般會員掃描的預設必經步驟。
- 不宣稱 GSC／GA4 指標變動由某個 Argus finding 造成。
- 不在資料模型穩定前同時開發排程、通知、GSC 與 GA4。

## 2. 現況審查與獨立判斷

### 2.1 已確認的程式現況

- `ScanJob` 直接歸屬使用者，保存 `original_url`、`normalized_url` 與 `origin`，目前沒有網站專案模型。
- 掃描列表預設依 `origin` 只回每組最新一筆；`/api/history/` 也依 `origin` 聚合。這是可利用的遷移來源，但 `origin` 包含 scheme／port，不能直接視為網站身分。
- 建立掃描已具備公開網址／SSRF 檢查、授權確認、第三方目標二次確認、主動掃描網域驗證、估價、原子預扣與排隊流程。新增專案後必須呼叫同一條服務鏈，不能另寫簡化版本。
- `VerifiedDomain` 是使用者層級的主動掃描閘門，支援 DNS TXT、meta、HTML file 與受限的 GSC owner 證據；GSC 連線本身不是驗證，只有 `siteOwner` 且 property 涵蓋專案 hostname 時才可寫入驗證。
- `Finding` 是單次掃描證據，已有 `rule_id`、page、category、evidence 等欄位，但沒有跨掃描穩定識別或 lifecycle。
- Dashboard、歷史、掃描、網域驗證已是分開頁面；改版需要新 project context 與相容路由，而不是只新增側邊欄。

### 2.2 對原提案的取捨

| 原提案項目 | 判斷 | 修訂理由 |
|---|---|---|
| 網站專案作為核心 | **採納** | 與既有 `origin` 聚合方向一致，但必須新增正式歸屬與遷移。 |
| 建站不掃描、不扣點 | **採納** | 專案是容器；扣點仍只發生於掃描建立。 |
| 第一版同時完成專案 UI 與 DNS | **修改** | 先交付「專案＋既有掃描」垂直切片，再接 DNS，避免一次改資料歸屬、導航與掃描 pipeline。 |
| `example.com`、`www`、子網域歸屬明確 | **採納但收緊** | 第一版以精確 hostname 為專案邊界；不自動把所有子網域合併。是否涵蓋子網域是掃描授權規則，不是專案歸屬規則。 |
| 網域驗證表直接承擔專案授權 | **否決** | 現有驗證是 user-scoped 主動掃描閘門；應以關聯／查詢判斷可用驗證，不改變其法律或技術語意。 |
| 問題中心顯示新增／持續／已修復／再次出現 | **採納但延後** | 必須先定義穩定指紋、規則版本與可比較範圍，否則「已修復」會產生假陽性。 |
| DNS 查詢直接進主報告 | **採納但非同步** | 觀測失敗不得拖垮或改變掃描結算；先顯示獨立區塊，再評估是否納入下載報告。 |
| Cloudflare URL Scanner 正式接入 | **條件式採納** | 先做 staff-only spike；只有 Unlisted 額度、隱私與資料保留條款可接受時才進會員 beta。 |
| GSC／GA4 分開呈現 | **採納** | 兩者定義、延遲與資源邊界不同，不可混成單一分數。 |
| GSC 先於 GA4 | **採納** | GSC 的網站資源對應較貼近專案；GA4 property／stream 不一定能由 hostname 唯一推導。 |
| 監測與提醒最後做 | **採納** | 必須等比較語意、排程成本與通知去重穩定。 |
| 八階段線性一路開發 | **修改** | 改成有 go/no-go 與回滾點的六個 release；外部整合各自可停用。 |

## 3. 核心領域模型

### 3.1 `SiteProject`（第一個 migration）

建議欄位：

- `id`：不可猜測的 UUID；網址可安全暴露，不沿用遞增 ID 作跨專案導覽。
- `owner`：`ForeignKey(User, CASCADE)`；第一版不抽象成 organization。
- `name`：會員顯示名稱。
- `canonical_url`：正規化後的公開 HTTP(S) URL，用於預填掃描，不代表固定掃描範圍。
- `hostname_ascii`：小寫、去尾點、IDNA ASCII 的精確 hostname，供唯一性與權限判斷。
- `default_scan_options`：只保存白名單欄位（categories、max pages、depth、robots、mode）；建立掃描時仍重新驗證與估價。
- `archived_at`、`created_at`、`updated_at`。

約束與規則：

- 第一版限制同一 owner 只能有一個相同 `hostname_ascii` 的未封存專案。
- `www.example.com` 與 `example.com` 是不同專案；若日後需要合併，另做明確的 host alias，不做隱性猜測。
- canonical URL 不得含帳密；query／fragment 預設剝除。若產品將來支援 path-scoped project，再另立 ADR 與唯一性規則。
- 專案只能封存，不級聯刪除掃描、報告或計費稽核資料。

### 3.2 `ScanJob.project`

- 新增 `ForeignKey(SiteProject, PROTECT)`，先 nullable 以完成資料遷移，驗證後再改為 non-null。
- 新掃描 API 由 path 或 body 接收 `project_id`，但目標 hostname 必須與專案精確 hostname 相同；不得只相信前端選擇器。
- 保留 `original_url`、`normalized_url`、`origin` 作不可變快照。專案改名或 canonical URL 變更不得回寫舊任務。
- 授權聲明與扣點仍綁 `ScanJob`；建立專案不建立 `AuthorizationConsent`。

### 3.3 網域驗證關係

第一版不把 `VerifiedDomain` 外鍵搬進專案，也不建立「GSC 已連線＝Argus 已驗證」捷徑；只有 Google 明確回報 `siteOwner` 且 property 涵蓋專案 hostname 時，才把該證據寫入既有驗證模型。建立主動掃描時依序檢查：

1. 專案屬於目前使用者。
2. 目標 hostname 屬於該專案。
3. 使用者有能涵蓋該 hostname 的有效 `VerifiedDomain`。
4. 使用者再次確認主動測試授權。

現有父網域涵蓋演算法在擴大使用前應另開安全工作項目，改用 Public Suffix List 判斷 registrable domain，避免把 public suffix 當成可涵蓋多租戶的父網域。

### 3.4 DNS 觀測

建議 `DnsObservationRun` ＋ `DnsObservationAnswer`，不要把整包結果塞進 `SiteProject`：

- run：project、觸發來源、resolver、queried_at、completed_at、status、error_code。
- answer：run、hostname、record_type、normalized_value、TTL、DNS response code、DNSSEC AD flag（如有）。
- 原始第三方 response 只在有除錯需要且完成 redaction 後短期保存；產品 UI 使用正規化欄位。

第一版查 `A`、`AAAA`、`CNAME`、`NS`。`MX`、`TXT`、`CAA` 只有對應檢測規則上線時才加入；尤其 TXT 可能包含驗證字串，不應無目的大量保存或展示。

### 3.5 跨掃描問題追蹤

不直接在 `Finding` 加一個可變 status。建議拆為：

- `IssueIdentity`：project、fingerprint、fingerprint_version、rule_id、category、stable page key、first_seen、last_seen、current_state。
- `IssueOccurrence`：issue、scan、finding、state_at_scan、observed_at。

指紋至少由「規則 ID＋規則版本＋正規化頁面 path／資源 key＋穩定證據 key」構成，不能使用可翻譯的 title／description。任何規則或指紋算法變更都要升版。

狀態判斷：

- `new`：首次在可比較掃描中出現。
- `persistent`：前一個可比較掃描也出現。
- `resolved`：後一個**成功完成且涵蓋相同 category、page scope、scan mode 與必要能力**的掃描沒有出現。
- `recurring`：resolved 後再次出現。
- `unknown`：掃描失敗、頁面未爬到、規則停用、scope 縮小或外部工具缺席；不得標成 resolved。

### 3.6 外部整合（後續 release）

GSC 與 GA4 共用連線外殼、分開資源與資料表：

- `ExternalConnection`：owner、provider、encrypted credential reference、scopes、status、last_success_at、last_error_code、revoked_at。
- `ProjectExternalResource`：project、connection、外部 property/resource ID、授權範圍、選取時間。
- provider-specific daily aggregate table：保留來源日期、同步時間、維度與資料品質旗標。

Token 必須後端加密保存、禁止進 log／serializer；支援 refresh、撤銷、重新授權、刪除與最小唯讀 scope。GA4 由使用者選 property／data stream，不以 hostname 自動綁定。

## 4. API、權限與相容策略

### 4.1 建議 API

- `GET/POST /api/projects/`
- `GET/PATCH /api/projects/{project_id}/`
- `POST /api/projects/{project_id}/archive/`
- `GET/POST /api/projects/{project_id}/scans/`
- `GET /api/projects/{project_id}/overview/`
- `GET /api/projects/{project_id}/history/`
- `GET /api/projects/{project_id}/issues/`（問題追蹤 release 才加入）
- `POST /api/projects/{project_id}/dns-observations/`

每個 nested endpoint 先以 `owner=request.user` 取得 project，再查子資源；不能先用 scan ID 查出物件後才比對。後端測試需涵蓋 project IDOR、跨專案 scan ID、封存專案、錯誤 hostname 與 staff 行為。

### 4.2 舊 API 與深連結

- `/api/scans/{id}/`、報告、截圖與取消端點第一輪保留，仍以使用者過濾；serializer 增加 `project_id`。
- `/api/scans/` 暫時保留，新增掃描要求 `project_id`；一個 release 後再評估移除舊列表語意。
- 舊 `/scans/{id}` 深連結先載入 scan，再導向 `/projects/{project_id}/scans/{id}` 或在相容 shell 中補 project context。
- `/dashboard` 可先成為「所有網站」入口，不要在 migration 完成前直接刪除。

## 5. 會員區資訊架構

### 5.1 路由

- `/projects`：所有網站。
- `/projects/new`：新增網站，不啟動掃描。
- `/projects/:projectId/overview`：專案總覽。
- `/projects/:projectId/scans` 與 `/scans/:scanId`：建立、列表與詳情。
- `/projects/:projectId/issues`：問題中心（release 3）。
- `/projects/:projectId/reports`：報告與歷史比較。
- `/projects/:projectId/analytics`：GSC／GA4（release 5）。
- `/projects/:projectId/integrations`：網域驗證與外部連線。
- `/projects/:projectId/settings`：專案設定與封存。

### 5.2 導覽判斷

- 網站切換器是 project context 控制器，不只是 filter；切換後導向另一專案的同類頁面，若該頁尚不可用則回 overview。
- 「通知、主題、帳戶」維持全域；「方案與用量」是跨專案入口。
- 不建立網站時顯示真正的 empty state；「所有網站」不是假的預設專案。
- 行動版仍需在首屏看得到目前網站與切換入口。
- 管理員後台保持獨立，不共用會員 project sidebar。

### 5.3 總覽內容優先序

第一版只顯示能由既有資料可靠回答的內容：最新掃描狀態、與前一個可比較掃描的分數差、重要 findings、驗證狀態、來源與更新時間。GSC／GA4 卡片在整合上線前不顯示假資料或 disabled 儀表板。

## 6. Cloudflare 能力落地邊界

### 6.1 1.1.1.1 DNS over HTTPS

採用 Cloudflare JSON DoH GET endpoint，帶 `name`、`type` 與 `Accept: application/dns-json`。但實作時還必須：

- connect/read timeout、有限重試與全域 concurrency cap。
- 僅允許正規化後的專案 hostname；不得成為任意 DNS relay。
- 將 NXDOMAIN、NODATA、timeout、SERVFAIL 分開，不用空陣列代表全部情況。
- 答案排序／去重後比較；對多 CDN、GeoDNS、輪詢與 TTL 保留「觀測差異」措辭，不直接判錯。
- 若要比較「兩個解析視角」，第二個來源必須明確命名並獨立保存；不能把本機 resolver 當成未標示的真相。
- DNS job 失敗不改變 `ScanJob.status`，也不阻止掃描結算／報告下載。

### 6.2 Cloudflare URL Scanner

先做不面向會員的 spike，go/no-go 條件如下：

1. Argus 帳戶有可接受的 Unlisted 額度；Free/Radar 只有 Public 額度時直接 **no-go**。
2. 法務／隱私說明、資料保存與刪除策略已確認；Unlisted 不是私密儲存。
3. 只允許已驗證專案的公開 URL，重新套用 Argus SSRF／DNS rebinding／redirect 安全策略。
4. 禁止提交 userinfo、fragment、敏感 query、測試帳密、cookie、Authorization 或自訂會員 header。不能只靠關鍵字刪參數後就宣稱安全；有 query 的 URL 預設拒絕或要求改掃無參數 canonical URL。
5. 明確 opt-in，顯示「URL 將交由 Cloudflare 從外部環境存取」。
6. 使用獨立 Celery queue、rate limit、最大 polling 時間與 terminal states；執行中的 `404` 不能當永久失敗。
7. Cloudflare 失敗、逾時或 quota exhausted 只讓外部證據成為 unavailable，不改變 Argus 主報告。

通過後才建立 `ExternalPageObservation`，保存 scan、page、provider、external ID、visibility、submitted URL、status、observed_at、expires_at 與經白名單擷取的摘要。截圖與完整 network log 是否落地需另做容量與個資評估；第一版不永久複製完整第三方 payload。

Agent Readiness 只能顯示成「Cloudflare 外部觀測」，不可覆蓋 Argus AEO finding，也不可直接進 Argus 分數。

## 7. Release 計畫與驗收閘門

### Release 0：契約與基線（先做，無 UI）

工作：

- 以測試鎖住現有掃描建立、扣點／退款、網域驗證、報告與舊深連結。
- 決定 hostname 正規化、專案唯一性、封存與舊資料合併規則。
- 取得資料快照統計：每位使用者 distinct hostname／origin、異常 URL、同 host 多 scheme／port 數量。

完成條件：遷移規則可用 fixture 重播，且有明確 rollback；尚未改任何會員流程。

### Release 1：網站專案垂直切片（建議第一個可交付版本）

工作：

- `SiteProject`、`ScanJob.project`、兩階段資料 migration 與約束。
- Projects API、所有網站、網站切換器、專案 overview／scans／history。
- 新掃描強制 project context，但完整沿用既有授權、估價、預扣與 queue。
- 舊 API／URL 相容與專案層 IDOR 測試。

舊資料 migration：

1. 由 `normalized_url` 解析 IDNA hostname，不以 display `origin` 字串直接分組。
2. 每個 `(user, hostname)` 建一個專案；名稱先用 hostname。
3. 同 host 的 HTTP／HTTPS／port 任務歸入同一專案，但仍保留各自 scan snapshot。
4. 無法解析的資料寫 migration audit 並停止上線，不建立「無歸屬」常態狀態。
5. 驗證所有 scan 都有 project 後才把 FK 改 non-null。

驗收：舊報告可開、跨專案不可見、建站不扣點、掃描扣退點與改版前相同、手機可切站。此 release 完成後才把 project 路由設為預設入口。

### Release 2：DNS 外部觀測

工作：

- DNS 模型、受限 DoH client、background task、API 與報告／總覽區塊。
- 明確錯誤分類、TTL／時間／resolver 標示、資料保留清理工作。

驗收：以 A／AAAA／CNAME／NS fixture 與真實受控網域驗證；NXDOMAIN、timeout、答案順序差異均正確；外部 DNS 失敗不影響掃描完成與計費。

### Release 3：問題中心與可信比較

工作：

- 指紋規格與版本、IssueIdentity／Occurrence backfill、scope comparability service。
- 問題列表、狀態篩選、scan-to-scan compare API 與 UI。

驗收：用兩到三次真實掃描重播 new／persistent／resolved／recurring；縮小頁數、取消維度、爬取失敗或規則停用只能得到 unknown，不能誤報 resolved。

### Release 4：URL Scanner 受控驗證

工作：

- staff-only spike、方案／可見性／quota 驗證、資料分類與 threat model。
- 僅在 go 條件通過後實作 queue、polling、摘要與會員 opt-in beta。

驗收：真實 Unlisted submission、執行中 404、完成、逾時、quota、第三方失敗、敏感 URL 拒絕均有測試；任一 no-go 條件存在就保持 feature flag 關閉。

### Release 5：GSC，之後才是 GA4

GSC：唯讀 OAuth、列出使用者可存取的 property、明確選取 project resource、daily sync、資料日期／時區／更新時間／資料不完整提示。不得把 API top rows 當完整明細。

**2026-10-02 實作狀態：**後端 OAuth、property 綁定、date 維度 Search Analytics 同步、owner-scoped API 與 `siteOwner` 網域驗證已完成；會員分析頁 UI 與排程同步仍待後續交付。

GA4：獨立 opt-in、使用者選 property／stream、分開呈現 users／sessions／events／configured key events；不把 GSC clicks 當 GA4 sessions，也不虛構未設定事件。

驗收：token refresh／revocation、錯誤資源、跨使用者／跨專案 IDOR、重跑同步冪等、provider quota 與斷線資料保留政策均通過。

### Release 6：監測與提醒

工作：排程、成本上限、quiet hours、事件去重、delivery log、重試與退訂。提醒只引用已完成 scan 或有明確資料日期的外部同步。

驗收：每則通知包含 project、觸發規則、比較基準、觀測時間與 evidence link；同一事件不重複轟炸，封存／停用連線後不再排程。

## 8. 測試、觀測與回滾

### 8.1 必要測試層

- Model／migration：唯一性、IDNA、封存、FK 完整性、舊資料回填。
- API：owner scoping、nested IDOR、封存專案、hostname mismatch、pagination。
- 計費：專案 CRUD 零交易；掃描 hold／settlement／refund 與既有行為一致。
- Task：DNS／URL Scanner retry、timeout、idempotency、服務失敗隔離。
- 前端：切站時 URL 與資料同步、舊深連結、empty/loading/error、390px 無水平捲動。
- E2E：建站 → 掃描 → 完成 → 歷史 → 切站；A 專案不能看到 B 的任何資源。

### 8.2 觀測指標

- project migration 未歸屬數（上線必須為 0）。
- project-scoped API 的 403／404、hostname mismatch 次數。
- DNS 成功率／延遲／rcode；外部 URL scan quota／逾時／完成率。
- 掃描建立成功率與 hold/refund 對帳；改版前後不可出現異常差異。
- OAuth refresh 失敗、同步 lag、provider quota errors。

### 8.3 回滾原則

- Release 1 採 expand-and-contract：先加 nullable FK 與雙讀驗證，再切 UI，最後才收緊 non-null；舊 `/scans` 入口至少保留一個 release。
- 外部整合全部有 server-side feature flag，停用不需回滾核心 schema。
- migration 不刪 `origin`、不重寫 scan snapshot、不刪歷史 finding 或計費紀錄。

## 9. 外部規格核實

- Cloudflare URL Scanner create API 支援 `Public`／`Unlisted` visibility 與 `agentReadiness`；Unlisted 只是不進列表／搜尋，知道 scan ID 仍可存取：<https://developers.cloudflare.com/api/resources/url_scanner/subresources/scans/methods/create/>。
- Cloudflare 方案限制頁目前列出 Free/Radar 每月 5,000 Public、0 Unlisted、每 10 秒 1 次：<https://developers.cloudflare.com/security-center/investigate/scan-limits/>。
- URL Scanner 執行中 result endpoint 可能回 404，官方建議每 10–30 秒輪詢：<https://developers.cloudflare.com/radar/investigate/url-scanner/>。
- Cloudflare JSON DoH 使用 GET 與 `Accept: application/dns-json`：<https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/>。
- Search Analytics API 受內部限制，只保證回傳 top rows，不保證所有資料列：<https://developers.google.com/webmaster-tools/v1/searchanalytics/query>。
- GA4 Data API 有 property token quota，應納入排程與錯誤處理：<https://developers.google.com/analytics/devguides/reporting/data/v1/quotas>。

## 10. 最終建議

1. **現在批准 Release 0–1**：網站專案資料模型與完整垂直切片是後續所有功能的真正地基。
2. **DNS 移到第二個 release**：它值得早做，但不應與最危險的資料歸屬 migration 同批上線。
3. **問題中心優先於行銷分析整合**：它直接完成「修復後再掃描驗證」的 Argus 核心閉環。
4. **URL Scanner 維持實驗功能**：沒有 Unlisted 額度或清楚隱私條款就不對會員開放；不要為了功能數量接受 Public 掃描風險。
5. **GSC 與 GA4 分批**：先驗證 OAuth／資源選取／同步基礎，再複用到 GA4；兩者 UI 與指標語意保持分離。
6. **不要先做通知中心空殼**：沒有穩定的比較與事件模型，通知只會放大誤報。
