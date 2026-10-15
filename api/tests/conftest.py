import os

# Valores falsos para pruebas: nunca se llama a servicios reales.
os.environ.setdefault("SUPABASE_URL", "https://prueba.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "clave-de-prueba")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-prueba")
# Modelo fijo para que las pruebas no dependan de lo que diga api/.env.
os.environ["IA_MODELO"] = "claude-haiku-5-5"
