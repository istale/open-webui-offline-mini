# KLS Loop v1 — SAFETY (No-Leak Exam Feedback)

本文件落地「不可洩題」規則（a）。

## 規則 a：禁止直接洩題，但允許理由/概念缺口
Exam Bot 回饋給 KLS 的內容：
- ✅ 允許：概念性理由、錯因分類、知識缺口清單、建議補強方向
- ❌ 禁止：題幹原文、選項全文、數字/關鍵特徵、可直接逆推出題目答案的細節

## 可輸出的回饋格式（建議）
對每題輸出：
- `result`: correct | incorrect | unknown
- `rationale`: 2~6 句概念性理由（避免引用題目內容）
- `gaps`: 缺口概念列表（例如「XXX 定義不清」「YYY 前提條件漏掉」）
- `study_actions`: 建議回補 KB 的行動（例如「在材料 A 的 slide_0023 補充 ZZZ 例外」）

## 遮罩策略
- 遇到數字：以 `<NUM>` 代替
- 遇到題幹關鍵句：改寫成抽象描述
- 禁止引用 `domain_knowledge_exams/` 的原文片段

## 稽核
- KLS 端應保留 Exam Bot 回饋的原始 JSON（僅內部）
- 若發現回饋包含疑似洩題內容：標記為 violation，且不得寫入 KB
