# propose: discover, clarify, write every document, get one approval

**Command:** `/tracespec propose <request>` (a bare `/tracespec <request>` means this). **Writes:** `.tracespec/changes/<change>/` and, the first time, `.tracespec.json`. **Stops for:** the answers, and the one approval.

Goal: turn the request into a change folder whose documents are complete and checked, so that two agents who never see each other's work produce tests and code that fit. You write all of it in one pass, then stop for the developer's review.

## 1. Start
1. **Find the project root** (git top folder, or the current folder) and `.tracespec.json`.
2. **Audit first** when living specs exist: `python <skill folder>/tools/check.py <project root> --audit --no-run`. On errors, tell the developer in plain words which capability drifted and which rules, criteria and tests it names (see [audit.md](audit.md)). Ask whether this request is about that drift; if it is, the proposal starts from it. Do not hide drift and carry on.
3. **The change name and the tier.** Propose a short kebab-case name (`add-discount`) and the tier (SKILL.md, "Tiers"). The developer confirms or changes either.

## 2. Discover (only the first change in a project, or when something new shows up)
1. **Read the project** (read only): README, `CLAUDE.md`, manifests, CI file, lint and format settings; the folder structure two levels deep; where the tests live and what they look like (framework, naming, helpers, fixtures); the code around the request and its callers. `git status --short` and the branch: uncommitted changes are not part of this change; offer a feature branch and create it only after a yes.
2. **Detect and confirm the layout.** Run `python <skill folder>/tools/check.py --detect <project root>` (the developer may already have run `check.py <project root> --init`, which wrote this guess to `.tracespec.json`; then confirm it instead of rewriting it). Show the guess in plain words and ask the developer to confirm or fix it, in one question set: which paths are **tests** and which are **code** (a path that is both counts as a test); the **test command** and the JUnit file it writes (a missing JUnit package is the developer's decision); the project's other checks (linter, type checker, build) for `checks`; whether test files sit next to code files (then searches are off for the build agents).
3. **Write `.tracespec.json`** as in SKILL.md ("State file"); never overwrite an existing one, add the change. Suggest `.tracespec-junit.xml` and `.tracespec-check.json` for `.gitignore`; do it only after a yes. `.tracespec/` (the lock and ledger make the audit work in CI) and `docs/features/` are meant to be committed; the commit is the developer's.
4. **Baseline:** `python <skill folder>/tools/check.py <project root> --baseline`. It records every existing test and the files already uncommitted. Failing tests go into `layout.knownFailing` only after the developer agrees. `CANNOT RUN` is the developer's environment problem: stop and say what is missing.
5. Show a short summary (stack, layout, test command, baseline counts, tier) and go on to clarify. Nothing is approved here.

## 3. Clarify
Turn the request into questions with answers, so nothing in the documents is a guess. Questions cost the developer attention: ask only what the code and the request do not answer.

1. **Find the capabilities** the request touches. Read their living specs (`.tracespec/specs/<capability>/spec.md`) and run `--trace <file>` on the files you expect to change. A request may add a new capability, change an existing one, or both. A new capability needs a kebab-case name and a one-sentence purpose.
2. **Make a private list of gaps:** who or what triggers it and the inputs (formats, limits, validation); the result and its side effects; edge cases and errors; what must **not** change in existing behaviour and who calls the code; data (schema, migration); rights and security; limits of speed or size; the interface (names, API shape, wording); configuration, flags, release; what is out of scope.
3. **Sort every gap** before it becomes a question:

   | Kind | When | What you do |
   |---|---|---|
   | **Answered by the repo or the living specs** | The code, the tests, the docs or a living spec show it | Do not ask. Record it as a Q row, Kind "repo", with the path |
   | **Question for the developer** | It changes what the change does, or touches data loss, money, security or compatibility; or only they know it | Ask it |
   | **Usual choice** | The project's conventions give a clear default and nothing is at risk | Write it as an assumption (ASM-n, status `open`) with the repo fact. The developer confirms it at the approval |
   | **Design detail** | How to build it, not what it does | Do not ask. It becomes a decision (D-n) in design.md |

   When you are unsure whether a gap is the developer's, it is the developer's.
4. **Ask 2–3 questions per turn**, each with a concrete example from their own code or request. Use AskUserQuestion when there are likely answers (2–4 options, your proposal first, "(Recommended)" when you have a reason). What only the developer can say in their own words (what it is for, what must never happen, deadlines) is plain text, no options.
5. **Always ask these two** in plain text. "What must never happen?" Record the words, then do the **never-happen walk**: every way it could still happen under the answers so far; each way no answer closes becomes a question for the developer, not a default. And: "Give me one or two real examples: this input, this result." These become criteria.
6. **Record each answer at once**, word for word, in a Q row of `proposal.md` (create the file from [../templates/proposal.md](../templates/proposal.md), or the small-tier file). A correction is a new row under "Corrections"; the old answer stays. Follow-up questions only when an answer contradicts an earlier one or opens a new risk.
7. **Stop asking** when you could write a criterion for every rule you expect.

## 4. Write the change folder, in one pass
Create the documents from the templates (small tier: only [../templates/small_proposal.md](../templates/small_proposal.md)):
- `proposal.md`: request, goal, capabilities touched, questions, never-happen walk, assumptions.
- `specs/<capability>/spec.md` per capability: the delta ([../templates/delta_spec.md](../templates/delta_spec.md)). **IDs come from `check.py --next-id FR|NFR|AC|NG`**; they are project-wide and never reused. ADDED rows are new. A MODIFIED row repeats the living row with its **full new text** and the same ID. A REMOVED row gives reason and migration; delete or modify the criteria that covered the rule in the same change. Every rule needs a criterion once merged; every criterion names the rule it covers; every FR, NFR and D names its source. Write criteria a test can decide, with real values. A rule that matters for "what must never happen" gets criteria that try to break it.
- `design.md` ([../templates/design.md](../templates/design.md)): existing code facts (enough for someone who cannot read the code to write fitting tests), design decisions D-n (inside the project's structure and style), interfaces the tests call (exact names and signatures, plus the test naming rule), affected areas (every path to change or add, kept small), risks.
- `tasks.md` ([../templates/tasks.md](../templates/tasks.md)): checkbox lines, T-1 the skeleton, every ADDED or MODIFIED criterion and every D named by a task, `needs T-n` where one task calls what another builds.

Each document is in the language the developer writes in, in short sentences, one word for one thing.

## 5. Check, show, approve
1. **Run `python <skill folder>/tools/check.py <project root> --gate 2`** and fix every error in the source document. Nothing goes to the developer with errors in it. Then read the documents once as the test writer would, who has only these files and the living specs: could you write a test for every criterion without asking anything? Could you build every interface without guessing?
2. **Show one short summary**, in plain words: the goal; per capability what is added, changed and removed (`check.py --show <change> --diff` prints it); each rule with its criterion in one line; every assumption and usual choice they are accepting (their confirmation of the questions); the affected files; anything that changes existing behaviour. Do not paste the documents and do not ask the developer to open them: the files under `.tracespec/` are for the agents, and this summary is the review.
3. **Ask one question**: "Approve the proposal v{x}?" with "Yes, approve" / "No, I want changes". Their remarks are recorded word for word in `review_log.md` (a Review notes row) and applied; then ask again.
4. **On yes**, record it with the tool: `python <skill folder>/tools/check.py <project root> --approve change --by "<name>" --words "<their exact words>"`. It re-runs the checks, writes version, fingerprint, the delta-row hashes, the hashes of the living rows it modifies or removes, state, the Status line and the review-log row. If it refuses, fix what it says; never write the record by hand.
5. **Go on to apply** in the same turn when no developer decision is open.
