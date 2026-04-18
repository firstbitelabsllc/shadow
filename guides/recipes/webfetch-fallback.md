# Recipe: WebFetch Fallback

> Recognize WebFetch failure modes early and escalate — don't retry the same hammer.

## When to use

- WebFetch returns empty content, a login wall, or an SPA shell
- Target is auth-gated (Life Time pool schedule, vendor portals)
- Target is JavaScript-rendered (Grafana stack API, most modern dashboards)
- You've already tried WebFetch once and it didn't give you the real page

## The recipe

**1. Recognize the failure signature on the first fetch.** Don't retry.

| Signal | What it means |
|---|---|
| `<title>Log in</title>` or redirect to `/login` | Auth-gated |
| Short HTML with `<div id="root"></div>` and nothing else | SPA shell, client-rendered |
| `Content-Type: text/html` but body is ~2KB of meta tags | Prerendered shell |
| 403 / 401 / "Access denied" | Auth-gated or bot-blocked |
| Content has `<noscript>` banner saying "enable JavaScript" | Client-rendered |

**2. Do NOT retry WebFetch with different URLs on the same domain.** Same failure mode. Stop.

**3. Fallback order:**

1. **Check for a public API, iCal, RSS, or sitemap endpoint** on the same domain (`/api`, `.ics`, `/feed`, `/sitemap.xml`, `/rss`). These are often static and cacheable.
2. **Ask the user to paste the rendered content.** This is cheap, accurate, and doesn't burn tool budget.
3. **Propose a specific alternative** — browserbase (if available), mobile API endpoint, OCR of a screenshot, curl with a specific cookie — and wait for confirmation before executing.
4. **Declare the blocker explicitly.** Say "WebFetch cannot reach this page; I need X to proceed" rather than fabricating or inferring content.

**4. Never fabricate data from a failed fetch.** If the page didn't load, you don't know what it says.

## Failure modes

Without this recipe:

- Agent retries WebFetch 5 times with URL variants, burning budget and time
- Agent infers or invents page content ("the schedule probably shows...")
- Agent continues downstream work on fabricated data
- User gets a confident-sounding answer based on nothing

## Example — copy-pasteable prompt when WebFetch fails

```
WebFetch returned [describe: empty / login wall / SPA shell] for <URL>.

I will NOT retry WebFetch on this domain — same failure mode.

Fallback options, in order of preference:
1. Is there a public API, iCal, RSS, or JSON endpoint on this domain I should try instead?
2. Can you paste the rendered page content here?
3. Should I launch browserbase / playwright / OCR a screenshot? (requires your confirmation)

Without one of the above, this task is blocked. I will not fabricate the content.
```

## See Also

- `guides/recipes/evidence-discipline.md` — don't invent data you don't have
- `browserbase` skill — the escalation path when dynamic rendering is required
