export interface ImageTestRequest {
  prompt: string;
  width?: number | null;
  height?: number | null;
  seed?: number | null;
}

export interface ImageTestResponse {
  message: string;
  provider: string;
  file_path: string;
  media_url: string;
  generation_time_sec?: number | null;
  width: number;
  height: number;
  seed?: number | null;
}

export interface ImageProviderInfo {
  provider: string;
  default_width: number;
  default_height: number;
  comfyui_base_url?: string | null;
}
