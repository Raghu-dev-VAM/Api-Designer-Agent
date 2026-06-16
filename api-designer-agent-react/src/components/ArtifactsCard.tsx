import { useState } from 'react';
import Icon from './Icon';
import SectionHeader from './SectionHeader';
import { artifacts } from '../data';
import type { Requirement, ActivityItem } from '../types';

interface ArtifactsCardProps {
  selectedRequirement: Requirement | null;
  generatedSpec: string;
  postmanCollection: string;
  isGeneratingPostman: boolean;
  dataModels: string;
  isGeneratingDataModels: boolean;
  swaggerDocs: string;
  isGeneratingSwagger: boolean;
  lastGeneratedAt: string;
  activity: ActivityItem[];
  onDownload: (filename: string, contents: string, type?: string) => void;
  onGeneratePostman: () => void;
  onGenerateDataModels: () => void;
  onGenerateSwagger: () => void;
}

const POSTMAN_NAME = 'Postman Collection';
const DATA_MODELS_NAME = 'Data Models / Schemas (JSON)';
const SWAGGER_NAME = 'Swagger Docs';

export default function ArtifactsCard({
  selectedRequirement, generatedSpec, postmanCollection, isGeneratingPostman,
  dataModels, isGeneratingDataModels,
  swaggerDocs, isGeneratingSwagger,
  lastGeneratedAt, activity, onDownload, onGeneratePostman, onGenerateDataModels, onGenerateSwagger,
}: ArtifactsCardProps) {
  const [showPostmanPreview, setShowPostmanPreview] = useState(false);
  const [showDataModelsPreview, setShowDataModelsPreview] = useState(false);
  const [showSwaggerPreview, setShowSwaggerPreview] = useState(false);

  const canGenerate = !!generatedSpec && !!selectedRequirement;

  const renderGenerateActions = (
    generated: string,
    isGenerating: boolean,
    canGen: boolean,
    onGenerate: () => void,
    onPreview: () => void,
    onDl: () => void,
    generateTitle: string,
  ) => {
    if (generated) {
      return (
        <>
          <button className="postman-btn preview" onClick={onPreview}><Icon name="eye" size={13} />Preview</button>
          <button className="postman-btn download" onClick={onDl}><Icon name="download" size={13} />Download</button>
        </>
      );
    }
    return (
      <button
        className="postman-btn generate"
        disabled={!canGen || isGenerating}
        title={canGen ? generateTitle : 'Generate OpenAPI spec first'}
        onClick={onGenerate}
      >
        {isGenerating
          ? <><div className="postman-spinner" />Generating…</>
          : <><Icon name="spark" size={13} />Generate</>}
      </button>
    );
  };

  return (
    <>
      <article className="card artifact-card">
        <SectionHeader number="4" title="Output Artifacts" subtitle="Download and share design artifacts" tone="green" />
        <div className="card-body">
          {artifacts.map(([name, desc, icon, color]) => {
            if (name === SWAGGER_NAME) {
              return (
                <div key={name} className="artifact-item postman-artifact">
                  <span className="artifact-icon" style={{ background: color }}><Icon name={icon} /></span>
                  <span><strong>{name}</strong><small>{desc}</small></span>
                  <div className="postman-actions">
                    {renderGenerateActions(
                      swaggerDocs, isGeneratingSwagger, canGenerate,
                      onGenerateSwagger,
                      () => setShowSwaggerPreview(true),
                      () => onDownload('swagger_docs.html', swaggerDocs, 'text/html'),
                      'Generate Swagger docs',
                    )}
                  </div>
                </div>
              );
            }

            if (name === POSTMAN_NAME) {
              return (
                <div key={name} className="artifact-item postman-artifact">
                  <span className="artifact-icon" style={{ background: color }}><Icon name={icon} /></span>
                  <span><strong>{name}</strong><small>{desc}</small></span>
                  <div className="postman-actions">
                    {renderGenerateActions(
                      postmanCollection, isGeneratingPostman, canGenerate,
                      onGeneratePostman,
                      () => setShowPostmanPreview(true),
                      () => onDownload('postman_collection.json', postmanCollection, 'application/json'),
                      'Generate Postman collection',
                    )}
                  </div>
                </div>
              );
            }

            if (name === DATA_MODELS_NAME) {
              return (
                <div key={name} className="artifact-item postman-artifact">
                  <span className="artifact-icon" style={{ background: color }}><Icon name={icon} /></span>
                  <span><strong>{name}</strong><small>{desc}</small></span>
                  <div className="postman-actions">
                    {renderGenerateActions(
                      dataModels, isGeneratingDataModels, canGenerate,
                      onGenerateDataModels,
                      () => setShowDataModelsPreview(true),
                      () => onDownload('data_models.json', dataModels, 'application/json'),
                      'Generate data models',
                    )}
                  </div>
                </div>
              );
            }

            return (
              <button
                className="artifact-item"
                key={name}
                disabled={!selectedRequirement}
                onClick={() => selectedRequirement && onDownload(
                  `${name.split(' ')[0].toLowerCase()}-${selectedRequirement.id}.txt`,
                  `${name}\n${desc}\n\nGenerated for ${selectedRequirement.id}: ${selectedRequirement.title}`
                )}
              >
                <span className="artifact-icon" style={{ background: color }}><Icon name={icon} /></span>
                <span><strong>{name}</strong><small>{desc}</small></span>
                <Icon name="download" size={16} />
              </button>
            );
          })}

          <div className="last-generated">
            <Icon name="bot" size={38} />
            <div>
              <strong>Last Generated</strong>
              <p>Requirement: {selectedRequirement ? `${selectedRequirement.id}: ${selectedRequirement.title}` : '—'}</p>
              <p>Generated on: {lastGeneratedAt || '—'}</p>
              {activity.map((item, index) => <p key={`${item.label}-${index}`}>{item.label}: {item.value}</p>)}
            </div>
          </div>
        </div>
      </article>

      {/* Swagger docs preview modal */}
      {showSwaggerPreview && swaggerDocs && (
        <div className="preview-modal-overlay" onClick={(e) => e.target === e.currentTarget && setShowSwaggerPreview(false)}>
          <div className="preview-modal">
            <div className="preview-modal-header">
              <span className="preview-modal-title"><Icon name="doc" size={16} />swagger_docs.html</span>
              <div className="preview-modal-actions">
                <button onClick={() => onDownload('swagger_docs.html', swaggerDocs, 'text/html')}><Icon name="download" size={15} />Download</button>
                <button className="preview-modal-close" onClick={() => setShowSwaggerPreview(false)} aria-label="Close"><Icon name="plus" size={16} /></button>
              </div>
            </div>
            <iframe
              srcDoc={swaggerDocs}
              title="Swagger UI Preview"
              style={{ flex: 1, border: 'none', width: '100%', minHeight: '500px' }}
              sandbox="allow-scripts allow-same-origin"
            />
          </div>
        </div>
      )}

      {/* Postman preview modal */}
      {showPostmanPreview && postmanCollection && (
        <div className="preview-modal-overlay" onClick={(e) => e.target === e.currentTarget && setShowPostmanPreview(false)}>
          <div className="preview-modal">
            <div className="preview-modal-header">
              <span className="preview-modal-title"><Icon name="rocket" size={16} />postman_collection.json</span>
              <div className="preview-modal-actions">
                <button onClick={() => onDownload('postman_collection.json', postmanCollection, 'application/json')}><Icon name="download" size={15} />Download</button>
                <button className="preview-modal-close" onClick={() => setShowPostmanPreview(false)} aria-label="Close"><Icon name="plus" size={16} /></button>
              </div>
            </div>
            <pre className="preview-modal-code">
              {(() => { try { return JSON.stringify(JSON.parse(postmanCollection), null, 2); } catch { return postmanCollection; } })()
                .split('\n').map((line, i) => <code key={i}><span>{i + 1}</span>{line}</code>)}
            </pre>
          </div>
        </div>
      )}

      {/* Data models preview modal */}
      {showDataModelsPreview && dataModels && (
        <div className="preview-modal-overlay" onClick={(e) => e.target === e.currentTarget && setShowDataModelsPreview(false)}>
          <div className="preview-modal">
            <div className="preview-modal-header">
              <span className="preview-modal-title"><Icon name="cube" size={16} />data_models.json</span>
              <div className="preview-modal-actions">
                <button onClick={() => onDownload('data_models.json', dataModels, 'application/json')}><Icon name="download" size={15} />Download</button>
                <button className="preview-modal-close" onClick={() => setShowDataModelsPreview(false)} aria-label="Close"><Icon name="plus" size={16} /></button>
              </div>
            </div>
            <pre className="preview-modal-code">
              {(() => { try { return JSON.stringify(JSON.parse(dataModels), null, 2); } catch { return dataModels; } })()
                .split('\n').map((line, i) => <code key={i}><span>{i + 1}</span>{line}</code>)}
            </pre>
          </div>
        </div>
      )}
    </>
  );
}
