import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription, switchMap, timer } from 'rxjs';

import { ProjectApiService } from '../../core/services/project-api.service';
import { ProjectDetail, VideoVersion } from '../../core/models/project.models';
import { PipelineWarningsComponent } from './pipeline-warnings.component';

interface RenderHistoryItem extends VideoVersion {
  isLatest: boolean;
  displayIndex: number; // 1 = newest, growing
}

@Component({
  selector: 'app-video-phase',
  standalone: true,
  imports: [CommonModule, PipelineWarningsComponent],
  template: `
    <div class="space-y-6">
      <app-pipeline-warnings [project]="project" />

      <p class="text-documentary-muted text-sm">
        Assemble a cinematic cut with eased Ken Burns camera moves, jump-cut pacing,
        film-grain overlays, and synced sound design. Every completed render is stored
        in the database — the latest sits at the top, all prior renders below so you can
        compare how the pipeline is improving.
      </p>

      @if (!canGenerate) {
        <div class="bg-documentary-bg border border-documentary-border rounded-lg p-4 text-sm text-documentary-muted">
          @if (project.audio_stale) {
            Script changed — regenerate audio first, then come back here.
          } @else if (!hasVisibleAudio) {
            Audio is missing — open the Audio step and generate narration first.
          } @else if (!hasVisibleImages) {
            Images are missing — open the Images step and generate scene images first.
          } @else {
            Waiting for project assets…
          }
        </div>
      }

      <button
        (click)="generate()"
        [disabled]="generating || !canGenerate"
        class="px-5 py-2.5 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed text-black font-semibold rounded-lg text-sm transition"
      >
        {{ buttonLabel }}
      </button>

      @if (generating || renderStatus) {
        <div class="bg-documentary-bg border border-amber-500/30 rounded-lg p-4 text-sm">
          <p class="text-amber-400 font-medium mb-1">Render status</p>
          <p class="text-slate-300">{{ renderStatus || 'Starting…' }}</p>
        </div>
      }

      @if (renderHistory.length) {
        <section class="space-y-3">
          <header class="flex items-baseline justify-between gap-3">
            <h3 class="text-sm font-semibold text-white">
              Render History ({{ renderHistory.length }})
            </h3>
            <span class="text-xs text-documentary-muted">Newest first · Times shown in EST</span>
          </header>

          <div class="space-y-4">
            @for (item of renderHistory; track trackItem($index, item)) {
              <article
                class="rounded-lg p-4 border transition-colors"
                [ngClass]="{
                  'border-amber-500 bg-amber-500/5': item.isLatest,
                  'border-documentary-border bg-documentary-bg': !item.isLatest
                }"
              >
                <div class="flex flex-wrap items-baseline justify-between gap-2 mb-2">
                  <div class="flex items-center gap-2">
                    <h4 class="text-sm font-semibold text-white">{{ item.label }}</h4>
                    @if (item.isLatest) {
                      <span class="px-2 py-0.5 rounded text-[10px] uppercase tracking-wider bg-amber-500 text-black font-bold">
                        Latest
                      </span>
                    }
                  </div>
                  <span class="text-xs text-documentary-muted">
                    {{ formatVersionDate(item.created_at) }}
                  </span>
                </div>

                @if (versionUrl(item.path); as vUrl) {
                  <video
                    [src]="vUrl"
                    controls
                    preload="metadata"
                    class="w-full max-w-3xl rounded-lg bg-black"
                  ></video>
                  <div class="mt-3 flex flex-wrap gap-3">
                    <button
                      type="button"
                      (click)="downloadVersion(item)"
                      class="px-3 py-1.5 border border-amber-500/60 hover:bg-amber-500/10 text-amber-300 rounded-lg text-sm transition"
                    >
                      Download {{ item.label }}
                    </button>
                    <a
                      [href]="vUrl"
                      target="_blank"
                      rel="noopener"
                      class="px-3 py-1.5 text-amber-400 hover:text-amber-300 rounded-lg text-sm transition"
                    >
                      Open in new tab
                    </a>
                  </div>
                } @else {
                  <p class="text-xs text-red-400">
                    File missing on disk: {{ item.path }}
                  </p>
                }
              </article>
            }
          </div>
        </section>
      } @else if (!generating) {
        <p class="text-documentary-muted text-sm">
          No renders yet — click <span class="text-amber-300">Generate Video</span> above to build the first cut.
        </p>
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
export class VideoPhaseComponent implements OnChanges, OnDestroy {
  @Input() project!: ProjectDetail;
  @Output() projectUpdated = new EventEmitter<void>();

  generating = false;
  error = '';
  success = '';
  renderStatus = '';
  private pollSub: Subscription | null = null;
  private dateFormatter = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
    timeZoneName: 'short',
  });

  constructor(private api: ProjectApiService) {}

  get canGenerate(): boolean {
    if (this.project.can_generate_video === true) return true;
    if (this.project.audio_stale === true) return false;
    if (
      this.project.can_generate_video === false &&
      this.hasVisibleAudio &&
      this.hasVisibleImages
    ) {
      return true;
    }
    if (this.project.can_generate_video === false) return false;
    return this.hasVisibleAudio && this.hasVisibleImages;
  }

  get hasVisibleAudio(): boolean {
    return !!(this.project.audio_path && this.project.whisper_timestamps);
  }

  get hasVisibleImages(): boolean {
    const scenes = this.project.scenes || [];
    if (!scenes.length) return false;
    return scenes.every(
      (s) => !!(s.selected_image_id || (s.images && s.images.length > 0))
    );
  }

  get buttonLabel(): string {
    if (this.generating) return 'Rendering Video…';
    if (this.project.video_path || this.project.status === 'video_ready') {
      return 'Regenerate Video';
    }
    return 'Generate Video';
  }

  /**
   * Single source of truth for what the UI displays: every render, newest first,
   * with the current `video_path` flagged as the latest.
   *
   * Handles three DB states:
   *   1. `video_versions` populated (normal)           → use as-is
   *   2. Legacy: `video_path` set, `video_versions` empty → synthetic Render 1 entry
   *   3. No renders at all                             → empty list
   */
  get renderHistory(): RenderHistoryItem[] {
    const raw: VideoVersion[] = [...(this.project.video_versions || [])].filter(
      (v) => !!v?.path
    );

    // Legacy fallback: video_path exists but no history rows yet
    const currentPath = this.normalizePath(this.project.video_path);
    if (currentPath && !raw.some((v) => this.normalizePath(v.path) === currentPath)) {
      raw.push({
        path: this.project.video_path!,
        label: raw.length
          ? `Render ${raw.length + 1}`
          : 'Render 1',
        created_at: this.project.updated_at || new Date().toISOString(),
      });
    }

    if (!raw.length) return [];

    // Newest last in DB order → reverse to newest first for UI
    const reversed = [...raw].reverse();
    const latestPath = currentPath || this.normalizePath(reversed[0].path);
    return reversed.map((v, i) => ({
      ...v,
      isLatest: this.normalizePath(v.path) === latestPath,
      displayIndex: i + 1,
    }));
  }

  trackItem(index: number, item: RenderHistoryItem): string {
    return `${item.path}-${item.created_at}-${index}`;
  }

  versionUrl(path: string): string | null {
    const url = this.api.mediaUrl(path);
    if (!url) return null;
    // Cache-bust so the browser doesn't serve a stale copy when a filename is reused
    const bust = encodeURIComponent(path);
    return `${url}?v=${bust}`;
  }

  /** Formats a UTC-ISO timestamp in Eastern Time (America/New_York). */
  formatVersionDate(iso: string): string {
    if (!iso) return 'Unknown time';
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return iso;
      return this.dateFormatter.format(d);
    } catch {
      return iso;
    }
  }

  downloadVersion(ver: VideoVersion): void {
    const url = this.versionUrl(ver.path);
    if (!url) return;
    const a = document.createElement('a');
    a.href = url;
    a.download = this.versionFilename(ver);
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  versionFilename(ver: VideoVersion): string {
    const base = ver.path.replace(/\\/g, '/').split('/').pop() || 'render.mp4';
    return base;
  }

  ngOnChanges(): void {
    if (!this.generating && this.project.render_status) {
      this.renderStatus = this.project.render_status;
    }
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  generate(): void {
    if (!this.canGenerate) return;
    this.generating = true;
    this.error = '';
    this.success = '';
    this.renderStatus = 'Starting video render…';
    this.startPolling();

    this.api.generateVideo(this.project.id).subscribe({
      next: (msg) => {
        this.stopPolling();
        this.generating = false;
        this.success = msg.message;
        this.renderStatus = 'Complete';
        // Parent re-fetches from DB → full video_versions history reappears
        this.projectUpdated.emit();
      },
      error: (err) => {
        this.stopPolling();
        this.generating = false;
        this.error = err.error?.detail || 'Video generation failed';
        this.renderStatus = this.error;
        this.projectUpdated.emit();
      },
    });
  }

  private normalizePath(path: string | null | undefined): string {
    return (path || '').replace(/\\/g, '/').toLowerCase();
  }

  private startPolling(): void {
    this.stopPolling();
    this.pollSub = timer(0, 1500)
      .pipe(switchMap(() => this.api.getProject(this.project.id)))
      .subscribe({
        next: (detail) => {
          if (detail.render_status) {
            this.renderStatus = detail.render_status;
          }
          // Live-refresh so the archived version pops in as soon as the DB is written
          if (detail.video_versions !== undefined) {
            this.project = {
              ...this.project,
              video_versions: detail.video_versions,
              video_path: detail.video_path,
              render_status: detail.render_status,
              updated_at: detail.updated_at,
            };
          }
        },
      });
  }

  private stopPolling(): void {
    if (this.pollSub) {
      this.pollSub.unsubscribe();
      this.pollSub = null;
    }
  }
}
