import { Component, OnInit } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

import { ProjectApiService } from '../../core/services/project-api.service';
import { PHASE_LABELS, ProjectSummary } from '../../core/models/project.models';

@Component({
  selector: 'app-project-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="max-w-5xl mx-auto px-6 py-10">
      <header class="mb-10">
        <h1 class="text-3xl font-bold text-white tracking-tight">
          History Channel Generator
        </h1>
        <p class="mt-2 text-documentary-muted">
          Automate faceless historical documentary videos from topic to final render.
        </p>
      </header>

      <section class="bg-documentary-card border border-documentary-border rounded-xl p-6 mb-10">
        <h2 class="text-lg font-semibold text-amber-400 mb-4">New Project</h2>
        <form (ngSubmit)="createProject()" class="space-y-4">
          <div>
            <label class="block text-sm text-slate-300 mb-1">Historical Topic</label>
            <input
              [(ngModel)]="topic"
              name="topic"
              required
              placeholder="e.g. The Fall of Constantinople 1453"
              class="w-full bg-documentary-bg border border-documentary-border rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
          </div>
          <label class="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              [(ngModel)]="isTestMode"
              name="testMode"
              class="w-4 h-4 rounded accent-amber-500"
            />
            <span class="text-sm text-slate-300">
              Enable Test Mode (2-Min Video) — 300 words, 3 images, 720p
            </span>
          </label>
          <button
            type="submit"
            [disabled]="creating || !topic.trim()"
            class="px-5 py-2.5 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-black font-semibold rounded-lg transition"
          >
            {{ creating ? 'Creating...' : 'Create Project' }}
          </button>
          @if (error) {
            <p class="text-red-400 text-sm">{{ error }}</p>
          }
        </form>
      </section>

      <section>
        <h2 class="text-lg font-semibold text-white mb-4">Your Projects</h2>
        @if (loading) {
          <p class="text-documentary-muted">Loading projects...</p>
        } @else if (projects.length === 0) {
          <p class="text-documentary-muted">No projects yet. Create one above.</p>
        } @else {
          <div class="space-y-3">
            @for (project of projects; track project.id) {
              <a
                [routerLink]="['/projects', project.id]"
                class="block bg-documentary-card border border-documentary-border rounded-xl p-5 hover:border-amber-500/40 transition"
              >
                <div class="flex justify-between items-start">
                  <div>
                    <h3 class="font-medium text-white">{{ project.topic }}</h3>
                    <p class="text-sm text-documentary-muted mt-1">
                      {{ phaseLabels[project.status] }}
                      @if (project.is_test_mode) {
                        <span class="ml-2 text-amber-400">Test Mode</span>
                      }
                    </p>
                  </div>
                  <span class="text-xs text-slate-500">
                    {{ project.created_at | date: 'mediumDate' }}
                  </span>
                </div>
              </a>
            }
          </div>
        }
      </section>
    </div>
  `,
})
export class ProjectDashboardComponent implements OnInit {
  topic = '';
  isTestMode = false;
  creating = false;
  loading = true;
  error = '';
  projects: ProjectSummary[] = [];
  phaseLabels = PHASE_LABELS;

  constructor(
    private api: ProjectApiService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadProjects();
  }

  loadProjects(): void {
    this.loading = true;
    this.api.listProjects().subscribe({
      next: (data) => {
        this.projects = data;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.error = 'Failed to load projects. Is the backend running?';
      },
    });
  }

  createProject(): void {
    if (!this.topic.trim()) return;
    this.creating = true;
    this.error = '';
    this.api.createProject(this.topic.trim(), this.isTestMode).subscribe({
      next: (project) => {
        this.creating = false;
        this.router.navigate(['/projects', project.id]);
      },
      error: (err) => {
        this.creating = false;
        this.error = err.error?.detail || 'Failed to create project';
      },
    });
  }
}
