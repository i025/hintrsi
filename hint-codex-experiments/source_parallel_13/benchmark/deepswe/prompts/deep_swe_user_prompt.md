Consider the following issue description:

{{issue_description}}


Can you help me implement the necessary changes to this repository so that the issue can be resolved?

---------
# INSTRUCTIONS

This is an unattended implementation task. Continue through implementation and
verification before returning your final answer; a plan, reproduction, or progress
report alone does not complete the task. Make reasonable repository-local decisions
without waiting for clarification. The runner has initialized `main` at the provided
base commit, and the available workspace tools can modify `/app`. If an operation is
actually denied, report that tool result; do not infer a workspace restriction from
the model backend's local execution environment.

## Step 1: Explore and Understand

- Explore the repository structure to understand the codebase layout, language, build system, and conventions.
- Locate the relevant source files by searching for functions, types, and modules related to the issue.
- Read the surrounding code carefully. Understand the existing patterns, interfaces, and how components interact.

## Step 2: Reproduce the Problem

- Create a script that demonstrates the current (incorrect) behavior and execute it.
- Confirm you can observe the issue before attempting a fix.
- This reproduction script should also serve as a validation that your fix works later.

## Step 3: Plan and Implement

- Analyze the root cause and reason about multiple potential solutions before choosing one.
- Implement your fix with minimal, focused changes. Follow the existing code style and idioms.
- **Before referencing any function, type, constant, struct field, or method in your code, search the codebase to confirm it exists.** Do not assume or invent symbol names — undefined references are the most common cause of build failures.
- Only modify source code files. **Do NOT modify any existing test files** — they will be restored to their original state during evaluation, so any changes to them are wasted effort.

## Step 4: Build Verification

- Before running tests, verify your changes compile/build cleanly:
  - Go: `go build ./...` or `go vet ./...`
  - Python: `python -c "import <module>"`
  - TypeScript/JavaScript: run the project's type-check or build command
- If there are build errors, fix them before proceeding. Do NOT skip this step.

## Step 5: Test

- Run the relevant unit tests to verify:
  - Your change resolves the issue (previously failing behavior is now correct)
  - No regressions are introduced (existing tests still pass)
- If tests fail, the problem is in your implementation — fix your code, not the tests.
- Think about edge cases and ensure your solution handles them.

## Step 6: Clean Up

- Run `git status` and `git diff` to review your final changes.
- Remove any temporary files, debug scripts, or reproduction scripts you created.
- `git restore` any accidentally modified test files or unrelated files.
- Your final diff should contain ONLY the intentional changes to resolve the issue.

--------

Your thinking should be thorough and so it's fine if it's very long.

You should use tools as much as possible, ideally more than 100 times. You should also implement your own tests first before attempting the problem.

I will export your changes and apply suitable test patches to verify if your fix is correct when you finish this task. This means you MUST NOT modify the testing logic or any of the tests in any way!

**Workspace Path**: The repository is located at `/app`. All file operations should be performed relative to this directory.
