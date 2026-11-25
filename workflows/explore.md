# explore: think it through, write nothing

**Command:** `/tracespec explore <topic>`. **Writes:** nothing, unless the developer asks you to capture a decision. **Stops for:** the conversation.

Use it when the developer is not sure yet what to build, or how. You are a thinking partner who has read the code.

## Do
1. Find the project root and, if there is one, read `.tracespec.json` and the living specs under `.tracespec/specs/` for the capabilities the topic touches.
2. **Read the code** the topic points at: the names and words in it, the files that would change, their callers, the tests near them. Say what you found with paths.
3. **Use the impact tool** when a file or a requirement is named: `python <skill folder>/tools/check.py <project root> --trace <file, file::symbol, ID or ticket>` shows the rules, criteria, tests and code symbols linked to it (see [trace.md](trace.md)).
4. **Think with them:** options and their costs, what the living specs already promise, what would break, what is unclear. Ask questions, but few and good. Recommend; do not survey.
5. **Write nothing** (no change folder, no spec, no code, no test). If the developer asks, capture decisions in a notes file they name, outside `.tracespec/specs/` and `.tracespec/changes/`.
6. When the direction is clear, say so in one line and offer: "Want me to propose this?" Propose starts from what was discussed; do not make them repeat it.
