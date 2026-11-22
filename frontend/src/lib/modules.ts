import { Bot, BookOpen, Lightbulb, Wrench, type LucideIcon } from 'lucide-react';

export type ModuleKey = 'harness' | 'idea' | 'knowledge' | 'ai';
export type TargetType = 'harness' | 'idea' | 'resource' | 'collection';

export const MODULES: Record<ModuleKey, { name: string; short: string; tagline: string; path: string; icon: LucideIcon; color: string; explainer: string }> = {
  harness: {
    name: 'Harness Lab', short: 'Harnesses', tagline: 'Explore. Test. Improve. Share.', path: '/harnesses', icon: Wrench, color: 'var(--harness)',
    explainer: 'Rules, hooks, subagents and MCP servers that people use to keep AI coding agents on track. Test them, write reports, suggest fixes.',
  },
  idea: {
    name: 'Project Ideas', short: 'Ideas', tagline: 'Share. Discuss. Collaborate. Build.', path: '/ideas', icon: Lightbulb, color: 'var(--idea)',
    explainer: 'Problems worth solving and the people who want to build them. Add suggestions, show interest, or ask to join.',
  },
  knowledge: {
    name: 'Knowledge Hub', short: 'Knowledge', tagline: 'Discover. Learn. Curate. Share.', path: '/resources', icon: BookOpen, color: 'var(--knowledge)',
    explainer: 'Docs, tutorials and guides with link health you can see, plus collections curated into learning paths.',
  },
  ai: {
    name: 'AI Workspace', short: 'AI', tagline: 'Ask. Generate. Refine. Create.', path: '/ai', icon: Bot, color: 'var(--ai)',
    explainer: 'Chat with context from any page, or draft harness docs and ideas. Nothing is published until you review it.',
  },
};

export const TARGET: Record<TargetType, { plural: string; module: ModuleKey; path: (id: string, slug?: string) => string; label: string }> = {
  harness: { plural: 'harnesses', module: 'harness', label: 'Harness', path: (id, slug) => `/harnesses/${id}${slug ? `/${slug}` : ''}` },
  idea: { plural: 'ideas', module: 'idea', label: 'Idea', path: (id, slug) => `/ideas/${id}${slug ? `/${slug}` : ''}` },
  resource: { plural: 'resources', module: 'knowledge', label: 'Resource', path: (id) => `/resources/${id}` },
  collection: { plural: 'collections', module: 'knowledge', label: 'Collection', path: (id, slug) => `/collections/${id}${slug ? `/${slug}` : ''}` },
};

export const TOOL_LABELS: Record<string, string> = {
  claude_code: 'Claude Code', github_copilot: 'GitHub Copilot', cursor: 'Cursor', devin: 'Devin', openai_codex: 'OpenAI Codex',
  windsurf: 'Windsurf', cline: 'Cline', aider: 'Aider', gemini_cli: 'Gemini CLI', other: 'Other',
};

export const SORT_LABELS: Record<string, string> = {
  recent: 'Most recent', popular: 'Most votes', trending: 'Trending', most_reviewed: 'Most reviewed',
  most_discussed: 'Most discussed', most_interest: 'Most interest',
};

export const COMPONENT_LABELS: Record<string, string> = {
  rule: 'Rules', instruction_file: 'Instruction files', agent: 'Agents', subagent: 'Subagents', skill: 'Skills',
  hook: 'Hooks', mcp_server: 'MCP servers', slash_command: 'Slash commands', workflow: 'Workflows', other: 'Other',
};
