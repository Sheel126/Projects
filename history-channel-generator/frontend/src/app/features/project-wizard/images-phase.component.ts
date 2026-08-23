import { Component, EventEmitter, Input, OnChanges, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ProjectApiService } from '../../core/services/project-api.service';
import { ProjectDetail, Scene } from '../../core/models/project.models';
import { PipelineWarningsComponent } from './pipeline-warnings.component';

@Component({
  selector: 'app-images-phase',
  standalone: true,
  imports: [CommonModule, RouterLink, PipelineWarningsComponent],
  template: `
    <div class="space-y-6">
      <app-pipeline-warnings [project]="project" />

      <p class="text-documentary-muted text-sm">
        Generate one cinematic image per scene via your configured local image provider
        (ComfyUI by default). Test Mode uses 3 scenes; production uses 12.
        Thumbnail reuses the first scene. Use <a routerLink="/image-test" class="text-amber-400 hover:text-amber-300">Image Test</a> to preview prompts first.
      </p>

      <button
        (click)="generate()"
        [disabled]="generating || !project.can_generate_images"
        class="px-5 py-2.5 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-black font-semibold rounded-lg text-sm transition"
      >
        {{ buttonLabel }}
      </button>

      @if (thumbnailUrl) {
        <div>
          <h3 class="text-sm font-semibold text-amber-400 mb-2">Thumbnail (scene 1)</h3>
          <img [src]="thumbnailUrl" alt="Thumbnail" class="rounded-lg max-w-md border border-documentary-border" />
        </div>
      }

      @for (scene of scenes; track scene.id) {
        <div class="bg-documentary-bg border border-documentary-border rounded-lg p-4">
          <h3 class="text-sm font-semibold text-white mb-1">
            Scene {{ scene.scene_order + 1 }}
          </h3>
          <p class="text-xs text-documentary-muted mb-3 line-clamp-2">{{ scene.narrative_excerpt }}</p>
          @if (primaryImage(scene); as img) {
            @if (imageUrl(img.file_path); as url) {
              <img [src]="url" alt="Scene {{ scene.scene_order + 1 }}" class="w-full max-w-lg aspect-video object-cover rounded-lg border border-documentary-border" />
            }
          } @else {
            <p class="text-xs text-slate-500">No image yet.</p>
          }
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
export class ImagesPhaseComponent implements OnChanges {
  @Input() project!: ProjectDetail;
  @Output() projectUpdated = new EventEmitter<void>();

  generating = false;
  error = '';
  success = '';
  scenes: Scene[] = [];
  thumbnailUrl: string | null = null;

  constructor(private api: ProjectApiService) {}

  get buttonLabel(): string {
    if (this.generating) return 'Generating Images (this may take a while)...';
    if (this.project.images_stale) return 'Regenerate Images (recommended)';
    if (this.scenes.length) return 'Regenerate Images';
    return 'Generate Images';
  }

  ngOnChanges(): void {
    this.scenes = this.project.scenes || [];
    this.thumbnailUrl = this.api.mediaUrl(this.project.thumbnail_path);
  }

  imageUrl(path: string): string | null {
    return this.api.mediaUrl(path);
  }

  primaryImage(scene: Scene) {
    if (!scene.images?.length) return null;
    return (
      scene.images.find((img) => img.id === scene.selected_image_id) ||
      scene.images[0]
    );
  }

  generate(): void {
    this.generating = true;
    this.error = '';
    this.success = '';
    this.api.generateImages(this.project.id).subscribe({
      next: (msg) => {
        this.generating = false;
        this.success = msg.message;
        this.projectUpdated.emit();
      },
      error: (err) => {
        this.generating = false;
        this.error = err.error?.detail || 'Image generation failed';
      },
    });
  }
}
