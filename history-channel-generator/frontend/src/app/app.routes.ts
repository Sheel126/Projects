import { Routes } from '@angular/router';
import { ProjectDashboardComponent } from './features/project-wizard/project-dashboard.component';
import { ProjectWizardComponent } from './features/project-wizard/project-wizard.component';

export const routes: Routes = [
  { path: '', component: ProjectDashboardComponent },
  { path: 'projects/:id', component: ProjectWizardComponent },
  { path: '**', redirectTo: '' },
];
