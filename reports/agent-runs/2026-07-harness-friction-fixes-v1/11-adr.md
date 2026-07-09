# ADR: Follow Up With Targeted Harness Friction Fixes

## Status

Accepted for stage design; pending development breakdown.

## Context

The manifest sync stage passed review and was accepted, but it required
manual compensation for Harness shortcomings. The observed friction points are
now concrete enough to address in a bounded Harness-only stage.

## Decision

Open a MEDIUM Harness-only stage to fix the highest-value friction points:

- false review-2 designer-overlap before final reviewer selection;
- single-owner checkpoint/status metadata gap;
- clean-worktree-safe validator evidence capture;
- dispatch ordering for validator evidence before fingerprint anchoring;
- documentation for delivery-anchored `head_sha` and validator fixed-point
  evidence semantics.

## Consequences

- This stage may modify shared Harness scripts and templates, so it requires
  development breakdown before implementation.
- Product code remains out of scope.
- Reviewers should focus on whether the changes preserve hard gates while
  reducing manual compensation.

## Alternatives Considered

- Leave as documentation only: rejected because #1/#2/#6 cause recurring gate
  failures or manual transcription risk.
- Patch only the template default: rejected as insufficient; it would not
  address single-owner status writes or validator evidence capture.
- Rewrite the Harness runner: rejected as too broad for the current stage.

本地北京时间: 2026-07-09 13:42:58 CST
下一步模型: claude
下一步任务: write development breakdown
