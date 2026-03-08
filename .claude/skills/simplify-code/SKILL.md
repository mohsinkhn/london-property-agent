---
name: simplify-code
description: Review and fix code quality issues including bloat, duplication, god functions, and unnecessary abstractions. Use this periodically to clean up the codebase, especially after adding new features.
---

# Simplify Code

Self-improvement skill. Review changed code for common agent-generated anti-patterns and fix them.

## Anti-Patterns to Detect and Fix

### 1. Copy-Pasted Logic
- **Detect**: Two+ functions with identical bodies differing only in a value/type.
- **Fix**: Extract a parameterized version. Use a flag, generic, or strategy object.

### 2. God Functions (>60 LOC or 3+ elif branches on type checks)
- **Detect**: Function handles multiple unrelated responsibilities via long if/elif chains.
- **Fix**: Split by responsibility. Each branch becomes its own function.

### 3. Incomplete Abstractions
- **Detect**: Caller always wraps a return value the same way.
- **Fix**: Move the wrapping into the callee.

### 4. Parallel Dispatch
- **Detect**: New feature handled in a separate code path outside the primary dispatcher.
- **Fix**: Extend the existing if/elif with the new condition.

### 5. Redundant Iteration
- **Detect**: Loop over list → filter → loop again over filtered subset.
- **Fix**: Use `continue`/early-return inside the primary loop.

### 6. Re-instantiation in Loops
- **Detect**: Class/client created fresh every iteration (e.g. httpx.AsyncClient inside a for loop).
- **Fix**: Instantiate once before the loop; pass instance in.

### 7. Dead Code & Backwards-Compat Shims
- **Detect**: Unused imports, variables prefixed with `_` that were renamed, `# removed` comments.
- **Fix**: Delete completely. No shims for internal code.

### 8. Unnecessary Error Handling
- **Detect**: try/except around code that can't fail, or catching Exception for expected paths.
- **Fix**: Only validate at system boundaries (user input, external APIs). Trust internal code.

### 9. Premature Abstraction
- **Detect**: Helper/utility created for a one-time operation. Base class with one subclass.
- **Fix**: Inline it. Three similar lines are better than one abstraction used once.

## Process

1. Read the files that were recently modified (use `git diff --name-only HEAD~1` or check recent changes).
2. For each file, apply the detection rules above.
3. Fix issues in-place using Edit.
4. Run tests after fixes to ensure nothing broke.
5. Report what was simplified and why.
