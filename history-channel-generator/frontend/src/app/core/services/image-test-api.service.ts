import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  ImageProviderInfo,
  ImageTestRequest,
  ImageTestResponse,
} from '../models/image-test.models';

@Injectable({ providedIn: 'root' })
export class ImageTestApiService {
  private readonly base = '/api/v1/images';

  constructor(private http: HttpClient) {}

  getProviderInfo(): Observable<ImageProviderInfo> {
    return this.http.get<ImageProviderInfo>(`${this.base}/provider`);
  }

  generateTestImage(payload: ImageTestRequest): Observable<ImageTestResponse> {
    return this.http.post<ImageTestResponse>(`${this.base}/test`, payload);
  }
}
