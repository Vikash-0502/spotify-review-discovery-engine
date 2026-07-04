# Why Conversation Context Token Usage Is High (Cursor / AI Assistants)

This note explains why long Cursor chat sessions consume a large number of **context tokens** — separate from Groq/API tokens used by the Review Discovery Engine itself.

## What “context tokens” means

Each time the assistant replies, the model receives a **single prompt** built from everything the IDE attaches to that turn:

- Your latest message
- Prior messages in the thread (or a summary of them)
- Open/recently viewed files and cursor position
- Tool results (file reads, search output, terminal logs, test output)
- Project rules, skills, and system instructions

Tokens are charged on **input size per request**, not only on the final answer length. A short reply can still be expensive if the input context is large.

## Why this project’s sessions get expensive quickly

### 1. Long conversation history

This build spanned many phases (API, RAG, dashboard, integration). Each turn re-sends:

- Earlier user requests and assistant plans
- Summaries of prior work when the window is compressed
- Decisions already made (Phase 7 vs 8 numbering, bug fixes, etc.)

**Effect:** History compounds — turn 50 carries much more text than turn 5.

### 2. Large file reads

`dashboard/app.py` is ~2,000 lines. A single `Read` of that file can add **tens of thousands of characters** to context. Multiple reads, partial reads, and re-reads after edits multiply cost.

Other sizable surfaces: `analysis/rag.py`, `docs.md/implementationplan.md`, test output, agent transcripts.

### 3. Tool output is included verbatim

Grep results, `pytest` runs, terminal sessions, and codebase search snippets are injected into the next model call. A full test suite log or wide ripgrep match list can be larger than the code change itself.

### 4. Conversation summarization is not “free”

When context limits approach capacity, Cursor **summarizes** older turns. The summary still occupies tokens, and recent detailed turns remain attached. You still pay for summary + recent history + new tools.

### 5. Parallel exploration in agent mode

Agent workflows often:

- Read many files before editing one
- Run commands and attach output
- Search broadly, then narrow

Each step adds to the **next** request’s input bundle.

### 6. Static instructions every turn

User rules, commit/PR workflows, coding principles, and skill files are re-applied on each invocation. Helpful for quality, but they add a fixed overhead per message.

## Rough mental model

```
Tokens per reply ≈
  system + rules
+ conversation history (or summary)
+ attached files / tool outputs
+ your new message
+ model’s generated answer (output tokens)
```

For this repo, **history + large file reads + test logs** usually dominate — not the size of the final code diff.

## How to reduce context usage in future sessions

| Technique | Why it helps |
|---|---|
| **Start a new chat per phase/task** | Drops accumulated history |
| **@-mention specific files/symbols** | Avoids whole-repo reads |
| **Ask for focused changes** | Fewer exploratory tool calls |
| **Close unrelated open files** | Less auto-attached editor context |
| **Run validation locally, paste only failures** | Smaller terminal payloads |
| **Split “plan” and “implement” chats** | Planning reads many files once; implementation chat stays lean |

## Project LLM usage vs Cursor context

| Layer | What uses tokens | Typical driver |
|---|---|---|
| **Cursor chat** | IDE context window | History, file reads, tool output |
| **Groq (RAG / pulse)** | API calls in `analysis/rag.py`, `delivery/pulse.py` | Retrieved review excerpts + prompts (capped by retrieval limits and `groq_tokens_per_minute`) |

High Cursor usage during development **does not** mean the production dashboard chat is sending 2,000-line files to Groq. The app retrieves a **small set of review snippets** per question.

## Related project controls

- RAG retrieval limit (default 6 reviews) in `analysis/rag.py`
- Pulse sample cap (`pulse_review_cap = 1000`) in `utils/config.py`
- Groq token budget checks before API calls in `analysis/rag.py`

---

**Bottom line:** Context usage is high because each assistant turn resends the growing conversation plus large artifacts from this codebase — not because a single small question inherently requires that much text. New chats, narrower scope, and citing only failing test lines keep costs down.
