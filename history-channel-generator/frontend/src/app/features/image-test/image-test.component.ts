import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ImageTestApiService } from '../../core/services/image-test-api.service';
import {
  ImageProviderInfo,
  ImageTestResponse,
} from '../../core/models/image-test.models';

@Component({
  selector: 'app-image-test',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="max-w-4xl mx-auto px-6 py-10">
      <header class="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 class="text-3xl font-bold text-white tracking-tight">Image Test</h1>
          <p class="mt-2 text-documentary-muted">
            Try a prompt with your local ComfyUI setup before generating a full
            project batch.
          </p>
        </div>
        <a
          routerLink="/"
          class="text-sm text-amber-400 hover:text-amber-300 transition shrink-0"
        >
          ← Back to Projects
        </a>
      </header>

      @if (providerInfo) {
        <p class="text-xs text-slate-500 mb-6">
          Provider: <span class="text-slate-300">{{ providerInfo.provider }}</span>
          · Defaults: {{ providerInfo.default_width }}×{{ providerInfo.default_height }}
          @if (providerInfo.comfyui_base_url) {
            · ComfyUI: {{ providerInfo.comfyui_base_url }}
          }
        </p>
      }

      <section class="bg-documentary-card border border-documentary-border rounded-xl p-6 mb-8">
        <form (ngSubmit)="generate()" class="space-y-4">
          <div>
            <label class="block text-sm text-slate-300 mb-1">Prompt</label>
            <textarea
              [(ngModel)]="prompt"
              name="prompt"
              required
              rows="4"
              placeholder="cinematic historical documentary still, dramatic lighting, photorealistic..."
              class="w-full bg-documentary-bg border border-documentary-border rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            ></textarea>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label class="block text-sm text-slate-300 mb-1">Width (optional)</label>
              <input
                type="number"
                [(ngModel)]="width"
                name="width"
                min="256"
                max="2048"
                placeholder="1280"
                class="w-full bg-documentary-bg border border-documentary-border rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              />
            </div>
            <div>
              <label class="block text-sm text-slate-300 mb-1">Height (optional)</label>
              <input
                type="number"
                [(ngModel)]="height"
                name="height"
                min="256"
                max="2048"
                placeholder="720"
                class="w-full bg-documentary-bg border border-documentary-border rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              />
            </div>
            <div>
              <label class="block text-sm text-slate-300 mb-1">Seed (optional)</label>
              <input
                type="number"
                [(ngModel)]="seed"
                name="seed"
                min="0"
                placeholder="random"
                class="w-full bg-documentary-bg border border-documentary-border rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              />
            </div>
          </div>

          <button
            type="submit"
            [disabled]="generating || !prompt.trim()"
            class="px-5 py-2.5 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-black font-semibold rounded-lg transition"
          >
            {{ generating ? 'Generating Test Image…' : 'Generate Test Image' }}
          </button>
        </form>

        @if (statusMessage) {
          <p class="mt-4 text-sm text-documentary-muted">{{ statusMessage }}</p>
        }
        @if (error) {
          <p class="mt-4 text-red-400 text-sm">{{ error }}</p>
        }
      </section>

      @if (result) {
        <section class="bg-documentary-card border border-documentary-border rounded-xl p-6">
          <h2 class="text-lg font-semibold text-amber-400 mb-4">Preview</h2>
          <img
            [src]="result.media_url"
            alt="Generated test image"
            class="w-full max-w-3xl rounded-lg border border-documentary-border"
          />
          <dl class="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-slate-300">
            <div>
              <dt class="text-documentary-muted">Provider</dt>
              <dd>{{ result.provider }}</dd>
            </div>
            <div>
              <dt class="text-documentary-muted">Dimensions</dt>
              <dd>{{ result.width }}×{{ result.height }}</dd>
            </div>
            @if (result.generation_time_sec != null) {
              <div>
                <dt class="text-documentary-muted">Generation time</dt>
                <dd>{{ result.generation_time_sec | number: '1.1-1' }}s</dd>
              </div>
            }
            @if (result.seed != null) {
              <div>
                <dt class="text-documentary-muted">Seed</dt>
                <dd>{{ result.seed }}</dd>
              </div>
            }
            <div class="sm:col-span-2">
              <dt class="text-documentary-muted">Saved to</dt>
              <dd class="break-all text-xs text-slate-400">{{ result.file_path }}</dd>
            </div>
          </dl>
        </section>
      }
    </div>
  `,
})
export class ImageTestComponent implements OnInit {
  prompt = '';
  width: number | null = null;
  height: number | null = null;
  seed: number | null = null;

  generating = false;
  statusMessage = '';
  error = '';
  result: ImageTestResponse | null = null;
  providerInfo: ImageProviderInfo | null = null;

  constructor(private api: ImageTestApiService) {}

  ngOnInit(): void {
    this.api.getProviderInfo().subscribe({
      next: (info) => {
        this.providerInfo = info;
      },
      error: () => {
        this.error = 'Could not load image provider info. Is the backend running?';
      },
    });
  }

  generate(): void {
    if (!this.prompt.trim()) return;

    this.generating = true;
    this.error = '';
    this.statusMessage = 'Submitting prompt to local image provider…';
    this.result = null;

    this.api
      .generateTestImage({
        prompt: this.prompt.trim(),
        width: this.width || null,
        height: this.height || null,
        seed: this.seed ?? null,
      })
      .subscribe({
        next: (response) => {
          this.generating = false;
          this.statusMessage = response.message;
          this.result = response;
        },
        error: (err) => {
          this.generating = false;
          this.statusMessage = '';
          this.error =
            err.error?.detail ||
            'Test image generation failed. Is ComfyUI running on port 8188?';
        },
      });
  }
}
