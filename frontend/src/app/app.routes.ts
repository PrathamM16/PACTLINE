import { inject } from '@angular/core';
import { CanActivateFn, Router, Routes } from '@angular/router';
import { VoiceRoomComponent } from './voice/voice-room.component';
import { EngineeringComponent } from './engineering/engineering.component';
import { IntegrationsComponent } from './core/integrations.component';
import { LoginComponent } from './core/login.component';
import { isLoggedIn } from './core/auth';

const requireLogin: CanActivateFn = () => (isLoggedIn() ? true : inject(Router).parseUrl('/login'));

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'voice' },
  { path: 'login', component: LoginComponent },
  { path: 'voice', component: VoiceRoomComponent, canActivate: [requireLogin] },
  { path: 'engineering', component: EngineeringComponent, canActivate: [requireLogin] },
  { path: 'integrations', component: IntegrationsComponent, canActivate: [requireLogin] },
];
