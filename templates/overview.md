# <<Feature title>>

> Developer overview. Read this to understand the feature without opening the agent files in `.tracespec/`.
> The narrative is written by tracespec from the code that was built. The block at the end is generated and refreshed by `check.py`.

## Purpose

<<Two or three sentences: who needs this, what problem it solves, what changes for them. Plain words, no requirement IDs.>>

## How it fits into the codebase

<<Where the feature sits in the existing system: which existing modules call it or are called by it, what it reuses, what it deliberately leaves alone, and anything an existing caller will notice.>>

## Architecture

<<The shape in a few lines: the main pieces and how they relate. A small diagram helps when the flow has more than two steps (a mermaid block is fine).>>

## Key components

| Component | Path | Responsibility |
|---|---|---|
| <<name>> | `<<path/to/file>>` | <<what it does and owns, in one line>> |

## Data flow

<<Numbered steps from the trigger to the result: what comes in, what each component does with it, what goes out or is stored. Say what happens on the main failure paths.>>

## Facts (generated)

<!-- tracespec:facts:begin -->
<!-- tracespec:facts:end -->
