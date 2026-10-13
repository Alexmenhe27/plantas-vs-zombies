// Configuración de producción. La clave "anon" de Supabase es pública (la protege RLS),
// así que puede vivir en la app. Las claves secretas NUNCA van aquí.
export const environment = {
  production: true,
  supabaseUrl: 'https://boppdniulsvoyevhoerp.supabase.co',
  supabaseAnonKey: 'sb_publishable_AZczmBRCiTExBRs0vzlT3A_Tnm5TJst',
  apiUrl: 'https://TU-API.run.app',
  limiteDiario: 10,
};
