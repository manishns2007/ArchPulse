import React, { useState } from 'react';
import {
  X,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowRight,
  FileText,
  Clock,
  Layers,
} from 'lucide-react';
import {
  runSequentialPipeline,
  INITIAL_PIPELINE_STAGES,
  PipelineStageState,
  PipelineStageKey,
} from '../../api/pipeline';

interface AddCommunicationModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  onSuccess: (commId: string) => void;
}

const DEMO_TEMPLATES = [
  {
    label: 'Site Coordination Meeting (Tasks, Approvals & Deadlines)',
    text: `Site coordination meeting summary:
1. Marco confirmed MEP ducting in zone B must be rerouted before inspection by Friday Sept 19.
2. Rachel approved the revised Italian travertine stone tiles for the penthouse master suites.
3. David will coordinate electrical conduits with the ceiling contractor by Tuesday.
4. Elena confirmed the budget overrun of $12,500 for upgraded HVAC chillers is approved by ownership.
5. Sarah must deliver finalized structural load calculations to city engineering department by September 24.`,
  },
  {
    label: 'Design Team Email: Facade Glazing Specifications',
    text: `Hi Team,
Following up on the facade engineering review:
We have officially approved triple-pane acoustic glazing for the street-facing curtain walls (Spec Ref: FG-402).
Alex - please finalize thermal barrier detailing by end of week, Sept 18th.
Marcus is responsible for submitting acoustic test certifications to the lead architect by Sept 22.
Best regards,
Claire`,
  },
  {
    label: 'Slack / Chat Thread: Concrete Pour Logistics',
    text: `Liam: Quick update from the field. Foundation slab pour for Sector 4 is locked in for Thursday 7:00 AM.
Carlos: Roger that. Carlos will ensure cement mixer trucks have site access clearance by Wednesday 5 PM.
Liam: Also, structural engineer approved adding superplasticizer batch #441 to maintain slump.`,
  },
];

export const AddCommunicationModal: React.FC<AddCommunicationModalProps> = ({
  isOpen,
  onClose,
  projectId,
  onSuccess,
}) => {
  const [content, setContent] = useState('');
  const [sourceType, setSourceType] = useState<'text' | 'transcript'>('text');
  const [isRunning, setIsRunning] = useState(false);
  const [stages, setStages] = useState<PipelineStageState[]>(INITIAL_PIPELINE_STAGES);
  const [pipelineResult, setPipelineResult] = useState<any>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleStageUpdate = (
    stageKey: PipelineStageKey,
    status: 'running' | 'completed' | 'failed',
    data?: any,
    error?: string
  ) => {
    setStages(prev =>
      prev.map(s => (s.key === stageKey ? { ...s, status, data, error } : s))
    );
  };

  const handleExecute = async () => {
    if (!content.trim() || isRunning) return;

    setIsRunning(true);
    setPipelineError(null);
    setPipelineResult(null);
    setStages(INITIAL_PIPELINE_STAGES.map(s => ({ ...s, status: 'idle', error: undefined, data: undefined })));

    try {
      const result = await runSequentialPipeline(
        projectId,
        content.trim(),
        sourceType,
        handleStageUpdate
      );
      setPipelineResult(result);
    } catch (err: any) {
      setPipelineError(err.message || 'Pipeline execution encountered an error.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleReset = () => {
    setContent('');
    setStages(INITIAL_PIPELINE_STAGES);
    setPipelineResult(null);
    setPipelineError(null);
  };

  return (
    <div className="drawer-overlay" onClick={isRunning ? undefined : onClose}>
      <div
        className="glass-panel animate-scale-in"
        onClick={e => e.stopPropagation()}
        style={{
          width: '760px',
          maxWidth: '92vw',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
          boxShadow: 'var(--shadow-lg)',
          border: '1px solid var(--border-subtle)',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-subtle)',
            background: 'var(--bg-surface)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '30px',
                height: '30px',
                borderRadius: 'var(--radius-sm)',
                background: 'linear-gradient(135deg, var(--accent) 0%, #4338ca 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Sparkles size={16} color="#fff" />
            </div>
            <div>
              <h2 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
                Ingest Project Communication
              </h2>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Target Project: <span style={{ color: 'var(--accent-light)', fontFamily: 'var(--font-mono)' }}>{projectId}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isRunning}
            className="btn-ghost"
            style={{ padding: '6px' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Preset Templates */}
          {!isRunning && !pipelineResult && (
            <div>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px', letterSpacing: '0.5px' }}>
                Quick Presets (One-Click Populate)
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {DEMO_TEMPLATES.map((tmpl, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setContent(tmpl.text)}
                    className="btn-ghost"
                    style={{
                      justifyContent: 'flex-start',
                      fontSize: '12px',
                      padding: '7px 10px',
                      background: 'var(--bg-surface)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      textAlign: 'left',
                    }}
                  >
                    <FileText size={14} color="var(--accent)" />
                    <span style={{ color: 'var(--text-secondary)' }}>{tmpl.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Text Area Input */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Raw Unstructured Content (Meeting notes, Slack thread, Email, Transcript)
              </label>
              <div style={{ display: 'flex', gap: '8px', fontSize: '11px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', color: 'var(--text-secondary)' }}>
                  <input
                    type="radio"
                    name="sourceType"
                    checked={sourceType === 'text'}
                    onChange={() => setSourceType('text')}
                    disabled={isRunning || !!pipelineResult}
                  />
                  Text / Email
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', color: 'var(--text-secondary)' }}>
                  <input
                    type="radio"
                    name="sourceType"
                    checked={sourceType === 'transcript'}
                    onChange={() => setSourceType('transcript')}
                    disabled={isRunning || !!pipelineResult}
                  />
                  Meeting Transcript
                </label>
              </div>
            </div>

            <textarea
              value={content}
              onChange={e => setContent(e.target.value)}
              placeholder="Paste project communication text here..."
              disabled={isRunning || !!pipelineResult}
              rows={6}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-primary)',
                fontFamily: 'inherit',
                fontSize: '13px',
                lineHeight: 1.5,
                resize: 'vertical',
              }}
            />
          </div>

          {/* Sequential Live Pipeline Status Tracker */}
          {(isRunning || pipelineResult || pipelineError) && (
            <div
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '14px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Layers size={14} color="var(--accent)" />
                  <span>Sequential M1→M8 Execution Flow</span>
                </div>
                {isRunning && (
                  <span className="badge badge-review" style={{ fontSize: '10px' }}>
                    Executing Live
                  </span>
                )}
                {pipelineResult && (
                  <span className="badge badge-approved" style={{ fontSize: '10px' }}>
                    All 8 Modules Complete
                  </span>
                )}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                {stages.map(s => {
                  let badgeBg = 'var(--bg-card)';
                  let badgeColor = 'var(--text-muted)';
                  let icon = <Clock size={12} />;

                  if (s.status === 'running') {
                    badgeBg = 'var(--accent-subtle)';
                    badgeColor = 'var(--accent-light)';
                    icon = <Loader2 size={12} className="animate-spin" />;
                  } else if (s.status === 'completed') {
                    badgeBg = 'rgba(16, 185, 129, 0.12)';
                    badgeColor = 'var(--status-approved)';
                    icon = <CheckCircle2 size={12} />;
                  } else if (s.status === 'failed') {
                    badgeBg = 'rgba(239, 68, 68, 0.15)';
                    badgeColor = 'var(--status-rejected)';
                    icon = <AlertCircle size={12} />;
                  }

                  return (
                    <div
                      key={s.key}
                      style={{
                        background: badgeBg,
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '8px 10px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--accent-light)' }}>
                          {s.module}
                        </span>
                        <span style={{ color: badgeColor }}>{icon}</span>
                      </div>
                      <div style={{ fontSize: '11px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {s.label}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Error Output */}
              {pipelineError && (
                <div style={{ marginTop: '12px', padding: '10px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--status-rejected)', borderRadius: 'var(--radius-sm)', color: 'var(--status-rejected)', fontSize: '12px' }}>
                  <strong>Pipeline Error:</strong> {pipelineError}
                </div>
              )}

              {/* Success Extraction Summary */}
              {pipelineResult && (
                <div
                  style={{
                    marginTop: '12px',
                    padding: '12px',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-card)',
                    borderRadius: 'var(--radius-sm)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', gap: '16px', fontSize: '12px' }}>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Actions: </span>
                      <strong style={{ color: 'var(--text-primary)' }}>{pipelineResult.actions?.length || 0}</strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Tasks: </span>
                      <strong style={{ color: 'var(--text-primary)' }}>{pipelineResult.tasks?.length || 0}</strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Decisions: </span>
                      <strong style={{ color: 'var(--text-primary)' }}>{pipelineResult.decisions?.length || 0}</strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Memory: </span>
                      <strong style={{ color: 'var(--status-approved)' }}>Indexed</strong>
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      onSuccess(pipelineResult.communication.communication_id);
                      onClose();
                    }}
                    className="btn-primary"
                    style={{ fontSize: '11px', padding: '6px 12px' }}
                  >
                    <span>View In Workspace</span>
                    <ArrowRight size={13} />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '14px 20px',
            borderTop: '1px solid var(--border-subtle)',
            background: 'var(--bg-surface)',
          }}
        >
          <button
            type="button"
            onClick={handleReset}
            disabled={isRunning}
            className="btn-ghost"
            style={{ fontSize: '12px' }}
          >
            Clear
          </button>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isRunning}
              className="btn-secondary"
              style={{ fontSize: '12px' }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleExecute}
              disabled={isRunning || !content.trim() || !!pipelineResult}
              className="btn-primary"
              style={{ fontSize: '12px' }}
            >
              {isRunning ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  <span>Processing M1→M8...</span>
                </>
              ) : (
                <>
                  <Sparkles size={14} />
                  <span>Execute Pipeline</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
