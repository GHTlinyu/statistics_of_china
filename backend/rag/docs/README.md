# RAG搭建知识库流程-中国国家统计年鉴（2025）

## 一、源数据获取

- 源数据来自中国国家统计局官网，具体地址：https://www.stats.gov.cn/sj/ndsj/2025/indexch.htm
- 网页数据使用AI智能体工具（Codex、deepseek harness、Claud code等）获取，并放入`rag\中国统计年鉴2025源数据`文件夹下

## 二、源数据预处理
> 目的：获取的原始数据格式是图片，而给到大模型的是文本

- 使用**OCR模型**识别图片并转换为markdown格式文档，markdown格式十分结构化，为下一步文档分块准备
- 使用paddleocr V6模型提取
- 使用chatgpt（其他模型）识别统计年鉴原始图片，给出实现提取脚本代码细节的**SKILL**，利用这个SKILL实现的代码得到的成果更准确
- 提取出的数据放入`rag\中国统计年鉴2025_表格数据_v6.md`
- 检查**最低置信度小于0.7**数据
- 文档`rag\中国统计年鉴2025_表格数据_v6.md`中一些大表格从语义上可以再化分出子项，避免将大量无相关数据给到大模型，引起上下文污染
- 使用AI工具从语义和结构上划分出子项，放入`rag\中国统计年鉴2025_表格数据_v6_拆分.md`

## 四、文档分块
> 目的： 给到大模型最小最相关文档块内容，省token和回答内容清晰

- 从`rag\中国统计年鉴2025_表格数据_v6_拆分.md`文档中基于最小内容拆分,例如：`## C01-02`表示章节，那么下其最小子项是`### 人口(万人)`
- 分块数据放入`rag\中国统计年鉴2025_chunks.json`

注：description字段是文档增强部分加入的

## 五、测试集
> 目的： 测试向量模型以及文档增强后检索的Recall,MRR,NDCG指标是否达到要求

- 使用AI工具为`rag\中国统计年鉴2025_chunks.json`中的每个数据加上`description字段`，该字段含义是文档块内容的一句话总结，后续向量检索就是检索这句话
- 不使用原始文档块做向量检索原因是原始文档块是表格，语义匹配指标不能达到要求
- 根据`rag\中国统计年鉴2025_chunks.json`裁剪出`rag\evaluate_retrieval\中国统计年鉴2025_chunks_meta.json`，并为每一个数据加上唯一标识chunk_id，chunk_id生成规则：sha256("中国统计年鉴2025|{title}|{序号}")，
- 使用AI工具为`rag\evaluate_retrieval\中国统计年鉴2025_chunks_meta.json`生成检索测试集，这里为每一个数据生成一项，放入`rag\evaluate_retrieval\中国统计年鉴2025_检索测试集.jsonl`
- 给出测试脚本`rag\evaluate_retrieval\evaluate_retrieval_jina.py`,这里使用了**jinaai/jina-embeddings-v5-text-small**向量模型

测试结果：
```
========== 检索评测结果 ==========
有效问题数：1229
目标文档不存在数：0
Recall@1：0.7950
MRR：0.8717
Recall@5：0.9691
MRR@5：0.8682
NDCG@5：0.8939
Recall@10：0.9878
MRR@10：0.8709
NDCG@10：0.9000
Recall@20：0.9984
MRR@20：0.8716
NDCG@20：0.9028

文件结果：rag\evaluate_retrieval\retrieval_result.json
```

## 六、存入数据库

- 基于postgresql+pgvector搭建向量数据库，后续向量检索由postgresql负责
- 数据结构有文档表、章节表、文档块表

文档表
```sql
CREATE TABLE documents (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    title           VARCHAR(500) NOT NULL,
    document_type   VARCHAR(50),
    year            SMALLINT,

    file_name       VARCHAR(255),
    file_path       TEXT,
    file_format     VARCHAR(20),
    file_size       BIGINT,
    file_hash       VARCHAR(128),

    description     TEXT,
    source          VARCHAR(500),

    status          VARCHAR(30) NOT NULL DEFAULT 'pending',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE documents IS '知识库文档表';

COMMENT ON COLUMN documents.id IS '文档主键';
COMMENT ON COLUMN documents.title IS '文档标题';
COMMENT ON COLUMN documents.document_type IS '文档类型，例如统计年鉴';
COMMENT ON COLUMN documents.year IS '年鉴年份';
COMMENT ON COLUMN documents.file_name IS '原始文件名';
COMMENT ON COLUMN documents.file_path IS '原始文件存储路径';
COMMENT ON COLUMN documents.file_format IS '原始文件格式，例如 pdf、docx、md';
COMMENT ON COLUMN documents.file_size IS '原始文件大小，单位字节';
COMMENT ON COLUMN documents.file_hash IS '原始文件哈希，用于文件去重';
COMMENT ON COLUMN documents.description IS '文档描述';
COMMENT ON COLUMN documents.source IS '文档来源';
COMMENT ON COLUMN documents.status IS '文档处理状态';
COMMENT ON COLUMN documents.created_at IS '创建时间';
COMMENT ON COLUMN documents.updated_at IS '最后更新时间';
```

章节表
```sql
CREATE TABLE document_chapters (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    document_id     BIGINT NOT null,
                   

    parent_id       BIGINT,

    title           VARCHAR(500) NOT NULL,
    chapter_no      VARCHAR(100),
    chapter_level   SMALLINT NOT NULL DEFAULT 1,
    sort_order      INTEGER NOT NULL DEFAULT 0,

    page_start      INTEGER,
    page_end        INTEGER,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()

);
--
COMMENT ON TABLE document_chapters IS '文档章节表';
COMMENT ON COLUMN document_chapters.document_id IS '所属文档ID';
COMMENT ON COLUMN document_chapters.parent_id IS '父章节ID，NULL表示顶级章节';
COMMENT ON COLUMN document_chapters.title IS '章节标题';
COMMENT ON COLUMN document_chapters.chapter_no IS '原始章节编号';
COMMENT ON COLUMN document_chapters.chapter_level IS '章节层级，从1开始';
COMMENT ON COLUMN document_chapters.sort_order IS '同级章节排序号';
COMMENT ON COLUMN document_chapters.page_start IS '起始页码，可为空';
COMMENT ON COLUMN document_chapters.page_end IS '结束页码，可为空';
```

文档块表
```sql
CREATE TABLE document_chunks (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chunk_id        VARCHAR(100) NOT NULL,
    document_id     BIGINT NOT NULL,
    chapter_id      BIGINT,
    chunk_index     INTEGER,
    chunk_type      VARCHAR(30) NOT NULL DEFAULT 'text',
    title           VARCHAR(500),
    content         TEXT NOT NULL,
    page_start      INTEGER,
    page_end        INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE document_chunks IS '文档分块表';
COMMENT ON COLUMN document_chunks.id IS '数据库内部主键';
COMMENT ON COLUMN document_chunks.chunk_id IS '稳定的业务标识，由应用程序生成';
COMMENT ON COLUMN document_chunks.document_id IS '所属文档ID';
COMMENT ON COLUMN document_chunks.chapter_id IS '所属章节ID';
COMMENT ON COLUMN document_chunks.chunk_index IS '分块在文档中的顺序';
COMMENT ON COLUMN document_chunks.chunk_type IS '分块类型，如 text、table_rows、note';
COMMENT ON COLUMN document_chunks.title IS '分块标题';
COMMENT ON COLUMN document_chunks.content IS '分块正文内容';
COMMENT ON COLUMN document_chunks.page_start IS '起始页码，可为空';
COMMENT ON COLUMN document_chunks.page_end IS '结束页码，可为空';
```