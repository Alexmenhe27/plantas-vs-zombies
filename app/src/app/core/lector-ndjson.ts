/**
 * Lee una respuesta NDJSON (un objeto JSON por línea) a medida que llega y avisa cada objeto completo.
 * Así la app muestra el nombre de la especie en cuanto la IA lo escribe, sin esperar la respuesta entera.
 */
export async function leerNdjson<T>(cuerpo: ReadableStream<Uint8Array>, alObjeto: (objeto: T) => void): Promise<void> {
  const lector = cuerpo.getReader();
  const decodificador = new TextDecoder();
  let pendiente = '';
  const procesar = (texto: string) => {
    pendiente += texto;
    let salto: number;
    while ((salto = pendiente.indexOf('\n')) >= 0) {
      const linea = pendiente.slice(0, salto).trim();
      pendiente = pendiente.slice(salto + 1);
      if (linea) alObjeto(JSON.parse(linea) as T);
    }
  };
  for (;;) {
    const { done, value } = await lector.read();
    if (done) break;
    procesar(decodificador.decode(value, { stream: true }));
  }
  procesar(decodificador.decode() + '\n');
}
