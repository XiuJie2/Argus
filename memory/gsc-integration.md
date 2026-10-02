# Google Search Console 整合決策

- GSC 放在獨立 `integrations` app，不與 Argus 登入身分或掃描狀態機混合。
- OAuth scope 固定為 `webmasters.readonly`；正式 callback 無尾斜線：`https://ars.clouda.dpdns.org/api/integrations/gsc/callback`。
- callback 用資料庫一次性 state 綁定 user + SiteProject，不依賴前端 JWT／session。
- Token 以 Fernet 加密保存；API、log 與錯誤訊息不得輸出 token。
- `siteOwner` 且 Domain property 涵蓋 hostname，或 URL-prefix property 是精確 host 根路徑，才是所有權證明；子路徑 owner 與 full/restricted user 只能讀資料。
- Search Analytics 第一版只同步 date 維度的 clicks、impressions、CTR、position；不與 Argus 分數合成，也不宣稱因果。
- GSC owner 驗證寫入既有 `VerifiedDomain(method=gsc)` 並沿用 90 天 TTL；同步可續期，但仍保留掃描授權勾選。
- 2026-10-02 補齊會員可操作入口：專案設定會顯示涵蓋目前 hostname 的有效驗證，並提供 GSC 授權／property 選擇及 DNS／HTML 備援入口；不能再只以後端已有 endpoint 視為功能完成。
