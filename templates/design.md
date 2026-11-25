# Design: <<change title>>

> For the test writer, who cannot read the code, and for the coder. Everything a test needs is here.
> Stay inside the project's existing structure and style.

## Existing code facts

Facts about the current code that the test writer needs, written from what was read in discovery. Facts only: names,
signatures, fixtures, conventions. No new design here.

- Test framework and command: <<e.g. pytest; tests in tests/, named test_*.py>>
- How tests build the objects they need: <<helpers, factories, fixtures with names and paths>>
- Existing interfaces the change touches (name, signature, behaviour today): <<...>>
- Conventions the tests follow (naming, layout, assertion style): <<...>>

## Design decisions

| ID | Decision | Why | Source |
|---|---|---|---|
| D-1 | <<decision>> | <<reason, with the repo fact it follows>> | Q-1 |

## Interfaces the tests call

The only way tests may reach the change. For each: exact name, location, signature, inputs, outputs, errors. The test
writer calls nothing else. The coder builds exactly these.

Test naming rule: every test name contains the number of the criterion it checks, for example
`test_AC31_rejects_empty_cart` or `it("AC31 rejects an empty cart")`. A test may name several.

| Name and location | Signature | Behaviour on error |
|---|---|---|
| <<module.function>> | <<(arg: type) -> type>> | <<raises X / returns Y>> |

## Affected areas

Files and folders the change changes or adds. The check fails for a changed file outside this list.

| Path | New or changed | What |
|---|---|---|
| <<path>> | new / changed | <<what>> |

## Risks

| ID | Risk | What limits it |
|---|---|---|
| R-1 | <<what could go wrong, for example breaking an existing caller>> | <<AC or D that covers it>> |
