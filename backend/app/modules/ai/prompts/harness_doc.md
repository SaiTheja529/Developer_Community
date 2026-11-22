---
version: 1
---
Task: write submission documentation for an AI coding harness hosted in a public GitHub repository.

A harness is the set of rules, instruction files, agents, subagents, skills, hooks, MCP servers,
slash commands and workflows that shape how an AI coding tool behaves in a project.

Use ONLY the repository content provided below (metadata, README, key harness files, file tree).
- For every component, set evidence_path to the repository path where you observed it, or null if inferred.
- Put everything you could not determine from the provided content into gaps_and_uncertainties
  (for example: test coverage, supported tool versions, setup prerequisites that are not documented).
- short_description must be at most 280 characters.
- suggested_tools must come from: {TOOLS}.
- suggested_category must be one of: {CATEGORIES}.
- suggested_tags: up to 8 lowercase tags using a-z, 0-9, '.', '+', '#', '-'.
- Write detailed_explanation, architecture, setup_instructions and limitations as Markdown.
