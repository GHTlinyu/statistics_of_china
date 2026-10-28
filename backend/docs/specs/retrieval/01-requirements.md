# 01 需求规格：文档块向量检索与重排

- 功能 slug：`retrieval`
- 状态：已确认（融合权重、召回参数为默认值，待复核）
- 日期：2026-10-28

## 背景与目标

RAG 知识库数据已入库：`document_chunks` 保存分块正文，`chunk_retrieval` 保存标题、总结及两列 1024 维向量。主工作流需要「问题 → 相关文档块」的检索能力，并要求以 tool 形式暴露，供后续 Agent 直接调用。

向量与重排均通过外部模型 API 完成，服务内不加载本地推理模型。

## 需求条目

| 编号 | 需求 | 说明 |
| --- | --- | --- |
| R1 | 检索主表 | `chunk_retrieval`：`chunk_id`、`title`、`title_embedding VECTOR(1024)`、`summary`、`summary_embedding VECTOR(1024)`、`created_at`、`updated_at`。 |
| R2 | 向量接口 | OpenAI 兼容的 `POST /embeddings`，模型 `jinaai/jina-embeddings-v5-text-small`，1024 维。 |
| R3 | 任务区分 | 查询用 query 任务，入库用 document 任务（Jina：`retrieval.query` / `retrieval.passage`）。 |
| R4 | summary 召回 | 只用 `summary_embedding` 计算余弦相似度召回；`title` 不参与检索打分。没有 summary 向量的分块不参与召回。 |
| R5 | 重排 | 调用 Jina Rerank 接口对候选片段重新打分排序。 |
| R6 | 正文回表 | 以 `chunk_id` 关联 `document_chunks.content` 取片段正文。 |
| R7 | tool 化 | 暴露 `search_yearbook(query, top_k=5)`，返回 JSON 字符串（正文完整返回，不截断），供 Agent 调用。 |
| R8 | 配置 | `.env` 提供 `LLM_EMBEDDING_*` 与 `LLM_RERANK_*`；缺失时给出明确报错。 |
| R9 | 降级 | 重排失败退回向量排序；embedding 失败视为检索失败并抛错。 |
| R10 | 维度校验 | 返回向量必须为 1024 维，否则报错。 |
| R11 | 同步 | 检索链路为同步实现，是否放入线程池由调用方决定。 |

## 非目标

- 建向量索引（本期不建，走全表扫描）
- 重写入库脚本（数据已落库）
- 把主工作流的检索节点改成 ReAct / 多步工具调用（后续）
- 查询改写、多路召回、结果缓存
- 前端展示与交互

## 验收标准

1. 配置齐全时，`ChunkRetriever(db).search(query, top_k, top_n)` 返回按重排分数排序、带正文的片段。
2. 未配置 embedding 凭据时，报错信息列出缺失项，且不发起网络请求。
3. 向量维度不符时立即报错。
4. 重排接口失败时仍返回向量排序结果，不中断调用方。
5. `search_yearbook` 作为 LangChain tool 可被 `.invoke({"query": ...})` 正常调用。

## 变更记录

| 日期 | 变更 | 原因 |
| --- | --- | --- |
| 2026-10-28 | 初稿 | 用户提出检索与重排需求 |
