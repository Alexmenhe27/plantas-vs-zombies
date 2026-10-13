"""Configuración leída de variables de entorno (ver .env.example)."""
import os
from dataclasses import dataclass, field


def _env_file() -> None:
    """Carga un archivo .env sencillo si existe (sin dependencias extra)."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_env_file()


@dataclass(frozen=True)
class Settings:
    supabase_url: str = field(default_factory=lambda: os.environ.get("SUPABASE_URL", "").rstrip("/"))
    supabase_service_key: str = field(default_factory=lambda: os.environ.get("SUPABASE_SERVICE_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))
    ia_modelo: str = field(default_factory=lambda: os.environ.get("IA_MODELO", "gemini-flash-latest"))
    # Si IA_MODELO no existe, no tiene cuota, falla o tarda demasiado, se prueban estos en orden.
    # Los alias "-latest" los mantiene Google apuntando al modelo vigente, así no se quedan viejos.
    ia_modelos_respaldo: list[str] = field(
        default_factory=lambda: [
            m.strip()
            for m in os.environ.get("IA_MODELOS_RESPALDO", "gemini-flash-latest,gemini-flash-lite-latest,gemini-2.5-flash").split(",")
            if m.strip()
        ]
    )
    # Segundos máximos de espera a un modelo de Gemini, y en total contando los de respaldo.
    ia_tiempo_maximo: float = field(default_factory=lambda: float(os.environ.get("IA_TIEMPO_MAXIMO", "40")))
    ia_tiempo_total: float = field(default_factory=lambda: float(os.environ.get("IA_TIEMPO_TOTAL", "110")))
    ia_url: str = field(default_factory=lambda: os.environ.get("IA_URL", "https://generativelanguage.googleapis.com").rstrip("/"))
    limite_diario: int = field(default_factory=lambda: int(os.environ.get("LIMITE_DIARIO", "10")))
    # Por debajo de esta confianza la especie no se agrega al catálogo (queda "en revisión").
    confianza_para_catalogo: float = field(default_factory=lambda: float(os.environ.get("CONFIANZA_PARA_CATALOGO", "0.5")))
    confianza_minima: float = field(default_factory=lambda: float(os.environ.get("CONFIANZA_MINIMA", "0.7")))
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

    def faltantes(self) -> list[str]:
        """Variables obligatorias que no están configuradas."""
        faltan = []
        if not self.supabase_url:
            faltan.append("SUPABASE_URL")
        if not self.supabase_service_key:
            faltan.append("SUPABASE_SERVICE_KEY")
        if not self.gemini_api_key:
            faltan.append("GEMINI_API_KEY")
        return faltan


settings = Settings()
