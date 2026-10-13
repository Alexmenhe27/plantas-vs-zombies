// Configuración de desarrollo. La clave "anon" de Supabase es pública (la protege RLS),
// así que puede vivir en la app. Las claves secretas NUNCA van aquí.
export const environment = {
  production: false,
  supabaseUrl: 'https://boppdniulsvoyevhoerp.supabase.co',
  supabaseAnonKey: 'sb_publishable_AZczmBRCiTExBRs0vzlT3A_Tnm5TJst',
  // La API corre en la misma computadora que sirve la app: funciona en localhost y desde el cel por la red local.
  apiUrl: `http://${location.hostname}:8000`,
  limiteDiario: 10,
};
