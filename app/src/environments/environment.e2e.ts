// Solo para las pruebas de punta a punta (pruebas/e2e): apunta al mini Supabase local.
export const environment = {
  production: false,
  supabaseUrl: 'http://localhost:54321',
  supabaseAnonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6Im1pbmktc3VwYWJhc2UiLCJleHAiOjIxMDcxOTYxODB9.p-Q146oV7S6UFJ3gcOxozuXPkzj98lfpNyqOZPXc6ic',
  apiUrl: 'http://localhost:8000',
  limiteDiario: 10,
};
