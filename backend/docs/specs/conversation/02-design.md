# 02 设计：会话记录

- 功能 slug：`conversation`
- 日期：2026-10-26

## 数据模型

### conversation

| 列 | 类型 | 约束 |
| --- | --- | --- |
| id | BIGSERIAL | PRIMARY KEY |
| user_id | BIGINT | NOT NULL，FK → `account.id`，建索引 |
| title | VARCHAR(255) | NULL |
| state | BIGINT | DEFAULT 1（1 正常，2 删除） |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP，ORM `onupdate` 刷新 |

### message

| 列 | 类型 | 约束 |
| --- | --- | --- |
| id | BIGSERIAL | PRIMARY KEY |
| conversation_id | BIGINT | NOT NULL，FK → `conversation.id`，建索引 |
| role | VARCHAR(20) | NOT NULL，CHECK IN ('user','assistant','system') |
| content | TEXT | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |

> 相较用户给出的 DDL：按确认结果补充了两个外键与查询索引（FK 不自动建索引）；其余结构保持一致。

## 模块结构（沿用现有分层）

```
app/
├── model/conversation.py       # Conversation、Message ORM
├── schema/conversationDTO.py   # ConversationDTO、MessageDTO、CreateConversationRequest
├── schema/pageDTO.py           # PageResult[T] 通用分页结构
├── mapper/conversationMapper.py
├── mapper/messageMapper.py
├── service/conversationService.py
└── controller/conversationController.py
```

## 接口定义

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/conversation?page=1&page_size=20` | 当前用户会话分页（state=1，updated_at 倒序） |
| POST | `/conversation` | 创建会话，body `{title?: string}`，201 |
| GET | `/conversation/{id}` | 会话详情 |
| GET | `/conversation/{id}/messages?page=1&page_size=20` | 消息分页（created_at 正序） |
| DELETE | `/conversation/{id}` | 软删除（state=2） |

所有接口需登录（全局鉴权自动生效），并在处理器内注入 `TokenPayload` 取得 `user_id`。

## 分页结构

```python
class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
```

- `page` ≥ 1，默认 1；`page_size` 1~100，默认 20。
- 查询统一 `select(...).order_by(...).offset(...).limit(...)` + `select(func.count())` 统计总数。

## 数据隔离与错误处理

- 查询会话一律附加 `Conversation.user_id == current_user.user_id AND Conversation.state == 1`。
- 不存在 / 不属于当前用户 / 已删除 → 404 `Conversation not found`（统一措辞，避免泄露存在性）。
- 删除时同步设置 `state=2`，ORM `onupdate` 刷新 `updated_at`。
