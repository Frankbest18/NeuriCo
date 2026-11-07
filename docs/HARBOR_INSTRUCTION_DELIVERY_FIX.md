# Harbor focused ordinary instruction delivery fix

Branch: `harbor-focused-managed-ordinary`, follow-up to `baf100d`.

## Problem

Harbor's idea conversion keeps the complete instruction in
`idea.background.description` and a shortened version in `idea.hypothesis`.
The resource-finder renderer ignores `background.description`. In the first
smoke its task stopped at “Fix all the pr...”, omitting essential scope and
restrictions. The experiment runner already receives the full description.

## Implementation

1. In `PromptGenerator.generate_resource_finder_prompt`, render the nonempty
   `background.description` for focused managed ordinary research using the
   existing research prompt's “User-Provided Instructions and Context” block,
   delimiters, and priority note. Preserve the complete text and existing context.
2. Keep this correction behind `focused_managed_ordinary`, so existing
   AutoResearch and unfocused ordinary rendering remains unchanged. Do not
   change the idea converter, hypothesis length, workflow, or reasoning guidance.
3. Add a Harbor-to-rendered-prompt regression using a long multiline instruction
   with a required output and a prohibition beyond the hypothesis cutoff. Check
   resource-finder plan/execution/review and experiment-runner equivalents;
   decode serialized idea context where applicable. Cover missing descriptions
   and verify that legacy prompt branches do not change with this field.
4. Run focused tests and the Harbor contracts, then the NeuriCo test suite.
   Commit the fix on the existing branch.

## Manager boundary

Manager phase reviews receive the submitted plan, summary, and artifacts, with
read access to workspace files. They do not automatically receive the original
idea as a dedicated task input. The corrected resource prompt is saved through
the existing logging path and is available for manager inspection. Do not claim
that this guarantees the manager reads it. Direct task injection into manager
reviews would be a separate change; this fix restores the missing worker input.

## Acceptance and subsequent smoke

The long instruction survives intact in the resource prompts and remains
available to experiment prompts. Planning restrictions still apply; no new
execution permission or interpretation advice is introduced. Existing branches
remain unchanged. After pushing the reviewed follow-up commit, a fresh neutral
smoke can verify live delivery and final evidence preservation. Retain the first
run; a passing benchmark score is not required to demonstrate instruction
delivery, and a new score does not by itself establish causation.

## Local validation (2026-11-07)

- The new Harbor conversion-to-prompt regression failed on the original code
  for plan, execution, and review, and passes with the correction.
- NeuriCo suite: 519 passed.
- Harbor contracts: 31 passed; 7 Linux-only checks skipped on macOS.
- Compatibility tests compare legacy rendering with and without the description
  and cover absent/empty descriptions plus preservation of existing context.
- No new model-backed benchmark run has been performed for this follow-up.
