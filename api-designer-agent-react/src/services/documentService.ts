import type { Requirement } from '../types';
import { config } from '../config';

export async function extractRequirementsFromDocx(file: File): Promise<Requirement[]> {
  const form = new FormData();
  form.append('file', file);

  const res = await fetch(`${config.apiBaseUrl}/api/designer/extract-requirements`, {
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
  return (data.requirements as Requirement[]).map((r) => ({ ...r, status: r.status ?? 'Draft' }));
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

  const res = await fetch(`${config.apiBaseUrl}/api/designer/generate`, {
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
