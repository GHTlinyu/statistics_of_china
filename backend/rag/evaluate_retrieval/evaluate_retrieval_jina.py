import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

# #========== 检索评测结果 ==========
# 有效问题数：1229
# 目标文档不存在数：0
# Recall@1：0.7950
# MRR：0.8717
# Recall@5：0.9691
# MRR@5：0.8682
# NDCG@5：0.8939
# Recall@10：0.9878
# MRR@10：0.8709
# NDCG@10：0.9000
# Recall@20：0.9984
# MRR@20：0.8716
# NDCG@20：0.9028

# ---------- 配置 ----------
MODEL_NAME = "jinaai/jina-embeddings-v5-text-small"

BASE_DIR = Path(__file__).resolve().parent

DOCUMENTS_FILE = BASE_DIR.parent / "中国统计年鉴2025_chunks_meta.json"
QUERIES_FILE = BASE_DIR.parent / "中国统计年鉴2025_检索测试集.jsonl"

CACHE_DIR = Path("embedding_cache")
CACHE_DIR.mkdir(exist_ok=True)

DOC_VECTORS_FILE = CACHE_DIR / "jina_document_vectors.npy"
DOC_IDS_FILE = CACHE_DIR / "jina_document_ids.json"

TOP_K_VALUES = (5, 10, 20)


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    documents = json.loads(DOCUMENTS_FILE.read_text(encoding="utf-8"))
    queries = load_jsonl(QUERIES_FILE)

    # 检查数据
    assert documents, "文档数据为空"
    assert queries, "测试问题为空"

    doc_ids = [doc["chunk_id"] for doc in documents]
    assert len(doc_ids) == len(set(doc_ids)), "发现重复的 chunk_id"

    doc_texts = [
        f"{doc.get('title') or ''}\n{doc.get('description') or ''}".strip()
        for doc in documents
    ]

    print(f"文档数：{len(documents)}")
    print(f"问题数：{len(queries)}")

    model = SentenceTransformer(
        MODEL_NAME,
        trust_remote_code=True,
    )

    # ---------- 文档向量：只在缓存不存在时生成 ----------
    cache_valid = (
        DOC_VECTORS_FILE.exists()
        and DOC_IDS_FILE.exists()
        and json.loads(DOC_IDS_FILE.read_text(encoding="utf-8")) == doc_ids
    )

    if cache_valid:
        doc_vectors = np.load(DOC_VECTORS_FILE)
        print("已加载文档向量缓存")
    else:
        print("正在生成文档向量……")
        doc_vectors = model.encode(
            doc_texts,
            task="retrieval",
            prompt_name="document",
            normalize_embeddings=True,
            batch_size=16,
            show_progress_bar=True,
            convert_to_numpy=True,
        )

        np.save(DOC_VECTORS_FILE, doc_vectors)
        DOC_IDS_FILE.write_text(
            json.dumps(doc_ids, ensure_ascii=False),
            encoding="utf-8",
        )

    # ---------- 查询向量 ----------
    query_texts = [q["query"] for q in queries]

    print("正在生成查询向量……")
    query_vectors = model.encode(
        query_texts,
        task="retrieval",
        prompt_name="query",
        normalize_embeddings=True,
        batch_size=16,
        show_progress_bar=True,
        convert_to_numpy=True,
    )

    # 归一化向量点积 = 余弦相似度
    scores = query_vectors @ doc_vectors.T

    # ---------- 计算指标 ----------
    doc_id_to_index = {doc_id: i for i, doc_id in enumerate(doc_ids)}

    hits = []
    reciprocal_ranks = []
    ndcg_scores = {k: [] for k in TOP_K_VALUES}
    recall_scores = {k: [] for k in TOP_K_VALUES}
    missing_targets = []

    for qi, query in enumerate(queries):
        target_id = query["chunk_id"]

        if target_id not in doc_id_to_index:
            missing_targets.append((query["query_id"], target_id))
            continue

        ranking = np.argsort(-scores[qi])
        target_index = doc_id_to_index[target_id]

        # 目标文档在排序结果中的 1-based 排名
        rank = int(np.where(ranking == target_index)[0][0]) + 1

        hits.append(rank == 1)
        reciprocal_ranks.append(1.0 / rank)

        for k in TOP_K_VALUES:
            recall_scores[k].append(float(rank <= k))

            # 每题只有一个相关文档，且其相关度为 1。
            # 因此 NDCG@K 等于 1/log2(rank+1)，命中时才计分。
            ndcg = 1.0 / np.log2(rank + 1) if rank <= k else 0.0
            ndcg_scores[k].append(float(ndcg))

    evaluated = len(reciprocal_ranks)

    if evaluated == 0:
        raise ValueError("没有可评测的问题：请检查测试集 chunk_id 是否存在于文档文件中")

    print("\n========== 检索评测结果 ==========")
    print(f"有效问题数：{evaluated}")
    print(f"目标文档不存在数：{len(missing_targets)}")
    print(f"Recall@1：{np.mean(hits):.4f}")
    print(f"MRR：{np.mean(reciprocal_ranks):.4f}")

    for k in TOP_K_VALUES:
        print(f"Recall@{k}：{np.mean(recall_scores[k]):.4f}")
        print(
            f"MRR@{k}：{np.mean([rr if rr >= 1 / k else 0 for rr in reciprocal_ranks]):.4f}"
        )
        print(f"NDCG@{k}：{np.mean(ndcg_scores[k]):.4f}")

    # 输出每个问题的排名，方便排查错误案例
    results = []
    for qi, query in enumerate(queries):
        target_id = query["chunk_id"]
        if target_id not in doc_id_to_index:
            continue

        ranking = np.argsort(-scores[qi])
        target_index = doc_id_to_index[target_id]
        rank = int(np.where(ranking == target_index)[0][0]) + 1

        top_results = []
        for idx in ranking[:5]:
            top_results.append(
                {
                    "chunk_id": doc_ids[idx],
                    "title": documents[idx].get("title"),
                    "score": float(scores[qi, idx]),
                }
            )

        results.append(
            {
                "query_id": query["query_id"],
                "query": query["query"],
                "target_chunk_id": target_id,
                "target_rank": rank,
                "top5": top_results,
            }
        )

    Path("retrieval_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n详细结果已写入 retrieval_results.json")


if __name__ == "__main__":
    main()
