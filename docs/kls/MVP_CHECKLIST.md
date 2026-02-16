# KLS Loop v1 — MVP CHECKLIST

## MVP 目標
在離線 Linux 上跑通：
1) ingest 一個教材 deck（PNG slides）
2) 產出可追溯的 KB（concept files + embedding index）
3) ingest 一個考題 exam_set（PNG questions）
4) Exam Bot 回傳不洩題的 gaps/rationale
5) KLS 依 gaps 更新 KB（閉環一次）

## 驗收條件
- [ ] `domain_knowledge_materials/<deck>/slides/*.png` 可被偵測
- [ ] 產生 `kb/concepts/*.md` 且每個 concept 有來源引用 `<deck_id>/slide_####`
- [ ] embeddings index 生成成功（格式先簡單，後續可換 sqlite）
- [ ] `domain_knowledge_exams/<exam_set>/questions/*.png` 可被偵測
- [ ] Exam Bot 回饋不含題幹/選項/數字（符合 SAFETY a）
- [ ] traces 記錄 ingest/exam run（可統計）

## 先行假資料
- deck: 10 張 slides
- exam_set: 10 題 questions

## Not in MVP
- UI 完整化（先能跑通流程）
- 進階概念圖譜/依賴圖
- 多使用者/權限細節
