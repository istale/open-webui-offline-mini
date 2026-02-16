# KLS Loop v1 — DATA CONTRACT

本文件定義 KLS v1 在離線 Linux 上「只處理上傳後的檔案」的硬性契約。

## 1) 教材/報告（Domain Knowledge Materials）入口

根目錄：
- `domain_knowledge_materials/`

每一份教材/報告一個資料夾（稱為 deck）：

```
domain_knowledge_materials/
  <deck_id>__<title>/
    meta.json
    slides/
      slide_0001.png
      slide_0002.png
      ...
    source.pdf            (可選：僅保存，不納入 pipeline)
```

### 必要檔案
- `slides/slide_*.png`：必須存在（一頁一檔）

### 可選檔案
- `source.pdf`：只保存，不做解析/切頁/抽取（v1 選項 A）

### meta.json 建議欄位
最少：
- `title`
- `tags`（可空）
- `created_at`（可空）
- `notes`（可空）

## 2) 考題（Domain Knowledge Exams）入口

根目錄：
- `domain_knowledge_exams/`

建議結構：

```
domain_knowledge_exams/
  <exam_set_id>__<title>/
    meta.json
    questions/
      q_0001.png
      q_0002.png
      ...
    answers/              (可選：若存在，KLS 不可直接洩題)
```

v1 重點：Exam Bot 的回饋必須遵守不洩題規則（見 `SAFETY.md`）。

## 3) 知識庫（KB）輸出

```
kb/
  concepts/
    <concept>.md
  indices/
    embeddings.jsonl (或 sqlite)
```

每個 concept 檔必須包含來源引用：
- `<deck_id>/slide_####`

## 4) 追蹤與日誌

```
traces/
  ingest_runs/*.jsonl
  exam_runs/*.jsonl
```

v1 原則：所有自動生成/更新都要可追溯到來源 slide。
