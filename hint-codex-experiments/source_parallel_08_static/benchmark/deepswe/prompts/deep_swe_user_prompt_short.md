Please solve this issue: {{issue_description}}


You can execute bash commands and edit files to implement the necessary changes.

## Recommended Workflow

This workflow should be done step-by-step so that you can iterate on your changes and any possible problems.

1. Analyze the codebase by finding and reading relevant files
2. Create a script to reproduce the issue
3. Edit the source code to resolve the issue
4. Verify your fix works by running your script again
5. Test edge cases to ensure your fix is robust
6. Submit your changes when you are done

## Constraints

- The repository is at `/app`. All file operations should be relative to this directory.
- Only modify source code files. **Do NOT modify any existing test files** — they will be restored to their original state during evaluation, so any changes to them are wasted effort.
- Before referencing any function, type, constant, struct field, or method in your code, search the codebase to confirm it exists. Undefined references are the most common cause of build failures.
- If tests fail, the problem is in your implementation — fix your code, not the tests.
