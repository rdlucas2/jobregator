# Ground Rules

These are non-negotiable. Follow them on every prompt, without exception.

## 1. Check Skills Before Acting

Before taking any action on a user prompt:

1. Review all available skills in `.claude/skills/`
2. Determine if any skill is relevant to the request
3. If a relevant skill exists, load and apply it — ask any skill-prompted questions or gather required context **before** acting

Do not skip this step. Skills may require upfront clarification that changes the approach entirely.

## 2. Conventional Commits

Every git commit MUST follow the conventional commits format. Apply the `conventional-commits` skill for all commits. See `.claude/skills/conventional-commits/SKILL.md` for the full spec.
