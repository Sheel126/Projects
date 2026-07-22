import { Component, EventEmitter, Input, OnChanges, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

import { ProjectApiService } from '../../core/services/project-api.service';
import { ProjectDetail } from '../../core/models/project.models';
import { FeedbackPanelComponent } from './feedback-panel.component';
import { PipelineWarningsComponent } from './pipeline-warnings.component';

@Component({
  selector: 'app-script-phase',
  standalone: true,
  imports: [CommonModule, FormsModule, FeedbackPanelComponent, PipelineWarningsComponent],
  template: `
    <div class="grid lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2 space-y-4">
        <app-pipeline-warnings [project]="project" />

        <div class="flex gap-3">
          <button
            (click)="generate()"
            [disabled]="generating"
            class="px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-black font-semibold rounded-lg text-sm transition"
          >
            {{ generating ? 'Generating...' : 'Generate Script' }}
          </button>
          <button
            (click)="save()"
            [disabled]="saving || !scriptText.trim()"
            class="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white rounded-lg text-sm transition"
          >
            {{ saving ? 'Saving...' : 'Approve & Save Script' }}
          </button>
        </div>

        @if (editorNotes.length > 0) {
          <div class="text-xs text-amber-400/90 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3">
            <p class="font-medium mb-1">Editor notes (script still generated):</p>
            <ul class="list-disc list-inside space-y-0.5">
              @for (note of editorNotes; track note) {
                <li>{{ note }}</li>
              }
            </ul>
            <p class="mt-2 text-documentary-muted">Completed in {{ iterations }} iteration(s).</p>
          </div>
        }

        <textarea
          [(ngModel)]="scriptText"
          rows="20"
          placeholder="Generated script will appear here..."
          class="w-full bg-documentary-bg border border-documentary-border rounded-lg px-4 py-3 text-sm text-slate-200 font-mono leading-relaxed resize-y"
        ></textarea>

        @if (error) {
          <p class="text-red-400 text-sm">{{ error }}</p>
        }
        @if (success) {
          <p class="text-green-400 text-sm">{{ success }}</p>
        }
      </div>

      <div>
        <app-feedback-panel
          [projectId]="project.id"
          [feedback]="project.feedback"
          (feedbackSubmitted)="onFeedbackSubmitted()"
        />
      </div>
    </div>
  `,
})
export class ScriptPhaseComponent implements OnChanges {
  @Input() project!: ProjectDetail;
  @Output() projectUpdated = new EventEmitter<void>();

  scriptText = '';
  generating = false;
  saving = false;
  error = '';
  success = '';
  editorNotes: string[] = [];
  iterations = 0;

  constructor(private api: ProjectApiService) {}

  ngOnChanges(): void {
    this.scriptText = this.project.script_text || '';
  }

  generate(): void {
    this.generating = true;
    this.error = '';
    this.success = '';
    this.api.generateScript(this.project.id).subscribe({
      next: (result) => {
        this.generating = false;
        this.scriptText = result.script_text;
        this.editorNotes = result.editor_notes;
        this.iterations = result.iterations;
        this.success = result.had_warnings
          ? 'Script generated with editor suggestions. Review and approve when ready.'
          : 'Script generated. Review and approve when ready.';
        this.projectUpdated.emit();
      },
      error: (err) => {
        this.generating = false;
        this.error = err.error?.detail || 'Script generation failed';
      },
    });
  }

  save(): void {
    this.saving = true;
    this.error = '';
    this.success = '';
    this.api.updateScript(this.project.id, this.scriptText).subscribe({
      next: (detail) => {
        this.saving = false;
        if (detail.audio_stale) {
          this.success =
            'Script saved. Audio is stale — regenerate audio (required) before video.';
        } else if (detail.images_stale) {
          this.success =
            'Script saved. Images may be outdated — regenerating images is recommended.';
        } else {
          this.success = 'Script approved. Proceed to Phase 2: Audio.';
        }
        this.projectUpdated.emit();
      },
      error: (err) => {
        this.saving = false;
        this.error = err.error?.detail || 'Failed to save script';
      },
    });
  }

  onFeedbackSubmitted(): void {
    this.projectUpdated.emit();
  }
}
