import os

# Valores falsos para pruebas: nunca se llama a servicios reales.
os.environ.setdefault("SUPABASE_URL", "https://prueba.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "clave-de-prueba")
os.environ.setdefault("GEMINI_API_KEY", "clave-gemini-prueba")
# Modelos fijos para que las pruebas no dependan de lo que diga api/.env.
os.environ["IA_MODELO"] = "gemini-prueba"
os.environ["IA_MODELOS_RESPALDO"] = "gemini-respaldo"
