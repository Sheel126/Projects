export type ProjectStatus =
  | 'created'
  | 'script_ready'
  | 'audio_ready'
  | 'images_ready'
  | 'video_ready';

export interface ProjectSummary {
  id: number;
  topic: string;
  is_test_mode: boolean;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface GeneratedImage {
  id: number;
  scene_id: number | null;
  variation_index: number;
  file_path: string;
  is_thumbnail: boolean;
}

export interface Scene {
  id: number;
  scene_order: number;
  narrative_excerpt: string;
  image_prompt: string | null;
  start_time: number | null;
  end_time: number | null;
  selected_image_id: number | null;
  images: GeneratedImage[];
}

export interface UserFeedback {
  id: number;
  project_id: number;
  stage: string;
  feedback_text: string;
  created_at: string;
}

export interface VideoVersion {
  path: string;
  label: string;
  created_at: string;
}

export interface ProjectDetail extends ProjectSummary {
  script_text: string | null;
  audio_path: string | null;
  whisper_timestamps: Record<string, unknown> | null;
  thumbnail_path: string | null;
  video_path: string | null;
  video_versions?: VideoVersion[] | null;
  render_status?: string | null;
  script_hash?: string | null;
  audio_script_hash?: string | null;
  images_script_hash?: string | null;
  can_generate_audio?: boolean;
  can_generate_images?: boolean;
  can_generate_video?: boolean;
  audio_stale?: boolean;
  images_stale?: boolean;
  pipeline_warnings?: string[];
  scenes: Scene[];
  feedback: UserFeedback[];
}

export interface ScriptGenerationResult {
  script_text: string;
  iterations: number;
  editor_notes: string[];
  had_warnings?: boolean;
}

export interface PipelineMessage {
  message: string;
  status: ProjectStatus;
  paragraphs_reused?: number | null;
  paragraphs_generated?: number | null;
}

export const PHASE_LABELS: Record<ProjectStatus, string> = {
  created: 'Phase 1: Script',
  script_ready: 'Phase 2: Audio',
  audio_ready: 'Phase 3: Images',
  images_ready: 'Phase 4: Video',
  video_ready: 'Complete',
};

export const FEEDBACK_STAGES = [
  { value: 'hook_creation', label: 'Hook Creation' },
  { value: 'scripting', label: 'Scripting' },
  { value: 'general', label: 'General' },
];
