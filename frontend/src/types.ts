export interface RepoMeta {
  full_name: string;
  description?: string;
  stars?: number;
  language?: string;
  url?: string;
  default_branch?: string;
}

export interface Snippet {
  path: string;
  start: number;
  end: number;
  code: string;
}

export interface Section {
  title: string;
  explanation: string;
  snippets: Snippet[];
}

export interface Overview {
  mode: "A" | "B";
  repo: RepoMeta;
  file_count: number;
  files_read: string[];
  summary: string;
  mermaid: string;
  sections: Section[];
  selection?: { name: string; reason: string };
  concept?: string;
}

export interface FollowupAnswer {
  answer: string;
  mermaid: string;
  snippets: Snippet[];
  newly_read?: string[];
}

export interface Backends {
  available: Record<string, boolean>;
  default: string;
}

/** A single turn in the chat-style conversation. */
export type ChatTurn =
  | { kind: "question"; text: string }
  | { kind: "answer"; data: FollowupAnswer };