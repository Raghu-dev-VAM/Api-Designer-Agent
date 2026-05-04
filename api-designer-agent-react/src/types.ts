export interface Source {
  id: string;
  name: string;
  desc: string;
  color: string;
  icon: string;
}

export interface Requirement {
  id: string;
  title: string;
  desc: string;
  source: string;
  priority: string;
  method: string;
  path: string;
  summary: string;
  status: 'Draft' | 'Approved' | 'Rejected';
  acceptanceCriteria?: string[];
  tags?: string[];
}

export interface ActivityItem {
  label: string;
  value: string;
}

export interface OpenApiResult {
  yaml: string;
}
