import type { Source, Requirement } from './types';

export const sources: Source[] = [
  { id: 'azure', name: 'Azure DevOps', desc: 'Boards / Wiki / PRD', color: '#dbeafe', icon: 'azure' },
  { id: 'jira', name: 'Jira', desc: 'Stories / Epics', color: '#e0f2fe', icon: 'diamond' },
  { id: 'confluence', name: 'Confluence', desc: 'Pages / Docs', color: '#dbeafe', icon: 'waves' },
  { id: 'excel', name: 'Excel / CSV', desc: '.xlsx, .csv', color: '#dcfce7', icon: 'sheet' }
];

export const requirements: Requirement[] = [
  { id: 'FR-001', title: 'Create Policy', desc: 'User should be able to create a policy', source: 'Jira: PROJ-123', priority: 'High', method: 'post', path: '/policies', summary: 'Create a new policy', status: 'Approved' },
  { id: 'FR-002', title: 'Validate Customer Details', desc: 'System should validate customer details', source: 'Confluence: Page-45', priority: 'Medium', method: 'post', path: '/customers/validate', summary: 'Validate customer details', status: 'Approved' },
  { id: 'FR-003', title: 'Fetch Policy by Policy Number', desc: 'System should fetch policy by policy number', source: 'Azure DevOps: Task-678', priority: 'High', method: 'get', path: '/policies/{policyNumber}', summary: 'Fetch policy by policy number', status: 'Draft' },
  { id: 'FR-004', title: 'Update Policy Status', desc: 'User should be able to update policy status', source: 'Excel: Sheet1', priority: 'Medium', method: 'patch', path: '/policies/{policyNumber}/status', summary: 'Update policy status', status: 'Draft' },
  { id: 'FR-005', title: 'Cancel Policy', desc: 'User should be able to cancel a policy', source: 'Local File: requirements.txt', priority: 'High', method: 'post', path: '/policies/{policyNumber}/cancel', summary: 'Cancel an active policy', status: 'Rejected' },
];

export const artifacts: [string, string, string, string][] = [
  ['OpenAPI Specification (YAML/JSON)', 'Complete OpenAPI 3.0 specification', 'doc', '#ccfbf1'],
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
