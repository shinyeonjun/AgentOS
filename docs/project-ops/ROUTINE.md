# AgentOS Jarvis Routine

## When The User Mentions AgentOS

1. Read `projects/agentos/GOAL.md`.
2. Read `projects/agentos/STATUS.md`.
3. Read `projects/agentos/NEXT.md`.
4. Check whether the user is asking for:
   - evaluation
   - research
   - design
   - implementation
   - presentation/report help
5. Work on the smallest useful slice.
6. Update project state files after meaningful decisions or progress.

## Research Mode

Use when the user asks for related work, papers, or market/technical validation.

- Prefer primary papers, official repos, benchmarks, and standards.
- Use `research/agentos-related-research/` for research artifacts.
- Use PaperQA2 only when local PDFs/text documents have been collected and the user approves possible LLM/embedding calls.

## Build Mode

Use when the user explicitly asks to build or prototype.

- Start with a copied or dedicated workspace.
- Keep demo-grade sandboxing honest.
- Run `scripts/jarvis-quality-check.sh` after local tool changes.
- Do not sync to real host project paths without explicit approval.

## Reporting Style

Keep updates short:

- what changed
- what passed
- what is blocked
- next concrete action
