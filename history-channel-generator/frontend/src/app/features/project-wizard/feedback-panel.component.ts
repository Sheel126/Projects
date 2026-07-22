import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

import { ProjectApiService } from '../../core/services/project-api.service';
import { FEEDBACK_STAGES, UserFeedback } from '../../core/models/project.models';

@Component({
  selector: 'app-feedback-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="bg-documentary-bg border border-documentary-border rounded-lg p-4">
      <h3 class="text-sm font-semibold text-amber-400 mb-3">Submit Agent Feedback</h3>
      <form (ngSubmit)="submit()" class="space-y-3">
        <select
          [(ngModel)]="stage"
          name="stage"
          class="w-full bg-documentary-card border border-documentary-border rounded-lg px-3 py-2 text-sm text-white"
        >
          @for (s of stages; track s.value) {
            <option [value]="s.value">{{ s.label }}</option>
          }
        </select>
        <textarea
          [(ngModel)]="feedbackText"
          name="feedback"
          rows="3"
          placeholder="e.g. Make the hook more aggressive, focus on the siege tactics..."
          class="w-full bg-documentary-card border border-documentary-border rounded-lg px-3 py-2 text-sm text-white resize-none"
        ></textarea>
        <button
          type="submit"
          [disabled]="submitting || !feedbackText.trim()"
          class="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white text-sm rounded-lg transition"
        >
          {{ submitting ? 'Saving...' : 'Save Feedback' }}
        </button>
        @if (message) {
          <p class="text-green-400 text-xs">{{ message }}</p>
        }
        @if (error) {
          <p class="text-red-400 text-xs">{{ error }}</p>
        }
      </form>

      @if (feedback.length > 0) {
        <div class="mt-4 pt-4 border-t border-documentary-border">
          <h4 class="text-xs text-documentary-muted mb-2">Previous Feedback</h4>
          <ul class="space-y-2 max-h-40 overflow-y-auto">
            @for (item of feedback; track item.id) {
              <li class="text-xs text-slate-400">
                <span class="text-amber-500">[{{ item.stage }}]</span>
                {{ item.feedback_text }}
              </li>
            }
          </ul>
        </div>
      }
    </div>
  `,
})
export class FeedbackPanelComponent {
  @Input() projectId!: number;
  @Input() feedback: UserFeedback[] = [];
  @Output() feedbackSubmitted = new EventEmitter<void>();

  stages = FEEDBACK_STAGES;
  stage = 'scripting';
  feedbackText = '';
  submitting = false;
  message = '';
  error = '';

  constructor(private api: ProjectApiService) {}

  submit(): void {
    if (!this.feedbackText.trim()) return;
    this.submitting = true;
    this.message = '';
    this.error = '';
    this.api
      .submitFeedback(this.projectId, this.stage, this.feedbackText.trim())
      .subscribe({
        next: () => {
          this.submitting = false;
          this.feedbackText = '';
          this.message = 'Feedback saved. Regenerate script to apply.';
          this.feedbackSubmitted.emit();
        },
        error: (err) => {
          this.submitting = false;
          this.error = err.error?.detail || 'Failed to save feedback';
        },
      });
  }
}
