import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';

import { ProjectApiService } from '../../core/services/project-api.service';
import { PHASE_LABELS, ProjectDetail, ProjectStatus } from '../../core/models/project.models';
import { ScriptPhaseComponent } from './script-phase.component';
import { AudioPhaseComponent } from './audio-phase.component';
import { ImagesPhaseComponent } from './images-phase.component';
import { VideoPhaseComponent } from './video-phase.component';

const STEPS: { key: ProjectStatus | 'script'; label: string }[] = [
  { key: 'script', label: 'Script' },
  { key: 'script_ready', label: 'Audio' },
  { key: 'audio_ready', label: 'Images' },
  { key: 'images_ready', label: 'Video' },
  { key: 'video_ready', label: 'Done' },
];

@Component({
  selector: 'app-project-wizard',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    ScriptPhaseComponent,
    AudioPhaseComponent,
    ImagesPhaseComponent,
    VideoPhaseComponent,
  ],
  template: `
    <div class="max-w-6xl mx-auto px-6 py-10">
      <a routerLink="/" class="text-sm text-documentary-muted hover:text-amber-400 transition">
        &larr; Back to Dashboard
      </a>

      @if (loading) {
        <p class="mt-8 text-documentary-muted">Loading project...</p>
      } @else if (project) {
        <header class="mt-6 mb-8">
          <h1 class="text-2xl font-bold text-white">{{ project.topic }}</h1>
          <p class="text-sm text-documentary-muted mt-1">
            {{ phaseLabels[project.status] }}
            @if (project.is_test_mode) {
              <span class="ml-2 text-amber-400 font-medium">Test Mode</span>
            }
          </p>
        </header>

        <!-- Stepper -->
        <nav class="flex flex-wrap gap-2 mb-8">
          @for (step of steps; track step.key; let i = $index) {
            <button
              (click)="activeStep = i"
              class="px-4 py-2 rounded-lg text-sm font-medium transition border"
              [class.bg-amber-500]="activeStep === i"
              [class.text-black]="activeStep === i"
              [class.border-amber-500]="activeStep === i"
              [class.bg-documentary-card]="activeStep !== i"
              [class.text-slate-300]="activeStep !== i"
              [class.border-documentary-border]="activeStep !== i"
            >
              {{ i + 1 }}. {{ step.label }}
            </button>
          }
        </nav>

        <section class="bg-documentary-card border border-documentary-border rounded-xl p-6">
          @if (activeStep === 0) {
            <app-script-phase [project]="project" (projectUpdated)="reload()" />
          }
          @if (activeStep === 1) {
            <app-audio-phase [project]="project" (projectUpdated)="reload()" />
          }
          @if (activeStep === 2) {
            <app-images-phase [project]="project" (projectUpdated)="reload()" />
          }
          @if (activeStep === 3 || activeStep === 4) {
            <app-video-phase [project]="project" (projectUpdated)="reload()" />
          }
        </section>
      } @else {
        <p class="mt-8 text-red-400">Project not found.</p>
      }
    </div>
  `,
})
export class ProjectWizardComponent implements OnInit {
  project: ProjectDetail | null = null;
  loading = true;
  activeStep = 0;
  steps = STEPS;
  phaseLabels = PHASE_LABELS;

  constructor(
    private route: ActivatedRoute,
    private api: ProjectApiService
  ) {}

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      const id = Number(params.get('id'));
      if (id) this.loadProject(id);
    });
  }

  loadProject(id: number): void {
    this.loading = true;
    this.api.getProject(id).subscribe({
      next: (data) => {
        this.project = data;
        this.loading = false;
        this.syncActiveStep(data.status);
      },
      error: () => {
        this.loading = false;
        this.project = null;
      },
    });
  }

  reload(): void {
    if (this.project) this.loadProject(this.project.id);
  }

  private syncActiveStep(status: ProjectStatus): void {
    const map: Record<ProjectStatus, number> = {
      created: 0,
      script_ready: 1,
      audio_ready: 2,
      images_ready: 3,
      video_ready: 4,
    };
    this.activeStep = map[status] ?? 0;
  }
}
