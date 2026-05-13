import type { Source, Requirement } from './types';

export const sources: Source[] = [
  { id: 'azure', name: 'Azure DevOps', desc: 'Boards / Wiki / PRD', color: '#dbeafe', icon: 'azure' },
  { id: 'jira', name: 'Jira', desc: 'Stories / Epics', color: '#e0f2fe', icon: 'diamond' },
  { id: 'confluence', name: 'Confluence', desc: 'Pages / Docs', color: '#dbeafe', icon: 'waves' },
  { id: 'excel', name: 'Excel / CSV', desc: '.xlsx, .csv', color: '#dcfce7', icon: 'sheet' }
];

export const requirements: Requirement[] = [];

export const artifacts: [string, string, string, string][] = [
  ['Swagger Docs', 'Interactive HTML API documentation', 'doc', '#ccfbf1'],
  ['API Endpoints Summary (Markdown)', 'Human-readable API summary', 'file', '#dbeafe'],
  ['Data Models / Schemas (JSON)', 'Request & response schemas', 'cube', '#ede9fe'],
  ['Postman Collection', 'Ready-to-use collection for testing', 'rocket', '#ffedd5'],
  ['Sequence Diagrams (Mermaid)', 'API flow and interactions', 'flow', '#e0e7ff'],
  ['API Design Review (PDF)', 'Review checklist and guidelines', 'checkfile', '#ccfbf1']
];

export const actions: [string, string, string][] = [
  ['Generate / Regenerate', 'Generate API design from requirement', 'spark'],
  ['Validate OpenAPI Spec', 'Validate spec for errors, standards & best practices', 'shield'],
  ['Export to API Gateway', 'Export spec to gateway', 'cloud'],
  ['Compare Changes', 'Compare with previous versions', 'sync'],
  ['Version History', 'View all generated versions', 'history']
];

export const features: [string, string[], string][] = [
  ['Requirement Intake', ['Connects to multiple sources', 'Extracts functional requirements', 'Identifies entities, actions, rules'], 'file'],
  ['API Design & Modeling', ['Identifies resources & operations', 'Defines request/response models', 'Applies REST best practices'], 'flow'],
  ['OpenAPI Generation', ['Generates OpenAPI 3.0 spec', 'Validates and ensures consistency', 'Versioning and tagging support'], 'spark'],
  ['Documentation & Artifacts', ['Generates docs, schemas, examples', 'Creates Postman collection', 'Generates sequence diagrams'], 'doc'],
  ['Governance & Quality', ['Follows API design standards', 'Security, error handling, pagination', 'Reusable and maintainable design'], 'shield']
];
