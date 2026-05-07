import type { Requirement } from '../types';
import { config } from '../config';

const TIMEOUT_MS = 120_000; // 2 minutes — enough for Render cold start

function fetchWithTimeout(input: RequestInfo, init: RequestInit = {}, ms = TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  return fetch(input, { ...init, signal: controller.signal }).finally(() => clearTimeout(timer));
}

export async function extractRequirementsFromDocx(file: File): Promise<{ requirements: Requirement[]; rawText: string }> {
  const form = new FormData();
  form.append('file', file);

  const rawText = await extractRawText(file);

  const res = await fetchWithTimeout(`${config.apiBaseUrl}/api/designer/extract-requirements`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    const detail = typeof err.detail === 'string'
      ? err.detail.replace(/[\r\n]/g, ' ')
      : 'Failed to extract requirements';
    throw new Error(detail);
  }

  const data = await res.json();
  return {
    requirements: (data.requirements as Requirement[]).map((r) => ({ ...r, status: r.status ?? 'Draft' })),
    rawText,
  };
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
  const body = {
    requirements: [{
      id: requirement.id,
      title: requirement.title,
      description: requirement.desc,
      source: requirement.source,
      priority: requirement.priority,
      status: requirement.status,
    }],
    api_title: requirement.title,
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
