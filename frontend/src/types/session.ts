export interface SessionView {
  role: 'VIEWER' | 'ANALYST' | 'ADMIN'
  authenticated: boolean
  auth_mode: 'development_bypass' | 'easy_auth' | 'anonymous'
  environment: string
  can_operate: boolean
  can_administer: boolean
}
