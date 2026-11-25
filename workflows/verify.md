# verify: converge, independent review, readiness report

**Command:** `/tracespec verify [change]`. **Writes:** the review log (review findings) and the developer overview `docs/features/<change>.md`. **Stops for:** nothing, unless a finding needs a decision.

Goal: show that the change does what its deltas say, and nothing else, and that the rest of the project still works. It is a report; it archives nothing. The normal path runs it at the end of apply and then archives.

## Do
1. **Full run.** `python <skill folder>/tools/check.py <project root> --gate 4`, and the project's other checks from `checks`. Report failures plainly; never go on with a failing check.
2. **Converge: code against the documents, by reading** (you, not the build agents). Every ADDED or MODIFIED rule and every D is reflected in the code; every criterion has a test that passes (the matrix lists them); **nothing else changed**: compare the changed files (`git status`, `git diff --stat`, or the files recorded on the tasks) with "Affected areas"; no new dependency, flag or public name the documents do not name; the code follows the project's style and its neighbours' patterns. Each gap becomes a new task, done the same way (test, then code), and you converge again.
3. **Independent review.** Start a third, separate reviewer: a new agent with a fresh context (a general-purpose subagent), or a person. Give it **only** the change's documents, the living specs of the capabilities touched, the code changes, the tests and the project's own conventions. Never your own summary or reasons. Ask it to find:
   - where the code does not do what the deltas say, or does more;
   - where a test would pass even if the code were wrong (too weak, a mock that proves nothing, an assertion on the wrong thing);
   - cases the specs do not cover that real use would hit (empty, large, concurrent, repeated, time-dependent, bad input that reaches a query, a command or a log line);
   - harm to existing callers of the changed code, and to the other capabilities that use the same files (`check.py --trace <file>`).
   Record each finding as IR-n in the review log with one outcome: **fixed** (a new task, test then code, with a test that fails first), **not a problem** (why), or **spec gap** (the specs do not say; the developer decides: a change now, or a follow-up). A spec gap that needs the developer's decision counts as open.
4. **Write the developer overview**, the one document in this process that is for people. Run `python <skill folder>/tools/check.py <project root> --overview`: it creates the skeleton `docs/features/<change>.md` from [../templates/overview.md](../templates/overview.md) the first time and never rewrites it. Then write three sections **from the code that was actually built** (read the files recorded on the tasks, not just the specs), in plain words, **short: about 30 lines in all, design first**:
   - **Purpose:** who needs it, what problem it solves, what changes for them. Two or three sentences, no requirement IDs.
   - **Design:** the important part, about 20 lines. How it fits into the existing code (what calls it, what it reuses, what it leaves alone), the shape of the solution, how data flows through it (a small mermaid diagram when there are more than two steps), and the key decision with the alternative that was rejected and why.
   - **Key components:** a table of component, path (a real file or folder, in backticks) and one-line responsibility. The tool checks that every path exists.
   Do not copy the specs into it, do not list criteria, tests or files to look at, and do not restate the task list: `--trace` answers those. Run `--gate 5` to check it (OVERVIEW001-007).
5. **Report**, in a short block: the change; the matrix summary from `check.py --matrix` (requirements and criteria, all PASS or not); the number of tests; the checks; the review findings by outcome and how many are open; the files changed; a link to the overview `docs/features/<change>.md`; and the verdict: **ready to archive** only when every criterion passes, nothing fails, the scope is clean, every task is ticked, the overview is complete and no finding is open.
