// components/ProductivityWarningModal.tsx
import React from 'react';
import { ValidationResult } from '../types/types';

interface ProductivityWarningModalProps {
  validation: ValidationResult;
  pendingAllocation: any;
  onClose: () => void;
  onSuggestionSelect: (suggestion: any) => void;
  onForceOverride: () => void;
}

const ProductivityWarningModal: React.FC<ProductivityWarningModalProps> = ({
  validation,
  pendingAllocation,
  onClose,
  onSuggestionSelect,
  onForceOverride
}) => {
  const warning = validation.warnings?.productivity_warning;

  if (!warning) return null;

  const getIcon = (option: string) => {
    switch (option) {
      case 'reduce_area': return '📉';
      case 'add_workers': return '👥';
      case 'update_productivity': return '⚡';
      case 'split_days': return '📅';
      default: return '•';
    }
  };

  const getTitle = (option: string) => {
    switch (option) {
      case 'reduce_area': return 'Reduce Area';
      case 'add_workers': return 'Add More Workers';
      case 'update_productivity': return 'Update Productivity';
      case 'split_days': return 'Split Across Days';
      default: return option;
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content warning-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">⚠️ {warning.message}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {/* Warning Details */}
          <div className="warning-details">
            <h4>Current Situation:</h4>
            <ul>
              <li>Workers: {warning.details.workers}</li>
              <li>Productivity: {warning.details.productivity_per_worker}</li>
              <li>Max Capacity: {warning.details.max_capacity}</li>
              <li>Requested: {warning.details.requested}</li>
              {warning.details.deficit && (
                <li style={{ color: 'var(--danger-color)', fontWeight: 600 }}>
                  Deficit: {warning.details.deficit}
                </li>
              )}
            </ul>
          </div>

          {/* Suggestions */}
          {warning.suggestions && warning.suggestions.length > 0 && (
            <div className="suggestions">
              <h4>Choose an option:</h4>
              
              {warning.suggestions.map((suggestion, index) => (
                <div
                  key={index}
                  className="suggestion-card"
                  onClick={() => onSuggestionSelect(suggestion)}
                >
                  <div className="suggestion-header">
                    <span className="suggestion-icon">{getIcon(suggestion.option)}</span>
                    <h5>{getTitle(suggestion.option)}</h5>
                  </div>

                  <p className="suggestion-description">{suggestion.description}</p>

                  {/* Preview */}
                  <div className="suggestion-preview">
                    {suggestion.option === 'reduce_area' && suggestion.allocation && (
                      <>
                        <div>Area: {suggestion.allocation.area} acres</div>
                        <div style={{ color: 'var(--success-color)' }}>✓ Will complete</div>
                      </>
                    )}
                    {suggestion.option === 'add_workers' && suggestion.allocation && (
                      <>
                        <div>Workers: {suggestion.allocation.workers}</div>
                        <div style={{ color: 'var(--text-secondary)' }}>{suggestion.allocation.note}</div>
                        <div style={{ color: 'var(--success-color)' }}>✓ Will complete</div>
                      </>
                    )}
                    {suggestion.option === 'update_productivity' && suggestion.allocation && (
                      <>
                        <div>New Productivity: {suggestion.allocation.new_productivity} acres/worker/day</div>
                        <div style={{ color: 'var(--success-color)' }}>✓ Will complete</div>
                      </>
                    )}
                    {suggestion.option === 'split_days' && suggestion.allocations && (
                      <>
                        {suggestion.allocations.map((alloc: any, i: number) => (
                          <div key={i}>Day {i + 1}: {alloc.area} acres ({alloc.workers} workers)</div>
                        ))}
                      </>
                    )}
                  </div>

                  <button className="btn-primary" style={{ width: '100%' }}>
                    Use This Option
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Force Override Section */}
          <div className="force-override-section">
            <h5>⚠️ Override Warning (Not Recommended)</h5>
            <p>
              Proceed anyway knowing the team cannot complete this work in one day.
              You will need to track actual completion manually.
            </p>
            <button className="btn-danger" onClick={onForceOverride}>
              Proceed Anyway (Force)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProductivityWarningModal;