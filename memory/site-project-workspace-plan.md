# 2026-09 網站專案工作區規劃決策

## 決策摘要

- 會員區後續以 `SiteProject` 作為長期工作單位，`ScanJob` 維持不可變時間點快照。
- 第一個交付版本只做 project model、舊資料回填、權限、相容路由與既有掃描垂直流程；DNS 改到第二個 release。
- 專案以精確 IDNA hostname 為邊界；`www`、apex 與其他子網域不自動合併。
- `VerifiedDomain` 保持使用者層級的主動掃描技術閘門；GSC 連線本身不等同驗證，但 Google 回報 `siteOwner` 且 property 涵蓋專案 hostname 時可作為第四種驗證證據。
- 建立專案不扣點；建立掃描必須沿用既有授權、估價、原子預扣、排隊與退款鏈。
- 跨掃描問題追蹤使用版本化 fingerprint 與 occurrence；只有後續成功且 scope 可比較時才能判定 resolved。
- DNS 是獨立、帶 resolver 與觀測時間的非同步證據，失敗不影響主掃描與計費。
- Cloudflare URL Scanner 先做 staff-only spike；沒有 Unlisted 額度、隱私與保留政策未完成時不得對會員開放。
- GSC 與 GA4 分批、分頁、分資料語意；不合成 Argus 健康分數，也不宣稱因果。

## 實作入口

完整規劃、release gate、資料遷移、驗收與回滾條件見：

- [`docs/superpowers/plans/2026-09-29-member-site-project-workspace.md`](../docs/superpowers/plans/2026-09-29-member-site-project-workspace.md)

## 2026-09-30 實作狀態

- 已完成 `SiteProject`、舊掃描回填、`ScanJob.project`、owner-scoped API、封存與 project filters。
- 已完成所有網站、新增網站、頂部切換器，以及專案總覽／掃描／問題／歷史／設定工作區。
- 舊 `/dashboard`、`/scans`、`/history` 與 scan detail 路由保留相容；GSC 後端、資料同步與 owner 驗證已於 2026-10-02 完成，DNS、URL Scanner、GA4 與監測提醒仍未實作。

## 2026-09-30 UX 修正

- 初版把全高深色側欄、網站切換器與四個全域連結同時塞進會員框架，造成頂部換行、側欄過重、內容對比不足，雖然功能可用但破壞 Argus 原本的精緻度。

- 修正版將側欄收斂為內容旁的 compact navigation card，頂部只保留首頁／所有網站與網站切換；主要動作回到虹膜青，琥珀色不再佔據工作區主視覺。
- 沒有掃描資料時不顯示三張空數字卡，而是提供第一份診斷基準的流程引導；桌機與 390px 行動版均以實際登入截圖驗證。
- PR #9 與 `main` 同時新增工作區檔案而產生 add/add 衝突；合併時保留已完成 UX 修整的版本，未回退成 `main` 中較早的初版介面。

## 2026-09-30 UX 二次修正

- 使用者確認前版仍有典型 AI dashboard 問題：裝飾性雷達圖、巨大空狀態、過多玻璃卡片與膠囊控制，讓功能層級比改版前更粗糙。
- 工作區改採內容優先的平面層級：側欄不再包成浮動卡片、切換器回歸標準表單控制、摘要卡合併為同一資料列，空狀態只保留一句說明與單一操作。
- 行動版 grid 必須明確設定 `align-content: start`；否則工作區的 `min-height` 會拉開兩個 grid row，造成導覽與內容間出現大段空白。
- 2026-10-01 合併 PR #10 時，`main` 仍是 UX 二次修正前的工作區版本；四個 add/add 衝突均保留 PR head 的內容優先版面，避免雷達圖、浮動玻璃側欄與行動版空白問題回歸。

## 2026-10-02 PR #11 衝突處理

- 合併 `main` 時保留較新的 GSC 實作狀態：連線本身不等同網域驗證，只有涵蓋專案 hostname 的 `siteOwner` property 能成為驗證證據。
- 規劃文件仍保留尚未交付的 DNS、Cloudflare URL Scanner、GA4 與監測提醒，不以已完成的 GSC 後端狀態推論其他階段也已完成。
