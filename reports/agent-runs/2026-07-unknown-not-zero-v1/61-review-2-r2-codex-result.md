# Review-2 r2 Result — Codex (`openai`), verdict REWORK

Transferred by the Human operator 2026-07-30 19:59 CST from a fresh read-only Codex
session run against `60-review-2-r2-codex.dispatch.md`. Range `ac8d493..7cadb88`.
Design involvement disclosed under D-6.

Format compliance: PASS — nine §7 labels, three closure lines, `[/TASK_RESULT]`.

`rework_count` → **2 of 3**. One formal round remains.

## Raw result, verbatim

```text
[TASK_RESULT v2]
任务 ID: review2r2-task1-codex
执行结果: completed（完成）
结果摘要: Review-2 REWORK：F2、F3及原有金额/时间戳回归均通过；最终扫查发现四处 live 业务状态写入仍静默吞异常，已发订单可能无持久化结论和可见事件，故不建议进入合并决策。
产物: [none（结论在终端输出）]
检查结果: [固定范围及修复差异核对; F2两站点与事件流核对; 测试承重/变异证据复核; F3勘误复核; M4守卫未退化; M6原始扫查发现P1; 定向55项通过; 全套1092 passed]
阻塞项: [P1：service.py:1721-1724、1734-1737、1754-1759、1776-1781 静默吞业务写失败]
本地北京时间: 2026-07-30 19:59:38 CST
下一步模型: opus5（记账人，Human 转交结果）
下一步任务: 记录本次 REWORK 与终端中的 P1 修复要求；由 Human 决定是否派发受限修复，修复后固定新提交范围先交叉 Review-1，再回到 Review-2。
评审结论: REWORK（返工）
问题记录: none（结论在终端输出）
修复要求: none（终端中已给出可执行要求）
[/TASK_RESULT]
```

M1-M5 passed: F2 repaired at both sites, the mutation evidence re-derived, F3's
correction judged adequate, the guard and T5 ground intact. M6 — the final sweep —
produced the P1.

## Bookkeeper verification — CONFIRMED, and worse than F2's two sites

All four verified against the code:

| Site | Swallowed call | Consequence |
|---|---|---|
| `:1721-1724` | `mark_attempt_rate_limited` | The rate-limited fact is lost, so the reconcile path consumes the failure counter for a 429 it was explicitly designed not to charge. The comment two lines above states why the stamp exists |
| `:1734-1737` | `resolve_attempt` (pause-class settle) | Both legs already terminal — **orders were sent** — and the settlement is discarded. `pair_outcome` stays NULL, the in-flight guard stalls the task, nothing is visible |
| `:1754-1759` | `resolve_attempt` (normal dispatch settle) | The main path. Orders sent, outcome computed, and its persistence can be lost silently. **A real order placed with no recorded conclusion** |
| `:1776-1781` | `mark_leg_querying` | A leg needing drain is never marked, so the drain never queries it — an in-flight order at the exchange is never reconciled and the pair never settles |

Codex's characterisation is accurate and material: **all four are after the POST**,
where F2's two were in the drain and recovery paths. Same family, larger blast
radius.

## My own error — the "exhaustive" negative result was false

`46-bookkeeper-verification-task1c.md` §4 said:

> `service.py` still contains three bare `except Exception: pass` blocks (`:995`,
> `:1024`, `:1062`) … So the F2 defect class is clear in `service.py`.
> 查过且没有, not 没查.

**That was wrong.** The mechanism is identifiable and it is mine: the command was

```text
grep -n "except Exception:" -A 1 service.py | grep -B 1 "pass" | head
```

— and `| head` truncated the output at ten lines. I reported a truncated grep as an
exhaustive sweep. A full enumeration finds **13** such sites in `service.py`, not 3.

This is the same error the entire stage exists to eliminate — asserting more than
the evidence supports — committed by the person auditing others for it, one file
after I wrote that the guard "is a speed bump, not a proof". It is the fourth time
an exhaustiveness claim in this stage proved false, and the second time it was mine.

## The full picture nobody has yet classified

A proper (untruncated) sweep of exception handlers whose body is a bare `pass` or
`continue`:

```text
service.py: 13 sites
   995  except Exception -> pass        (set_worker_exit_reason — audit write)
  1024  except Exception -> pass        (set_worker_exit_reason — audit write)
  1062  except Exception -> pass        (set_worker_exit_reason — audit write)
  1178  except Exception -> continue    ** resolve_leg_from_query — STATE WRITE, unclassified
  1279  except Exception -> pass        (the F2 fix's own narrow audit guard)
  1401  except Exception -> pass        (thread join, pragma: no cover)
  1410  except Exception -> pass        ** unclassified
  1632  except Exception -> pass        ** resolve_attempt, record path — unclassified
  1723  except Exception -> pass        Codex P1
  1736  except Exception -> pass        Codex P1
  1758  except Exception -> pass        Codex P1
  1780  except Exception -> pass        Codex P1
  1818  except Exception -> pass        (record_task_event — audit write, LEGITIMATE)
store.py: 1 site
   479  except (TypeError, ValueError) -> continue   ** unclassified
```

So beyond Codex's four there are **at least four more nobody has looked at**, and
the family has **three shapes**, not one: `pass`, `continue`, and a nested guard.
`:1178` is a `continue` around a state-authoritative leg write that also skips the
raw-response capture immediately after it.

And a detail worth naming: `:1818` already implements the exact pattern F2's fix
introduced — catch, record a `raw_persist_failed` event, continue. **The right
pattern already existed roughly 100 lines from the wrong ones.** F2's repair
re-derived a solution the file already contained.

## Consequence for how this is repaired

Three rounds of this family have now been fixed one named site at a time — the
review-1/2 rounds of the previous stage taught the same lesson, and it is why the
withdrawn `task2` brake rule exists. Human's instruction is therefore right and is
being followed: **one comprehensive read-only audit before any further repair**, so
the repair works from a closed, classified list instead of the four sites a reviewer
happened to name.

Packet: `70-exception-swallow-audit-codex.dispatch.md`. It is an audit, not a
repair, and does not consume a rework round. The scope of the repair — this stage or
its own — is a Human decision once the audit says how large the family is.
