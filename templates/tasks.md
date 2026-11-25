# Tasks: <<change title>>

> One checkbox line per task, small enough to test and finish in one go, in dependency order. Name what it serves
> (FR, NFR, AC, D) and what it needs (T-n) in the brackets. Every ADDED or MODIFIED criterion and every D is named by a
> task. `check.py --task-done T-n` ticks the box (only when the criteria it serves pass) and records its files.
> A new session resumes at the first unchecked task. Run `--task-start T-n` before a task: `--task-done` then adds `files:` and `symbols:` to the line
> (the code symbols the task touched), which become the code links in the trace store.

## 1. Skeleton

- [ ] T-1 The interfaces of design.md as stubs that do nothing useful, coder only (serves D-1)

## 2. Behaviour

- [ ] T-2 <<first behaviour>> (serves FR-<<n>>, AC-<<n>>, needs T-1)

## First-run record

For the quality numbers: did each criterion's test pass the first time it ran against real code?

| AC | Failed first (right reason) | Passed on the first real run |
|---|---|---|
