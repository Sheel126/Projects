import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  PipelineMessage,
  ProjectDetail,
  ProjectSummary,
  ScriptGenerationResult,
  UserFeedback,
} from '../models/project.models';

@Injectable({ providedIn: 'root' })
export class ProjectApiService {
  private readonly base = '/api/v1/projects';

  constructor(private http: HttpClient) {}

  listProjects(): Observable<ProjectSummary[]> {
    return this.http.get<ProjectSummary[]>(this.base);
  }

  createProject(topic: string, isTestMode: boolean): Observable<ProjectSummary> {
    return this.http.post<ProjectSummary>(this.base, {
      topic,
      is_test_mode: isTestMode,
    });
  }

  getProject(id: number): Observable<ProjectDetail> {
    return this.http.get<ProjectDetail>(`${this.base}/${id}`);
  }

  generateScript(id: number): Observable<ScriptGenerationResult> {
    return this.http.post<ScriptGenerationResult>(
      `${this.base}/${id}/generate-script`,
      {}
    );
  }

  updateScript(id: number, scriptText: string): Observable<ProjectDetail> {
    return this.http.put<ProjectDetail>(`${this.base}/${id}/script`, {
      script_text: scriptText,
    });
  }

  submitFeedback(
    id: number,
    stage: string,
    feedbackText: string
  ): Observable<UserFeedback> {
    return this.http.post<UserFeedback>(`${this.base}/${id}/feedback`, {
      stage,
      feedback_text: feedbackText,
    });
  }

  getFeedback(id: number): Observable<UserFeedback[]> {
    return this.http.get<UserFeedback[]>(`${this.base}/${id}/feedback`);
  }

  generateAudio(id: number): Observable<PipelineMessage> {
    return this.http.post<PipelineMessage>(
      `${this.base}/${id}/generate-audio`,
      {}
    );
  }

  generateImages(id: number): Observable<PipelineMessage> {
    return this.http.post<PipelineMessage>(
      `${this.base}/${id}/generate-images`,
      {}
    );
  }

  selectImage(
    projectId: number,
    sceneId: number,
    imageId: number
  ): Observable<ProjectDetail> {
    return this.http.patch<ProjectDetail>(
      `${this.base}/${projectId}/scenes/${sceneId}/select-image`,
      { image_id: imageId }
    );
  }

  generateVideo(id: number): Observable<PipelineMessage> {
    return this.http.post<PipelineMessage>(
      `${this.base}/${id}/generate-video`,
      {}
    );
  }

  mediaUrl(filePath: string | null): string | null {
    if (!filePath) return null;
    const normalized = filePath.replace(/\\/g, '/');
    const match = normalized.match(/output\/(\d+)\/(.+)$/);
    if (match) {
      return `/media/${match[1]}/${match[2]}`;
    }
    return null;
  }
}
