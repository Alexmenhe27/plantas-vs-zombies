"""Configuración leída de variables de entorno (ver .env.example)."""
import hashlib
import os
from dataclasses import dataclass, field


def _env_file() -> None:
    """Carga un archivo .env sencillo si existe (sin dependencias extra)."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(path):
        return
    # utf-8-sig: el Bloc de notas de Windows a veces guarda el archivo con BOM al inicio.
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            # Se quitan comillas puestas por error alrededor del valor ("clave" o 'clave').
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'").strip())


_env_file()

MODELO_POR_DEFECTO = "claude-haiku-5-5"


def _modelo(valor: str) -> str:
    valor = valor.strip()
    return valor if valor.startswith("claude") else MODELO_POR_DEFECTO


def _razonamiento(valor: str) -> str:
    valor = valor.strip().lower()
    return valor if valor in ("bajo", "sin") else "bajo"


@dataclass(frozen=True)
class Settings:
    supabase_url: str = field(default_factory=lambda: os.environ.get("SUPABASE_URL", "").rstrip("/"))
    supabase_service_key: str = field(default_factory=lambda: os.environ.get("SUPABASE_SERVICE_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    # Solo si tu clave es de ámbito "Organización": el ID del espacio de trabajo (wrkspc_...) al que se cobra.
    anthropic_workspace_id: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip())
    # Si quedó un modelo de otra IA (por ejemplo gemini-...), se usa el de Claude por defecto.
    ia_modelo: str = field(default_factory=lambda: _modelo(os.environ.get("IA_MODELO", "")))
    # "bajo" (recomendado): Claude razona un poco antes de responder.
    # "sin": responde sin razonar: casi el doble de rápido, pero en la evaluación del 14/10/2026 acertó bastante menos
    # (ver api/scripts/evaluar_ia.py y CAMBIOS.md), así que no se usa por defecto.
    ia_razonamiento: str = field(default_factory=lambda: _razonamiento(os.environ.get("IA_RAZONAMIENTO", "")))
    # Segundos máximos de espera entre un trozo y otro de la respuesta de Claude, y en total.
    ia_tiempo_maximo: float = field(default_factory=lambda: float(os.environ.get("IA_TIEMPO_MAXIMO", "30")))
    ia_tiempo_total: float = field(default_factory=lambda: float(os.environ.get("IA_TIEMPO_TOTAL", "60")))
    # Solo para pruebas: dirección de un servidor falso de Claude.
    ia_url: str = field(default_factory=lambda: os.environ.get("IA_URL", "").strip().rstrip("/") or "https://api.anthropic.com")
    # GBIF valida cada especie nueva (gratis, sin clave). Vacío = no validar (solo para pruebas sin internet).
    gbif_url: str = field(default_factory=lambda: os.environ.get("GBIF_URL", "https://api.gbif.org/v1").strip().rstrip("/"))
    gbif_tiempo_maximo: float = field(default_factory=lambda: float(os.environ.get("GBIF_TIEMPO_MAXIMO", "3")))
    # Por debajo de esta confianza la especie no se agrega al catálogo (queda "en revisión").
    confianza_para_catalogo: float = field(default_factory=lambda: float(os.environ.get("CONFIANZA_PARA_CATALOGO", "0.5")))
    confianza_minima: float = field(default_factory=lambda: float(os.environ.get("CONFIANZA_MINIMA", "0.7")))
    # Nota: el límite diario ya no se configura aquí; vive en la tabla "ajustes" de Supabase (ver COMO_EJECUTAR.md).
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in os.environ.get(
                "CORS_ORIGINS", "http://localhost:4200,http://localhost:8100,capacitor://localhost,http://localhost,ionic://localhost"
            ).split(",")
            if o.strip()
        ]
    )

    # Desarrollo: cualquier página servida desde la red local (para probar en el cel). En producción, déjalo vacío.
    cors_origin_regex: str | None = field(
        default_factory=lambda: os.environ.get(
            "CORS_ORIGIN_REGEX",
            r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?",
        )
        or None
    )
    # En producción oculta a la persona los detalles técnicos de los errores (siguen en la terminal de la API).
    produccion: bool = field(default_factory=lambda: os.environ.get("PRODUCCION", "").strip().lower() in ("1", "si", "sí", "true"))

    def faltantes(self) -> list[str]:
        """Variables obligatorias que no están configuradas."""
        faltan = []
        if not self.supabase_url:
            faltan.append("SUPABASE_URL")
        if not self.supabase_service_key:
            faltan.append("SUPABASE_SERVICE_KEY")
        if not self.anthropic_api_key:
            faltan.append("ANTHROPIC_API_KEY")
        return faltan

    def sal(self) -> bytes:
        """Sal para la huella anónima de la red de los invitados (derivada de la clave secreta: no hace falta otra variable)."""
        return hashlib.sha256(("sal-red:" + self.supabase_service_key).encode()).digest()


settings = Settings()
