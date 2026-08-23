import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { ImageTestComponent } from './image-test.component';
import { ImageTestApiService } from '../../core/services/image-test-api.service';

describe('ImageTestComponent', () => {
  let component: ImageTestComponent;
  let fixture: ComponentFixture<ImageTestComponent>;
  let api: jasmine.SpyObj<ImageTestApiService>;

  beforeEach(async () => {
    api = jasmine.createSpyObj('ImageTestApiService', [
      'getProviderInfo',
      'generateTestImage',
    ]);
    api.getProviderInfo.and.returnValue(
      of({
        provider: 'comfyui',
        default_width: 1280,
        default_height: 720,
        comfyui_base_url: 'http://127.0.0.1:8188',
      })
    );

    await TestBed.configureTestingModule({
      imports: [ImageTestComponent],
      providers: [
        provideRouter([]),
        { provide: ImageTestApiService, useValue: api },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ImageTestComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('loads provider info on init', () => {
    expect(api.getProviderInfo).toHaveBeenCalled();
    expect(component.providerInfo?.provider).toBe('comfyui');
  });

  it('shows error when generation fails', () => {
    api.generateTestImage.and.returnValue(
      throwError(() => ({ error: { detail: 'ComfyUI unavailable' } }))
    );
    component.prompt = 'test prompt';
    component.generate();
    expect(component.error).toContain('ComfyUI unavailable');
    expect(component.generating).toBeFalse();
  });

  it('renders preview on success', () => {
    api.generateTestImage.and.returnValue(
      of({
        message: 'ok',
        provider: 'comfyui',
        file_path: '/tmp/test.png',
        media_url: '/media/test_images/test.png',
        generation_time_sec: 10,
        width: 1280,
        height: 720,
        seed: 1,
      })
    );
    component.prompt = 'test prompt';
    component.generate();
    expect(component.result?.media_url).toBe('/media/test_images/test.png');
    expect(component.generating).toBeFalse();
  });
});
