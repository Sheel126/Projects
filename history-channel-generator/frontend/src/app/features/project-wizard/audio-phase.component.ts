import { Component, EventEmitter, Input, OnChanges, Output } from '@angular/core';
import { CommonModule } from '@angular/common';

import { ProjectApiService } from '../../core/services/project-api.service';
import { ProjectDetail } from '../../core/models/project.models';
import { PipelineWarningsComponent } from './pipeline-warnings.component';

@Component({
  selector: 'app-audio-phase',
  standalone: true,
  imports: [CommonModule, PipelineWarningsComponent],
  template: `
    <div class="space-y-6">
      <app-pipeline-warnings [project]="project" />

      <p class="text-documentary-muted text-sm">
        Generate narrator audio via ElevenLabs (paragraph reuse for small edits) and Whisper timestamps.
      </p>

      <button
        (click)="generate()"
        [disabled]="generating || !project.can_generate_audio"
        class="px-5 py-2.5 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-black font-semibold rounded-lg text-sm transition"
      >
        {{ buttonLabel }}
      </button>

      @if (project.audio_path) {
        <div class="bg-documentary-bg border border-documentary-border rounded-lg p-4">
          <h3 class="text-sm font-semibold text-white mb-2">Narration Preview</h3>
          @if (audioUrl) {
            <audio [src]="audioUrl" controls class="w-full"></audio>
          }
        </div>
      }

      @if (project.whisper_timestamps) {
        <div class="bg-documentary-bg border border-documentary-border rounded-lg p-4">
          <h3 class="text-sm font-semibold text-white mb-2">Timestamp Preview</h3>
          <pre class="text-xs text-slate-400 overflow-auto max-h-48">{{ timestampPreview }}</pre>
        </div>
      }

      @if (error) {
        <p class="text-red-400 text-sm">{{ error }}</p>
      }
      @if (success) {
        <p class="text-green-400 text-sm">{{ success }}</p>
      }
    </div>
  `,
})
export class AudioPhaseComponent implements OnChanges {
  @Input() project!: ProjectDetail;
  @Output() projectUpdated = new EventEmitter<void>();

  generating = false;
  error = '';
  success = '';
  audioUrl: string | null = null;
  timestampPreview = '';

  constructor(private api: ProjectApiService) {}

  get buttonLabel(): string {
    if (this.generating) return 'Generating Audio...';
    if (this.project.audio_stale) return 'Regenerate Audio (required)';
    if (this.project.audio_path) return 'Regenerate Audio';
    return 'Generate Audio & Timestamps';
  }

  ngOnChanges(): void {
    this.audioUrl = this.api.mediaUrl(this.project.audio_path);
    if (this.project.whisper_timestamps) {
      const segments = (this.project.whisper_timestamps as { segments?: unknown[] }).segments;
      this.timestampPreview = JSON.stringify(
        segments?.slice(0, 5) ?? this.project.whisper_timestamps,
        null,
        2
      );
    }
  }

  generate(): void {
    this.generating = true;
    this.error = '';
    this.success = '';
    this.api.generateAudio(this.project.id).subscribe({
      next: (msg) => {
        this.generating = false;
        this.success = msg.message;
        this.projectUpdated.emit();
      },
      error: (err) => {
        this.generating = false;
        this.error = err.error?.detail || 'Audio generation failed';
      },
    });
  }
}
