import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ProjectDetail } from '../../core/models/project.models';

@Component({
  selector: 'app-pipeline-warnings',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (project.pipeline_warnings?.length) {
      <div class="space-y-2 mb-4">
        @for (w of project.pipeline_warnings; track w) {
          <div class="text-sm rounded-lg px-3 py-2 border" [ngClass]="bannerClass(w)">
            {{ w }}
          </div>
        }
      </div>
    }
  `,
})
export class PipelineWarningsComponent {
  @Input({ required: true }) project!: ProjectDetail;

  bannerClass(w: string): Record<string, boolean> {
    const required = w.includes('required');
    return {
      'bg-red-500/10': required,
      'border-red-500/30': required,
      'text-red-300': required,
      'bg-amber-500/10': !required,
      'border-amber-500/30': !required,
      'text-amber-300': !required,
    };
  }
}
