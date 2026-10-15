import { Injectable, computed, signal } from '@angular/core';
import { AuthChangeEvent, Session, SupabaseClient, createClient } from '@supabase/supabase-js';
import { environment } from '../../environments/environment';
import { Perfil } from './modelos';

/** Cliente único de Supabase y estado de la sesión. */
@Injectable({ providedIn: 'root' })
export class SupabaseService {
  readonly client: SupabaseClient = createClient(environment.supabaseUrl, environment.supabaseAnonKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  });

  readonly session = signal<Session | null>(null);
  readonly perfil = signal<Perfil | null>(null);
  readonly listo = signal(false);
  /** Último evento de autenticación (p. ej. PASSWORD_RECOVERY al abrir el enlace del correo). */
  readonly evento = signal<AuthChangeEvent | null>(null);
  readonly userId = computed(() => this.session()?.user.id ?? null);
  readonly esAdmin = computed(() => this.perfil()?.rol === 'admin');
  /** Invitado: entró sin cuenta (inicio de sesión anónimo de Supabase). */
  readonly esInvitado = computed(() => !!this.session()?.user.is_anonymous);
  /** Correo pendiente de confirmar cuando un invitado crea su cuenta. */
  readonly correoPorConfirmar = computed(() => this.session()?.user.new_email ?? null);

  private readonly inicio: Promise<void>;

  constructor() {
    this.client.auth.onAuthStateChange((evento, session) => {
      this.evento.set(evento);
      this.session.set(session);
      if (!session) this.perfil.set(null);
      else if (evento === 'SIGNED_IN' || evento === 'USER_UPDATED') void this.cargarPerfil();
    });
    this.inicio = this.client.auth.getSession().then(async ({ data }) => {
      this.session.set(data.session);
      if (data.session) await this.cargarPerfil();
      this.listo.set(true);
    });
  }

  /** Espera a que se lea la sesión guardada (lo usan los guards). */
  esperarInicio(): Promise<void> {
    return this.inicio;
  }

  async cargarPerfil(): Promise<void> {
    const id = this.userId();
    if (!id) return;
    const { data } = await this.client.from('perfiles').select('*').eq('id', id).maybeSingle();
    this.perfil.set(data as Perfil | null);
  }

  async iniciarSesion(email: string, password: string): Promise<void> {
    const { error } = await this.client.auth.signInWithPassword({ email, password });
    if (error) throw new Error(traducirErrorAuth(error.message));
  }

  /** Entrar sin cuenta. Supabase crea un usuario anónimo; sus observaciones se conservan si después crea su cuenta. */
  async entrarComoInvitado(): Promise<void> {
    const { error } = await this.client.auth.signInAnonymously();
    if (error) throw new Error(traducirErrorAuth(error.message));
  }

  /** Devuelve true si hay que confirmar el correo antes de entrar. */
  async registrarse(email: string, password: string, username: string): Promise<boolean> {
    await this.revisarNombreLibre(username);
    const { data, error } = await this.client.auth.signUp({
      email,
      password,
      options: { data: { nombre_usuario: username }, emailRedirectTo: window.location.origin },
    });
    if (error) throw new Error(traducirErrorAuth(error.message));
    return !data.session;
  }

  /**
   * Un invitado crea su cuenta sin perder nada: se le agrega su correo al mismo usuario.
   * Supabase manda un correo para confirmarlo; el enlace lleva a elegir la contraseña.
   */
  async crearCuentaDesdeInvitado(email: string, username: string): Promise<void> {
    await this.revisarNombreLibre(username);
    const { error } = await this.client.auth.updateUser(
      { email, data: { nombre_usuario: username } },
      { emailRedirectTo: `${window.location.origin}/nueva-contrasena?alta=1` },
    );
    if (error) throw new Error(traducirErrorAuth(error.message));
    const id = this.userId();
    if (id) {
      await this.client.from('perfiles').update({ nombre_usuario: username }).eq('id', id);
      await this.cargarPerfil();
    }
  }

  private async revisarNombreLibre(username: string): Promise<void> {
    const { data: libre } = await this.client.rpc('nombre_usuario_disponible', { nombre: username });
    if (libre === false) throw new Error('Ese nombre de usuario ya existe. Prueba con otro.');
  }

  async recuperarContrasena(email: string): Promise<void> {
    const { error } = await this.client.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/nueva-contrasena`,
    });
    if (error) throw new Error(traducirErrorAuth(error.message));
  }

  async cambiarContrasena(password: string): Promise<void> {
    const { error } = await this.client.auth.updateUser({ password });
    if (error) throw new Error(traducirErrorAuth(error.message));
  }

  async cerrarSesion(): Promise<void> {
    await this.client.auth.signOut();
  }

  async actualizarUsername(username: string): Promise<void> {
    const id = this.userId();
    const { error } = await this.client.from('perfiles').update({ nombre_usuario: username }).eq('id', id);
    if (error) throw new Error(error.code === '23505' ? 'Ese nombre de usuario ya existe.' : 'No se pudo guardar el nombre.');
    await this.cargarPerfil();
  }

  /** Si las observaciones nuevas se publican (con ubicación aproximada). Por defecto: privadas. */
  async cambiarPublicarPorDefecto(valor: boolean): Promise<void> {
    const id = this.userId();
    const { error } = await this.client.from('perfiles').update({ publicar_por_defecto: valor }).eq('id', id);
    if (error) throw new Error('No se pudo guardar la preferencia.');
    const p = this.perfil();
    if (p) this.perfil.set({ ...p, publicar_por_defecto: valor });
  }

  token(): string | null {
    return this.session()?.access_token ?? null;
  }
}

export function traducirErrorAuth(mensaje: string): string {
  const m = mensaje.toLowerCase();
  if (m.includes('invalid login credentials')) return 'El correo o la contraseña no son correctos.';
  if (m.includes('email not confirmed')) return 'Confirma tu correo: te enviamos un enlace al registrarte.';
  if (m.includes('already registered') || m.includes('already been registered') || m.includes('email address has already'))
    return 'Ya existe una cuenta con ese correo.';
  if (m.includes('password should be at least')) return 'La contraseña debe tener al menos 6 caracteres.';
  if (m.includes('database error saving new user')) return 'No se pudo crear la cuenta. Prueba con otro nombre de usuario.';
  if (m.includes('anonymous sign-ins are disabled'))
    return 'Entrar sin cuenta todavía no está activado en este servidor. Crea una cuenta gratis para continuar.';
  if (m.includes('rate limit') || m.includes('too many')) return 'Demasiados intentos. Espera un momento y vuelve a probar.';
  if (m.includes('captcha')) return 'No pudimos comprobar que no eres un robot. Intenta de nuevo.';
  if (m.includes('invalid email') || m.includes('unable to validate email')) return 'Ese correo no es válido.';
  if (m.includes('fetch') || m.includes('network')) return 'Sin conexión. Revisa tu internet.';
  return 'Ocurrió un error. Intenta de nuevo.';
}
