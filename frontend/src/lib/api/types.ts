export type UUID = string;

export interface PageMeta { page: number; page_size: number; total: number; total_pages: number }
export interface Paginated<T> { data: T[]; meta: PageMeta }

export interface UserSummary { id: UUID; username: string; display_name: string; avatar_url: string | null; is_deleted: boolean }
export interface Category { slug: string; name: string; description?: string | null }
export interface Viewer { is_owner: boolean; has_voted: boolean; has_interest?: boolean; has_bookmarked: boolean; can_edit: boolean; can_moderate: boolean }
export type ContentStatus = 'published' | 'hidden' | 'removed';

export interface HarnessSummary {
  id: UUID; slug: string; name: string; short_description: string;
  tools: string[]; category: Category; tags: string[]; author: UserSummary;
  repo: { url: string; owner: string; name: string; stars: number | null; language: string | null };
  counts: { votes: number; comments: number; suggestions: number; reviews: number; bookmarks: number };
  ai_assisted: boolean; is_featured: boolean; status: ContentStatus; created_at: string; updated_at: string; viewer: Viewer;
}
export interface HarnessComponent { type: string; name: string; description: string }
export interface RatingSummary {
  count: number; overall: number | null; documentation: number | null; setup: number | null;
  coordination: number | null; reliability: number | null; counts: Record<string, number>;
}
export interface HarnessDetail extends HarnessSummary {
  detailed_explanation: string; architecture: string | null; components: HarnessComponent[];
  setup_instructions: string | null; limitations: string | null; accepts_collaboration: boolean;
  repo: HarnessSummary['repo'] & {
    forks: number | null; license: string | null; topics: string[]; pushed_at: string | null;
    archived: boolean; fetched_at: string | null; description?: string | null; unavailable?: boolean;
  };
  rating_summary: RatingSummary | null;
}

export type CollaborationStatus = 'sharing' | 'seeking_collaborators' | 'team_formed';
export interface IdeaSummary {
  id: UUID; slug: string; title: string; problem_statement: string; tech_stack: string[];
  category: Category; tags: string[]; author: UserSummary; collaboration_status: CollaborationStatus;
  counts: { votes: number; interest: number; comments: number; suggestions: number; collaborators: number; bookmarks: number };
  ai_assisted: boolean; is_featured: boolean; status: ContentStatus; created_at: string; updated_at: string; viewer: Viewer;
}
export interface IdeaDetail extends IdeaSummary {
  proposed_solution: string; description: string | null;
  expected_features: { title: string; detail?: string | null }[];
  github_url: string | null;
  collaboration: { status: CollaborationStatus; collaborator_count: number; viewer_request: null | { id: UUID; status: string } };
}

export type LinkStatus = 'pending' | 'ok' | 'redirected' | 'broken' | 'unreachable' | 'blocked';
export interface ResourceSummary {
  id: UUID; name: string; url: string; domain: string; description: string; category: Category;
  resource_type: string; official_verified: boolean; tags: string[]; level: string | null; language: string | null;
  link: { status: LinkStatus; http_status: number | null; final_url: string | null; last_checked_at: string | null; open_reports: number };
  submitter: UserSummary;
  counts: { votes: number; comments: number; suggestions: number; bookmarks: number; collections: number };
  ai_assisted: boolean; is_featured: boolean; status: ContentStatus; created_at: string; updated_at: string; viewer: Viewer;
}
export interface ResourceDetail extends ResourceSummary {
  collections_preview?: { id: UUID; slug: string; title: string }[];
}

export interface CollectionSummary {
  id: UUID; slug: string; title: string; description: string | null; category: Category; tags: string[];
  visibility: 'public' | 'private'; owner: UserSummary;
  counts: { items: number; votes: number; comments: number; bookmarks: number };
  preview_domains?: string[];
  ai_assisted: boolean; is_featured: boolean; status: ContentStatus; created_at: string; updated_at: string; viewer: Viewer;
}
export interface CollectionItem { position: number; note: string | null; resource?: ResourceSummary | null; resource_id?: UUID; unavailable?: boolean }
export interface CollectionDetail extends CollectionSummary { items: CollectionItem[] }

export interface Comment {
  id: UUID; deleted: boolean; parent_id: UUID | null; author: UserSummary | null; body: string | null;
  ai_assisted?: boolean; counts?: { votes: number; replies: number }; reply_count: number;
  edited_at?: string | null; created_at: string; viewer?: Viewer; replies?: Comment[];
}
export interface Suggestion {
  id: UUID; kind: string; title: string; body: string; status: string; owner_response: string | null;
  author: UserSummary | null; counts?: { votes: number }; ai_assisted?: boolean; created_at: string; viewer?: Viewer;
}
export interface Review {
  id: UUID; author: UserSummary; what_tested: string; worked_well: string | null; did_not_work: string | null;
  recommendations: string | null; environment: string | null; ratings: Record<string, number | null> | null;
  counts: { votes: number }; created_at: string; viewer?: Viewer; disclaimer_key: string;
}

export interface HomeBucket<T> { featured: T[]; trending: T[]; recent: T[] }
export interface HomeData {
  harnesses: HomeBucket<HarnessSummary>; ideas: HomeBucket<IdeaSummary>;
  resources: HomeBucket<ResourceSummary>; collections: HomeBucket<CollectionSummary>;
  counts: { harnesses: number; ideas: number; resources: number; collections: number; members: number };
}

export interface SearchResults {
  harnesses?: HarnessSummary[]; ideas?: IdeaSummary[]; resources?: ResourceSummary[]; collections?: CollectionSummary[];
}

export interface AppConfig {
  app_name: string;
  categories: Record<'harness' | 'idea' | 'resource' | 'collection', Category[]>;
  enums: Record<string, string[] | Record<string, string[]>>;
  labels?: Record<string, Record<string, string>>;
  limits: Record<string, Record<string, number | string>>;
  sorts: Record<string, string[]>;
  ai: { enabled: boolean; model_label: string; reason: string | null };
}

export interface MeProfile extends UserSummary {
  email: string; email_verified: boolean; has_password?: boolean; role: 'user' | 'moderator' | 'admin'; status?: string;
  bio?: string | null; skills?: string[]; interests?: string[];
}
export interface PublicProfile extends UserSummary {
  bio: string | null; skills: string[]; interests: string[]; website_url: string | null; github_username: string | null;
  contact_links: { label: string; url: string }[]; joined_at: string;
  stats: { harnesses: number; ideas: number; resources: number; collections: number; reviews: number; comments: number };
}

export interface ContextSource { kind: 'platform' | 'github'; label: string; url?: string; status: 'included' | 'failed' | 'unavailable' | 'stale'; truncated?: boolean; reason?: string }
export type ChatEvent =
  | { event: 'meta'; data: { conversation_id: UUID; user_message_id: UUID; assistant_message_id: UUID; context_sources: ContextSource[] } }
  | { event: 'delta'; data: { text: string } }
  | { event: 'done'; data: { assistant_message_id: UUID; status: 'complete'; usage: { input_tokens: number; output_tokens: number }; conversation_title?: string } }
  | { event: 'error'; data: { code: string; message: string } };

export type ContextType = 'harness' | 'idea' | 'resource' | 'collection';
export interface ConversationSummary {
  id: UUID; title: string | null; context: { type: ContextType; id: UUID; title: string } | null;
  message_count: number; last_message_at: string | null;
}
export interface ChatMessage {
  id: UUID; role: 'user' | 'assistant'; content: string;
  status: 'complete' | 'streaming' | 'cancelled' | 'error'; context_sources?: ContextSource[] | null; created_at: string;
  error?: string;
}
export interface ConversationDetail extends ConversationSummary { messages: ChatMessage[] }

/* ── AI drafts (backend §9.6–9.7) ───────────────────────────────────── */
export type DraftTask = 'harness_doc' | 'project_idea' | 'resource_recommendations' | 'feedback_suggestions';
export interface HarnessDocOutput {
  name: string; short_description: string; problem_addressed: string; detailed_explanation: string; architecture: string;
  components: { type: string; name: string; description: string; evidence_path: string | null }[];
  setup_instructions: string; limitations: string; suggested_tools: string[]; suggested_category: string; suggested_tags: string[];
  gaps_and_uncertainties: string[];
}
export interface IdeaDraftOutput {
  title: string; summary: string; problem_statement: string; proposed_solution: string; target_users: string;
  expected_features: { title: string; detail: string }[]; tech_stack: string[]; architecture: string; milestones: string[];
  challenges: string[]; suggested_category: string; suggested_tags: string[];
}
export interface Recommendation {
  order: number; name: string; url: string; description: string; resource_type: string; category: string | null; level: string | null;
  source: 'knowledge_hub' | 'model'; hub_resource_id: string | null;
  verification: { status: 'verified_hub' | 'verified_official_domain' | 'reachable_unverified'; http_status?: number | null; checked_at: string };
}
export interface FeedbackSuggestionOut { category: string; title: string; detail: string; confidence: 'low' | 'medium' | 'high'; based_on: string[] }
export interface AIDraft {
  id: UUID; task: DraftTask; title: string; input: Record<string, unknown>;
  output: Record<string, unknown>; context_sources: ContextSource[] | null; history_count: number; revision: number;
  status: 'draft' | 'published' | 'discarded'; published_target: { type: string; id: UUID } | null;
  model: string; created_at: string; updated_at: string;
  prefill?: unknown; label?: string; history?: { output: Record<string, unknown>; revision: number; saved_at: string }[];
}
export interface HarnessPrefill {
  name: string; repo_url: string; short_description: string; detailed_explanation: string; architecture: string | null;
  components: { type: string; name: string; description: string | null }[]; setup_instructions: string | null; limitations: string | null;
  tools: string[]; category: string | null; tags: string[];
}
export interface IdeaPrefill {
  title: string; problem_statement: string | null; proposed_solution: string | null; description: string;
  tech_stack: string[]; expected_features: { title: string; detail: string }[]; category: string | null; tags: string[];
}
export interface AIToday { tokens: number; generations: number; limit_tokens: number; limit_generations: number; resets_at: string }

export interface Collaboration {
  id: UUID; target: { type: 'idea' | 'harness'; id: UUID; title: string; url_path: string };
  requester: UserSummary | null; owner: UserSummary | null; message: string; skills: string[];
  status: 'pending' | 'accepted' | 'declined' | 'withdrawn'; response_message: string | null;
  created_at: string; responded_at: string | null;
  counterpart_contact: null | { email: string; links: { label: string; url: string }[] };
}
export interface NotificationItem {
  id: UUID; type: string; target_type: string; target_id: UUID;
  data: { target_title?: string; url_path?: string; snippet?: string; actor_display_name?: string | null; count?: number };
  actor: UserSummary | null; read: boolean; read_at: string | null; created_at: string;
}
