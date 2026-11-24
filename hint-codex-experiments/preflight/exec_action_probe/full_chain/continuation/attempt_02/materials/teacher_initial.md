## Stage: Initial Guidance

The fixed reference patch is available at /tmp/golden_diff.diff.

## Original Issue

The window report drops observations at the end of a requested window. A requested time window includes both its start and end timestamps; a window with equal endpoints must include observations at that timestamp. Empty windows should keep their existing zero/None result. Repair the implementation, preserve the public interface and data files, and verify the behavior with the existing tests. Summarize the change and the checks you ran.


## Workflow

1. Read the reference patch and understand the affected files and intended behavior.
2. Inspect the actual repository, related calls, types, interfaces, and data flow. Explain why the initial implementation fails.
3. Produce a detailed Markdown guide with these sections:
   - Problem Essence: explain the root cause in two or three sentences.
   - Key Files and Locations: cover every file affected by the reference patch and explain its role.
   - Solution Approach: explain the design and the relationships between the changes.
   - Implementation Directions: describe where to investigate, what logic needs attention, and why, without complete replacement code.
   - Pitfalls and Edge Cases: explain related changes that are easy to miss and relevant boundary conditions.
4. Write the complete guide to /tmp/hint_output.md and include it in your final response.

Begin by reading the reference patch, then inspect the repository.
