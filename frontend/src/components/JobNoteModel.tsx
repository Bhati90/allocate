
import React, { useEffect, useRef, useState, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { X, Send, CheckCircle, RotateCcw, Pencil } from 'lucide-react';
import { toast } from './ui/sonner';
import { API_BASE_URL } from '../types/config';

// ── Types ─────────────────────────────────────────────────────────────────────

interface NoteUser {
  id: number;
  username: string;
  full_name: string;
}

interface JobNote {
  id: number;
  job_id: string;
  author: NoteUser;
  text: string;
  tags: string[];
  tag_labels: string[];
  mentions: NoteUser[];
  is_resolved: boolean;
  resolved_by: NoteUser | null;
  resolved_at: string | null;
  resolution_note: string;
  note_date: string;
  created_at: string;
}

// ── Tag config ─────────────────────────────────────────────────────────────────

const ALL_TAGS: { key: string; label: string; color: string; bg: string; border: string }[] = [
  { key: 'urgent',         label: '🔴 Urgent',          color: '#991b1b', bg: '#fef2f2', border: '#fca5a5' },
  { key: 'important',      label: '⚠️ Important',        color: '#92400e', bg: '#fffbeb', border: '#fcd34d' },
  { key: 'mukkadam_issue', label: '👷 Mukkadam Issue',   color: '#1e3a5f', bg: '#eff6ff', border: '#93c5fd' },
  { key: 'farmer_issue',   label: '🌾 Farmer Issue',     color: '#14532d', bg: '#f0fdf4', border: '#86efac' },
  { key: 'sales',          label: '💼 Sales',             color: '#4c1d95', bg: '#f5f3ff', border: '#c4b5fd' },
  { key: 'operations',     label: '⚙️ Operations',       color: '#374151', bg: '#f9fafb', border: '#d1d5db' },
  { key: 'data_wrong',     label: '📊 Data Wrong',        color: '#7c2d12', bg: '#fff7ed', border: '#fdba74' },
  { key: 'price_mismatch', label: '💰 Price Mismatch',   color: '#134e4a', bg: '#f0fdfa', border: '#99f6e4' },
  { key: 'team_charging',  label: '⚡ Team Charging',    color: '#713f12', bg: '#fefce8', border: '#fef08a' },
];

const TAG_MAP = Object.fromEntries(ALL_TAGS.map(t => [t.key, t]));

// ── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function renderTextWithMentions(text: string, mentionedIds: number[], currentUserId: number) {
  const parts = text.split(/(@\w+)/g);
  return parts.map((part, i) => {
    if (part.startsWith('@')) {
      const name = part.slice(1).toLowerCase();
      const isMe = mentionedIds.some(id => id === currentUserId) &&
                   part.toLowerCase().includes(name);
      return (
        <span
          key={i}
          className={`font-bold ${isMe ? 'text-blue-600 bg-blue-50 px-0.5 rounded' : 'text-indigo-600'}`}
        >
          {part}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

// ── TagChip ───────────────────────────────────────────────────────────────────

const TagChip: React.FC<{ tagKey: string; small?: boolean }> = ({ tagKey, small }) => {
  const t = TAG_MAP[tagKey];
  if (!t) return null;
  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold border ${small ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-0.5'}`}
      style={{ color: t.color, background: t.bg, borderColor: t.border }}
    >
      {t.label}
    </span>
  );
};

// ── Main JobNoteModal ─────────────────────────────────────────────────────────

interface JobNoteModalProps {
  jobId: string;
  jobLabel?: string; // e.g. "Pruning – Ramesh Farm"
  noteDate: string;  // YYYY-MM-DD
  currentUserId: number;
  currentUserName: string;
  clusterId: number;
  onClose: () => void;
}

export const JobNoteModal: React.FC<JobNoteModalProps> = ({
  jobId, jobLabel, noteDate, currentUserId, currentUserName, clusterId, onClose,
}) => {
  const [notes, setNotes]           = useState<JobNote[]>([]);
  const [loading, setLoading]       = useState(true);
  const [text, setText]             = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [mentionIds, setMentionIds] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // @mention autocomplete
  const [mentionQuery, setMentionQuery]     = useState('');
  const [mentionResults, setMentionResults] = useState<NoteUser[]>([]);
  const [mentionAnchor, setMentionAnchor]   = useState<number | null>(null); // cursor pos of '@'
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // resolve UI state
  const [resolvingId, setResolvingId]       = useState<number | null>(null);
  const [resolveText, setResolveText]       = useState('');
  const [resolveLoading, setResolveLoading] = useState(false);

  // ── fetch notes ──────────────────────────────────────────────────────────────
  const fetchNotes = useCallback(async () => {
    try {
      const res  = await fetch(
        `${API_BASE_URL}/api/job-notes/?job_id=${jobId}&date=${noteDate}&cluster_id=${clusterId}`
      );
      const data = await res.json();
      setNotes(data);
    } catch {
      toast.error('Failed to load notes');
    } finally {
      setLoading(false);
    }
  }, [jobId, noteDate, clusterId]);

  useEffect(() => { fetchNotes(); }, [fetchNotes]);

  // ── @mention autocomplete ────────────────────────────────────────────────────
  const handleTextChange = async (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val    = e.target.value;
    const cursor = e.target.selectionStart;
    setText(val);

    // find the last '@' before cursor
    const before = val.slice(0, cursor);
    const atIdx  = before.lastIndexOf('@');
    if (atIdx !== -1 && !before.slice(atIdx + 1).includes(' ')) {
      const q = before.slice(atIdx + 1);
      setMentionQuery(q);
      setMentionAnchor(atIdx);
      if (q.length >= 1) {
        try {
          const res  = await fetch(`${API_BASE_URL}/api/users/search/?q=${encodeURIComponent(q)}`);
          const data = await res.json();
          setMentionResults(data);
        } catch { setMentionResults([]); }
      } else {
        setMentionResults([]);
      }
    } else {
      setMentionResults([]);
      setMentionAnchor(null);
    }
  };

  const insertMention = (user: NoteUser) => {
    if (mentionAnchor === null) return;
    const before  = text.slice(0, mentionAnchor);
    const cursor  = textareaRef.current?.selectionStart ?? text.length;
    const after   = text.slice(cursor);
    const newText = `${before}@${user.username} ${after}`;
    setText(newText);
    setMentionIds(prev => [...new Set([...prev, user.id])]);
    setMentionResults([]);
    setMentionAnchor(null);
    setTimeout(() => {
      if (textareaRef.current) {
        const pos = (before + `@${user.username} `).length;
        textareaRef.current.selectionStart = pos;
        textareaRef.current.selectionEnd   = pos;
        textareaRef.current.focus();
      }
    }, 0);
  };

  const toggleTag = (key: string) =>
    setSelectedTags(prev =>
      prev.includes(key) ? prev.filter(t => t !== key) : [...prev, key]
    );

  // ── submit note ──────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!text.trim()) return toast.error('Write something first');
    setSubmitting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API_BASE_URL}/api/job-notes/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Token ${token}` } : {}),
        },
        body: JSON.stringify({
          job_id:      jobId,
          text:        text.trim(),
          tags:        selectedTags,
          mention_ids: mentionIds,
          note_date:   noteDate,
        }),
      });
      if (!res.ok) throw new Error();
      toast.success('Note added');
      setText('');
      setSelectedTags([]);
      setMentionIds([]);
      fetchNotes();
    } catch {
      toast.error('Failed to add note');
    } finally {
      setSubmitting(false);
    }
  };

  // ── resolve ──────────────────────────────────────────────────────────────────
  const handleResolve = async (noteId: number) => {
    if (!resolveText.trim()) return toast.error('Add a resolution note');
    setResolveLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API_BASE_URL}/api/job-notes/${noteId}/resolve/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Token ${token}` } : {}),
        },
        body: JSON.stringify({ resolution_note: resolveText }),
      });
      if (!res.ok) throw new Error();
      toast.success('Marked as resolved ✅');
      setResolvingId(null);
      setResolveText('');
      fetchNotes();
    } catch {
      toast.error('Failed to resolve');
    } finally {
      setResolveLoading(false);
    }
  };

  const handleUnresolve = async (noteId: number) => {
    try {
      const token = localStorage.getItem('auth_token');
      await fetch(`${API_BASE_URL}/api/job-notes/${noteId}/unresolve/`, {
        method: 'POST',
        headers: { ...(token ? { Authorization: `Token ${token}` } : {}) },
      });
      fetchNotes();
    } catch { toast.error('Failed'); }
  };

  // ── split notes ───────────────────────────────────────────────────────────────
  const unresolved = notes.filter(n => !n.is_resolved);
  const resolved   = notes.filter(n =>  n.is_resolved);

  const mentionedMe = (n: JobNote) =>
    n.mentions.some(m => m.id === currentUserId);

  return ReactDOM.createPortal(
    <div
      className="fixed inset-0 z-[99999] flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.45)' }}
      onClick={onClose}
    >
      <div
        className="relative bg-white rounded-2xl shadow-2xl flex flex-col"
        style={{ width: 560, maxHeight: '88vh' }}
        onClick={e => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <h3 className="font-bold text-gray-900 text-base">📝 Notes</h3>
            {jobLabel && <p className="text-xs text-gray-500 mt-0.5">{jobLabel}</p>}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400">{noteDate}</span>
            <button onClick={onClose} className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-400">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ── Compose box ── */}
        <div className="px-5 py-4 border-b border-gray-100 bg-gray-50/60">
          {/* Tag selector */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {ALL_TAGS.map(t => {
              const active = selectedTags.includes(t.key);
              return (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => toggleTag(t.key)}
                  className={`text-[11px] px-2 py-0.5 rounded-full border font-semibold transition-all ${
                    active
                      ? 'ring-2 ring-offset-1'
                      : 'opacity-50 hover:opacity-80'
                  }`}
                  style={{
                    color: t.color, background: t.bg, borderColor: t.border,
                    ...(active && { '--tw-ring-color': t.border } as any),
                  }}
                >
                  {t.label}
                </button>
              );
            })}
          </div>

          {/* Textarea + mention dropdown */}
          <div className="relative">
            <textarea
              ref={textareaRef}
              value={text}
              onChange={handleTextChange}
              placeholder={`Write a note… use @username to mention someone`}
              rows={3}
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white"
            />

            {/* @mention dropdown */}
            {mentionResults.length > 0 && (
              <div className="absolute bottom-full left-0 mb-1 w-56 bg-white border border-gray-200 rounded-xl shadow-xl z-10 overflow-hidden">
                {mentionResults.map(u => (
                  <button
                    key={u.id}
                    type="button"
                    onMouseDown={e => { e.preventDefault(); insertMention(u); }}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-indigo-50 flex items-center gap-2"
                  >
                    <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold flex items-center justify-center flex-shrink-0">
                      {u.full_name[0]?.toUpperCase()}
                    </span>
                    <div>
                      <p className="font-medium text-gray-800">{u.full_name}</p>
                      <p className="text-[10px] text-gray-400">@{u.username}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center justify-between mt-2">
            <p className="text-[11px] text-gray-400">
              {selectedTags.length > 0
                ? `Tags: ${selectedTags.join(', ')}`
                : 'No tags selected'}
              {mentionIds.length > 0 && ` · ${mentionIds.length} mentioned`}
            </p>
            <button
              onClick={handleSubmit}
              disabled={submitting || !text.trim()}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-indigo-600 text-white text-xs font-bold rounded-lg hover:bg-indigo-700 disabled:opacity-40 transition"
            >
              <Send size={12} />
              {submitting ? 'Posting…' : 'Post Note'}
            </button>
          </div>
        </div>

        {/* ── Notes feed ── */}
        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-3">
          {loading && (
            <p className="text-sm text-gray-400 text-center py-6">Loading…</p>
          )}
          {!loading && notes.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-6 italic">
              No notes yet. Be the first to add one.
            </p>
          )}

          {/* Unresolved section */}
          {unresolved.length > 0 && (
            <div>
              <p className="text-[10px] font-bold text-red-500 uppercase tracking-wider mb-2">
                🔥 Open Issues ({unresolved.length})
              </p>
              <div className="space-y-2.5">
                {unresolved.map(n => (
                  <NoteCard
                    key={n.id}
                    note={n}
                    isMentioned={mentionedMe(n)}
                    currentUserId={currentUserId}
                    resolvingId={resolvingId}
                    resolveText={resolveText}
                    resolveLoading={resolveLoading}
                    onStartResolve={() => { setResolvingId(n.id); setResolveText(''); }}
                    onCancelResolve={() => setResolvingId(null)}
                    onResolveTextChange={setResolveText}
                    onConfirmResolve={() => handleResolve(n.id)}
                    onUnresolve={() => handleUnresolve(n.id)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Resolved section */}
          {resolved.length > 0 && (
            <div>
              <p className="text-[10px] font-bold text-green-600 uppercase tracking-wider mb-2 mt-4">
                ✅ Resolved ({resolved.length})
              </p>
              <div className="space-y-2.5">
                {resolved.map(n => (
                  <NoteCard
                    key={n.id}
                    note={n}
                    isMentioned={mentionedMe(n)}
                    currentUserId={currentUserId}
                    resolvingId={resolvingId}
                    resolveText={resolveText}
                    resolveLoading={resolveLoading}
                    onStartResolve={() => {}}
                    onCancelResolve={() => setResolvingId(null)}
                    onResolveTextChange={setResolveText}
                    onConfirmResolve={() => handleResolve(n.id)}
                    onUnresolve={() => handleUnresolve(n.id)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

// ── NoteCard ──────────────────────────────────────────────────────────────────

interface NoteCardProps {
  note: JobNote;
  isMentioned: boolean;
  currentUserId: number;
  resolvingId: number | null;
  resolveText: string;
  resolveLoading: boolean;
  onStartResolve:       () => void;
  onCancelResolve:      () => void;
  onResolveTextChange:  (v: string) => void;
  onConfirmResolve:     () => void;
  onUnresolve:          () => void;
}

const NoteCard: React.FC<NoteCardProps> = ({
  note, isMentioned, currentUserId,
  resolvingId, resolveText, resolveLoading,
  onStartResolve, onCancelResolve, onResolveTextChange,
  onConfirmResolve, onUnresolve,
}) => {
  const isResolvingThis = resolvingId === note.id;

  return (
    <div
      className={`rounded-xl border overflow-hidden transition-all ${
        note.is_resolved
          ? 'border-green-200 bg-green-50/40 opacity-75'
          : isMentioned
          ? 'border-blue-300 bg-blue-50/50 ring-1 ring-blue-200'
          : 'border-gray-200 bg-white'
      }`}
    >
      {/* @mention highlight banner */}
      {isMentioned && !note.is_resolved && (
        <div className="px-3 py-1 bg-blue-500 text-white text-[10px] font-bold">
          👋 You were mentioned
        </div>
      )}

      <div className="px-4 py-3">
        {/* Author row */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold flex items-center justify-center">
              {note.author?.full_name?.[0]?.toUpperCase() ?? '?'}
            </span>
            <span className="text-xs font-semibold text-gray-800">
              {note.author?.full_name ?? 'Unknown'}
            </span>
            <span className="text-[10px] text-gray-400">{timeAgo(note.created_at)}</span>
          </div>
          {note.is_resolved ? (
            <button
              onClick={onUnresolve}
              className="flex items-center gap-1 text-[10px] text-gray-400 hover:text-orange-500 transition"
            >
              <RotateCcw size={10} /> Reopen
            </button>
          ) : (
            <button
              onClick={onStartResolve}
              className="flex items-center gap-1 text-[10px] text-emerald-600 hover:text-emerald-700 font-semibold transition"
            >
              <CheckCircle size={11} /> Mark resolved
            </button>
          )}
        </div>

        {/* Tags */}
        {note.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {note.tags.map(t => <TagChip key={t} tagKey={t} small />)}
          </div>
        )}

        {/* Note text with @mention highlights */}
        <p className="text-sm text-gray-700 leading-relaxed">
          {renderTextWithMentions(
            note.text,
            note.mentions.map(m => m.id),
            currentUserId
          )}
        </p>

        {/* Resolve inline form */}
        {isResolvingThis && (
          <div className="mt-3 border-t border-gray-100 pt-3">
            <p className="text-xs font-semibold text-gray-600 mb-1">
              How was this resolved?
            </p>
            <textarea
              value={resolveText}
              onChange={e => onResolveTextChange(e.target.value)}
              placeholder="Describe what was done to fix this…"
              rows={2}
              className="w-full border border-gray-200 rounded-lg px-2.5 py-2 text-xs resize-none focus:outline-none focus:ring-2 focus:ring-emerald-300"
              autoFocus
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={onCancelResolve}
                className="flex-1 py-1.5 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={onConfirmResolve}
                disabled={resolveLoading || !resolveText.trim()}
                className="flex-1 py-1.5 rounded-lg text-xs font-bold bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-40 transition"
              >
                {resolveLoading ? 'Saving…' : '✅ Confirm Resolved'}
              </button>
            </div>
          </div>
        )}

        {/* Resolution info (if resolved) */}
        {note.is_resolved && note.resolution_note && (
          <div className="mt-2 px-3 py-2 bg-green-100 rounded-lg">
            <p className="text-[10px] font-bold text-green-700 mb-0.5">
              ✅ Resolved by {note.resolved_by?.full_name ?? 'someone'}
              {note.resolved_at && ` · ${timeAgo(note.resolved_at)}`}
            </p>
            <p className="text-xs text-green-800 italic">"{note.resolution_note}"</p>
          </div>
        )}
      </div>
    </div>
  );
};