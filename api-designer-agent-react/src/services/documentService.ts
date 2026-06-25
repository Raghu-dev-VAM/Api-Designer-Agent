import type { Requirement } from '../types';
import { config } from '../config';

const TIMEOUT_MS = 120_000;

async function fetchWithTimeout(input: RequestInfo, init: RequestInit = {}, ms = TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  const res = await fetch(input, { ...init, signal: controller.signal }).finally(() => clearTimeout(timer));
  return res;
}

/** Normalise a raw requirements array from either endpoint to match the Requirement type.
 *  Workflow spec fields: id, title, desc, source, priority, status, summary, acceptanceCriteria */
function normaliseRequirements(raw: unknown[]): Requirement[] {
  return (raw as Array<Record<string, unknown>>).map((r) => {
    const ac = r.acceptanceCriteria;
    const acStr = Array.isArray(ac)
      ? ac.map((c) => String(c).trim()).filter(Boolean).join(' ')
      : typeof ac === 'string' ? ac : '';
    return {
      ...r,
      desc: (r.desc ?? r.description ?? '') as string,
      summary: (r.summary ?? '') as string,
      method: (r.method ?? 'get') as string,
      path: (r.path ?? '/resource') as string,
      status: ((r.status ?? 'Draft') as 'Draft' | 'Approved' | 'Rejected'),
      acceptanceCriteria: acStr,
    };
  }) as Requirement[];
}



async function extractRawText(file: File): Promise<string> {
  try {
    const mammoth = await import('mammoth');
    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText({ arrayBuffer });
    return result.value.trim();
  } catch {
    return '';
  }
}

export async function generateOpenApi(requirement: Requirement): Promise<{ yaml: string }> {
  // Sanitise all string fields — strip control characters that cause JSON 422
  const clean = (s: string) => (s ?? '').replace(/[\x00-\x1F\x7F]/g, ' ').trim();

  const body = {
    requirements: [{
      id: clean(requirement.id),
      title: clean(requirement.title),
      description: clean(
        `${requirement.desc}` +
        `${requirement.summary ? ` Summary: ${requirement.summary}` : ''}` +
        `${requirement.method ? ` HTTP Method: ${requirement.method.toUpperCase()}` : ''}` +
        `${requirement.path ? ` Path: ${requirement.path}` : ''}`
      ),
      source: clean(requirement.source),
      priority: clean(requirement.priority),
      status: requirement.status ?? 'Draft',
    }],
    api_title: clean(requirement.title),
    api_version: '1.0.0',
  };

  const res = await fetchWithTimeout(`${config.apiBaseUrl}/api/designer/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Generation failed' }));
    const detail = typeof err.detail === 'string'
      ? err.detail.replace(/[\r\n]/g, ' ')
      : 'Failed to generate OpenAPI spec';
    throw new Error(detail);
  }

  const data = await res.json();
  return { yaml: data.open_api_yaml };
}

export async function generatePostmanCollection(openApiYaml: string, apiTitle: string): Promise<string> {
  const body = {
    open_api_yaml: openApiYaml,
    artifact_type: 'postman',
    api_title: apiTitle,
  };

  const res = await fetchWithTimeout(`${config.apiBaseUrl}/api/designer/artifact`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to generate Postman collection' }));
    const detail = typeof err.detail === 'string'
      ? err.detail.replace(/[\r\n]/g, ' ')
      : 'Failed to generate Postman collection';
    throw new Error(detail);
  }

  const data = await res.json();
  return data.content;
}

export interface AzureConfig {
  organization: string;
  project: string;
  pat: string;
  areaPath?: string;
  maxItems?: number;
}

export async function fetchAzureStories(cfg: AzureConfig): Promise<Requirement[]> {
  const body = {
    organization: cfg.organization,
    project: cfg.project,
    pat: cfg.pat,
    area_path: cfg.areaPath || null,
    max_items: cfg.maxItems ?? 50,
  };

  const res = await fetchWithTimeout(`${config.apiBaseUrl}/api/azure/fetch-stories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Azure fetch failed' }));
    const detail = typeof err.detail === 'string'
      ? err.detail.replace(/[\r\n]/g, ' ')
      : 'Failed to fetch Azure DevOps stories';
    throw new Error(detail);
  }

  const data = await res.json();
  return (data.requirements as Requirement[]).map((r) => ({ ...r, status: r.status ?? 'Draft' }));
}

export interface JiraConfig {
  host: string;
  email: string;
  apiToken: string;
  projectKey: string;
  maxItems?: number;
}

export interface ConfluenceConfig {
  host: string;
  email: string;
  apiToken: string;
  spaceKey: string;
  maxItems?: number;
}

export async function fetchJiraStories(cfg: JiraConfig): Promise<Requirement[]> {
  const body = {
    host: cfg.host,
    email: cfg.email,
    api_token: cfg.apiToken,
    project_key: cfg.projectKey,
    max_items: cfg.maxItems ?? 50,
  };

  const res = await fetchWithTimeout(`${config.apiBaseUrl}/api/jira/fetch-stories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Jira fetch failed' }));
    throw new Error(typeof err.detail === 'string' ? err.detail.replace(/[\r\n]/g, ' ') : 'Failed to fetch Jira stories');
  }

  const data = await res.json();
  return (data.requirements as Requirement[]).map((r) => ({ ...r, status: r.status ?? 'Draft' }));
}

export async function fetchConfluenceStories(cfg: ConfluenceConfig): Promise<Requirement[]> {
  const body = {
    host: cfg.host,
    email: cfg.email,
    api_token: cfg.apiToken,
    space_key: cfg.spaceKey,
    max_items: cfg.maxItems ?? 20,
  };

  const res = await fetchWithTimeout(`${config.apiBaseUrl}/api/confluence/fetch-stories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Confluence fetch failed' }));
    throw new Error(typeof err.detail === 'string' ? err.detail.replace(/[\r\n]/g, ' ') : 'Failed to fetch Confluence pages');
  }

  const data = await res.json();
  return (data.requirements as Requirement[]).map((r) => ({ ...r, status: r.status ?? 'Draft' }));
}

export interface ColumnMapping {
  userStory: string;
  storyId: string;
  title: string;
  priority: string;
  acceptanceCriteria: string;
}

/**
 * Unified extraction — POST /api/designer/extract
 * Works for .docx (Word), .xlsx and .csv (Excel/CSV).
 *
 * Flow:
 *  1. No mapping passed  → server returns { needs_mapping, columns } → show modal
 *  2. Mapping passed     → server extracts and returns requirements
 */
export async function extractRequirementsFromFile(
  file: File,
  mapping?: ColumnMapping,
): Promise<{ requirements: Requirement[]; rawText: string; needsMapping?: boolean; columns?: string[]; filename?: string }> {
  const form = new FormData();
  form.append('file', file);
  if (mapping?.userStory) {
    form.append('userStory', mapping.userStory);
  }

  const res = await fetchWithTimeout(`${config.apiBaseUrl}/api/designer/extract`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Extraction failed' }));
    throw new Error(typeof err.detail === 'string' ? err.detail.replace(/[\r\n]/g, ' ') : 'Failed to extract requirements');
  }

  const data = await res.json();

  // Spreadsheet with no mapping — tell UI to open the column-mapping modal
  if (data.needs_mapping) {
    return { requirements: [], rawText: '', needsMapping: true, columns: data.columns, filename: data.filename };
  }

  // Word: also extract raw text client-side for the Raw tab
  let rawText = data.raw_text ?? '';
  if (!rawText && file.name.toLowerCase().endsWith('.docx')) {
    rawText = await extractRawText(file);
  }

  return { requirements: normaliseRequirements(data.requirements), rawText };
}

export async function generateDataModels(openApiYaml: string): Promise<string> {
  const body = { open_api_yaml: openApiYaml, artifact_type: 'data-models' };

  const res = await fetchWithTimeout(`${config.apiBaseUrl}/api/designer/data-models`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to generate data models' }));
    throw new Error(typeof err.detail === 'string' ? err.detail.replace(/[\r\n]/g, ' ') : 'Failed to generate data models');
  }

  const data = await res.json();
  return data.content;
}

export interface CodeGenStatus {
  event: 'status' | 'agent_message' | 'done' | 'error' | 'incremental_ready';
  agent?: string;
  message?: string;
  preview?: string;
  step?: number;
  total?: number;
  percent?: number;
  project_name?: string;
  file_count?: number;
  src_count?: number;
  test_count?: number;
  file_list?: string[];
  src_files?: string[];
  test_files?: string[];
  zip_base64?: string;
  pre_review_zip_base64?: string;
  pre_review_available?: boolean;
  download_url?: string;
}

export function startCodeGen(
  openApiYaml: string,
  projectName: string,
  llmProvider: 'groq' | 'openai',
  onStatus: (s: CodeGenStatus) => void,
): () => void {
  let es: EventSource | null = null;
  let cancelled = false;

  fetchWithTimeout(`${config.apiBaseUrl}/api/codegen/generate-dotnet`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      open_api_yaml: openApiYaml,
      project_name: projectName,
      llm_provider: llmProvider,
    }),
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to start code generation' }));
      onStatus({ event: 'error', message: typeof err.detail === 'string' ? err.detail : 'Failed to start' });
      return;
    }
    const data = await res.json();
    if (cancelled) return;

    es = new EventSource(`${config.apiBaseUrl}${data.stream_url}`);

    es.addEventListener('status', (e) => {
      onStatus({ event: 'status', ...JSON.parse(e.data) });
    });
    es.addEventListener('agent_message', (e) => {
      onStatus({ event: 'agent_message', ...JSON.parse(e.data) });
    });
    es.addEventListener('incremental_ready', (e) => {
      onStatus({ event: 'incremental_ready', ...JSON.parse(e.data) });
    });
    es.addEventListener('done', (e) => {
      onStatus({ event: 'done', ...JSON.parse(e.data) });
      es?.close();
    });
    es.addEventListener('error', (e) => {
      const data = (e as MessageEvent).data;
      onStatus({ event: 'error', message: data ? JSON.parse(data).message : 'Stream error' });
      es?.close();
    });
  }).catch((err) => {
    onStatus({ event: 'error', message: err.message });
  });

  return () => { cancelled = true; es?.close(); };
}

export async function generateSwaggerDocs(openApiYaml: string): Promise<string> {
  const body = { open_api_yaml: openApiYaml, artifact_type: 'swagger' };

  const res = await fetchWithTimeout(`${config.apiBaseUrl}/api/designer/swagger-docs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to generate Swagger docs' }));
    throw new Error(typeof err.detail === 'string' ? err.detail.replace(/[\r\n]/g, ' ') : 'Failed to generate Swagger docs');
  }

  const data = await res.json();
  return data.content;
}
