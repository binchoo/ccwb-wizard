# Quota Enforcement Model & Token-Lifetime Tuning

This guide defines **what kind of quota enforcement this stack can and cannot provide**, and
how to tune it. It is the decision-making companion to
[QUOTA_MONITORING.md](./QUOTA_MONITORING.md), which covers policy setup, alerts, and the
`ccwb quota` CLI.

**Audience**: operators and architects deciding how strictly to enforce token quotas.

---

## TL;DR

- This stack is **not an LLM gateway / inline proxy**. It hooks the AWS credential path
  (`credential-process`), not individual Bedrock requests.
- Therefore it supports **best-effort, issuance-time quota gating** — not hard, real-time,
  per-request enforcement. An already-issued session token cannot be revoked mid-flight.
- **Token lifetime (`max_session_duration`) is the primary lever** for how tightly quotas
  bite. Shorter tokens → tighter enforcement, at a re-authentication cost.
- If you need a true hard cap (per-request blocking, token-level caps), you need an inline
  proxy in front of Bedrock. That is out of scope for this stack.

---

## Scope & limitations (read first)

The credential helper participates only when AWS credentials are issued or refreshed. It
never sees individual model-invocation requests.

| Capability | Supported? |
|---|---|
| Quota gating at credential issuance / refresh | Yes (best-effort) |
| Opportunistic re-check of cached sessions | Yes (interval-based) |
| Per-request blocking / token-level hard cap | **No** (needs an inline proxy) |
| Revoking an already-issued, still-valid session | **No** |

While a previously issued STS token is still valid, **no quota overage can interrupt that
session.** This is an architectural property, not a defect.

---

## How enforcement actually works

Quota is consulted at only two moments:

1. **Issuance gate** — immediately before new credentials are issued. If the quota check
   returns `allowed=false`, no credentials are emitted.
2. **Opportunistic re-check** — when `credential-process` is re-invoked *and* more than
   `quota_check_interval` (default 30 min) has elapsed since the last check.

The subtle part: `credential-process` is re-invoked by the **AWS SDK only when its
credential cache expires** — that is, when the token `Expiration` (= `max_session_duration`)
passes. It is **not** invoked per Bedrock request. In a long-running Claude Code process,
the token lifetime therefore effectively governs how often re-checks can happen.

```
Claude Code → AWS SDK
  ├─ SDK credential cache valid (until Expiration)  → reuse, credential-process NOT called
  └─ SDK credential cache expired → run credential-process
        ├─ internal STS cache still valid → reuse + opportunistic quota re-check
        └─ internal STS cache expired
              ├─ id_token still valid → silent STS re-exchange (no browser)
              └─ id_token expired      → browser OIDC login
```

---

## The core formula

> **Worst-case block latency (overage → access actually denied) ≈ remaining lifetime of the
> currently issued token ≤ `max_session_duration`.**

This single relationship drives every tuning decision. The only way to make enforcement
tighter is to shorten the token lifetime so the next issuance gate arrives sooner.
`quota_check_interval` refines *within* that window but cannot beat it.

---

## Tuning levers

| Config key | Role | Default |
|---|---|---|
| `max_session_duration` (seconds) | **Primary lever.** STS token lifetime = block-latency ceiling | direct `43200` (12h) / Cognito `28800` (8h) |
| `quota_check_interval` (minutes) | Minimum gap between re-checks. `0` = check on every re-invocation | `30` |
| `quota_fail_mode` | Behavior when the quota API errors/times out: `open` (allow) or `closed` (deny) | `open` |
| `quota_check_timeout` (seconds) | Quota API call timeout | `5` |

**Rule of thumb:** keep `quota_check_interval ≤ max_session_duration`. If the interval is
larger than the token lifetime, you forfeit re-check opportunities.

Constraints:
- STS minimum session is **900 s (15 min)** — you cannot go below this.
- For direct STS (`AssumeRoleWithWebIdentity`), `max_session_duration` cannot exceed the
  IAM role's `MaxSessionDuration`.

---

## Recommended profiles

| Enforcement strength | `max_session_duration` | `quota_check_interval` | `quota_fail_mode` | When to use |
|---|---|---|---|---|
| Loose (default) | 8–12h | 30m | open | Trust-based teams, UX first. Effectively issuance-time only. |
| Standard (recommended) | 1h | 30m or 0 | open | ~Hourly re-check. Best balance. |
| Strict | 30m (min 15m) | 0 | closed | Cap block latency at ~30 min. Accepts re-auth cost. |
| Hard real-time | — | — | — | **Not achievable here. Use an inline LLM gateway.** |

---

## Trade-offs of shortening token lifetime

Shorter `max_session_duration` buys tighter enforcement but costs:

- **More frequent STS re-issuance** → higher STS / IdP API load.
- **Browser re-login risk** — but this is governed by **id_token lifetime (IdP-controlled),
  not the STS session.** While the cached id_token is still valid, the helper performs a
  *silent* STS re-exchange with no browser prompt; the browser only opens once the id_token
  itself expires.
  - **Practical guidance:** shorten the STS session for tighter quotas, but keep the IdP
    id_token lifetime generous so users are not prompted to log in every cycle.
- **Do not** push the STS session toward the 15-min floor for normal use — re-authentication
  becomes too frequent to be workable.

Using a short STS session purely to emulate real-time enforcement is an anti-pattern: STS
session length is meant to bound credential exposure, not to act as a quota polling clock.

---

## Decision guidance

- **Need a true hard cap?** Put an **inline proxy (LLM gateway)** in front of Bedrock that
  checks every request. This stack's quota is positioned as *cost visibility + best-effort
  gating*, not hard enforcement.
- **Best-effort is enough (most cases)?** Start at the **Standard profile (1h session)**.
  Tighten toward 30m only if needed, and pair it with a generous IdP token lifetime and
  `quota_fail_mode=closed`.
- **Want only to tighten re-checks?** Lower `quota_check_interval`, but remember it only
  takes effect when `credential-process` is re-invoked — the SDK cache (token lifetime)
  limit still applies.

---

## Configuration example

In the credential provider `config.json` profile:

```json
{
  "profiles": {
    "ClaudeCode": {
      "quota_api_endpoint": "https://xxx.execute-api.us-east-1.amazonaws.com",
      "max_session_duration": 3600,
      "quota_check_interval": 30,
      "quota_fail_mode": "closed",
      "quota_check_timeout": 5
    }
  }
}
```

Without `quota_api_endpoint`, the helper skips quota checks entirely.

---

## See also

- [QUOTA_MONITORING.md](./QUOTA_MONITORING.md) — policy setup, `ccwb quota` CLI, alerts,
  fine-grained policies, and the underlying tables/Lambdas.
- [ANTHROPIC_CUSTOM_HEADERS_GUIDE.md](../../ANTHROPIC_CUSTOM_HEADERS_GUIDE.md) — the
  attribution magic header (how `user`/`team`/`dept` scopes are derived).
- [ARCHITECTURE.md](./ARCHITECTURE.md) — overall system architecture.
