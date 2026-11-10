# Rate Limiter Handbook

Original SkillCorpus fixture (MIT). Multi-chapter technical primer with bilingual notes.

## Chapter 1 — Token Bucket Basics

A **token bucket** admits requests while tokens remain. Tokens refill at a fixed
rate `r` up to capacity `b`. A request of cost `c` consumes `c` tokens.

Unique anchor phrase: `TOKEN_BUCKET_REFILL_ANCHOR`.

中文要点：令牌桶以速率 r 补充令牌，桶容量为 b。

## Chapter 2 — Sliding Window Counter

The sliding window counter stores request counts in time buckets and estimates
the rolling total. Prefer it when you need smoother limits than a fixed window.

Unique anchor phrase: `SLIDING_WINDOW_ANCHOR_42`.

## Chapter 3 — Distributed Limits

In a cluster, keep a **central counter** or a **local approximation** with
periodic sync. Central counters are accurate but add latency; local
approximations can over-admit under partitions.

Unique anchor phrase: `DISTRIBUTED_LIMIT_PARTITION_NOTE`.

跨章节提醒：分布式限流必须同时考虑 Chapter 1 的桶参数与本章的同步延迟。

## Chapter 4 — Client Retry Policy

Retries need jitter. Use full jitter: `sleep = random(0, min(cap, base * 2**attempt))`.
Never stampede a depleted bucket without backoff.

Unique anchor phrase: `FULL_JITTER_RETRY_RULE`.

## Chapter 5 — Observability

Export `accepted_total`, `rejected_total`, and `token_level`. Alert when
reject ratio exceeds 5% for five minutes.

Unique anchor phrase: `REJECT_RATIO_ALERT_5PCT`.

## Chapter 6 — Anti-Patterns

- Silent drop without metrics
- Shared global bucket across unrelated tenants
- Retrying immediately after HTTP 429 with zero jitter

Unique anchor phrase: `ANTIPATTERN_NO_JITTER_429`.
