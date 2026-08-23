import { Routes } from '@angular/router';
import { ProjectDashboardComponent } from './features/project-wizard/project-dashboard.component';
import { ProjectWizardComponent } from './features/project-wizard/project-wizard.component';
import { ImageTestComponent } from './features/image-test/image-test.component';

export const routes: Routes = [
  { path: '', component: ProjectDashboardComponent },
  { path: 'image-test', component: ImageTestComponent },
  { path: 'projects/:id', component: ProjectWizardComponent },
  { path: '**', redirectTo: '' },
];
