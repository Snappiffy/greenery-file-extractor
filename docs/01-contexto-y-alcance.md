# 01 · Contexto y alcance

## El problema que resuelve

Greenary compra plantas a una decena de viveros (*growers*). Cada uno manda periódicamente
su lista de precios y disponibilidad. Esas listas alimentan el catálogo interno, que a su
vez alimenta cotizaciones, órdenes de compra y facturación.

Hasta ahora el archivo se le entregaba entero a un modelo de lenguaje para que lo leyera.
Eso tenía dos problemas: coste proporcional a filas × corridas, y errores de interpretación
imposibles de depurar.

**La observación clave: el formato de cada grower es estricto y cambia una o dos veces al
año.** Un formato estricto no necesita un modelo que lo lea — necesita un parser
configurado. Este servicio es ese parser.

## Dónde encaja

```
                    ┌──────────────────────────────┐
                    │  Worker (Bun)                │
                    │  orquesta la corrida         │
                    └───────┬──────────────▲───────┘
                            │              │
        POST /v1/extract    │              │  filas + diagnósticos
        (perfil + URL)      │              │
                            ▼              │
                    ┌──────────────────────┴───────┐
                    │  EXTRACTOR  (este servicio)  │
                    │  Python · FastAPI · sin estado│
                    └───────┬──────────────────────┘
                            │ GET (URL firmada)
                            ▼
                    ┌──────────────────────────────┐
                    │  Object storage (R2 / S3)    │
                    │  archivo crudo inmutable     │
                    └──────────────────────────────┘
```

El worker es el único cliente. Nadie más llama a este servicio, y este servicio no llama a
nadie salvo al object storage para descargar el documento.

## Qué hace

1. Descarga el documento desde una URL firmada (o lo recibe en línea, en base64).
2. Calcula un **fingerprint del layout** y lo compara con el que trae el perfil.
3. Extrae filas aplicando el perfil: recorta columnas por geometría, parsea precio, tamaño,
   cantidad y disponibilidad.
4. Devuelve las filas con su texto crudo, sus valores parseados y sus incidencias, más un
   bloque de diagnósticos.

Y, por separado, `POST /v1/sample` devuelve **evidencia del layout** (líneas con
coordenadas, candidatos de columna, líneas de tabla detectadas) para que el worker pueda
construir un perfil nuevo cuando aparece un grower o cambia una plantilla.

## Qué NO hace — y por qué

| No hace | Por qué |
|---|---|
| Llamar a un LLM | La inferencia de perfiles vive en el worker. Aquí rompería el determinismo y metería secretos en un servicio que de otro modo es puro |
| Emparejar contra el catálogo | No conoce SKUs, plantas ni variedades. El emparejamiento (`grower_alias`, trigramas) es del worker |
| Escribir en base de datos | No tiene credenciales. Lo que produce es una respuesta HTTP, nada más |
| Decidir si una fila se aplica | Solo reporta lo que leyó y lo que le costó leerlo. La decisión es del worker y de la persona que aprueba la corrida |
| Parsear xlsx, xls o csv | Los tabulares los parsea el worker en Bun. Este servicio es para documentos donde hay que recuperar estructura a partir de geometría |
| Guardar el documento | Lo descarga a memoria o a un temporal, lo procesa y lo descarta |

## El contrato conceptual

> **Entra** un documento y un perfil. **Sale** una lista de filas y un juicio honesto sobre
> la calidad de la lectura. El servicio no opina sobre el negocio.

Todo lo que se añada debe caber en esa frase. Si una funcionalidad propuesta no cabe,
pertenece al worker.

## Vocabulario

| Término | Significado aquí |
|---|---|
| **grower** | Vivero proveedor. Opaco para este servicio: solo un identificador que se transporta |
| **perfil** | El objeto que describe cómo leer los documentos de un grower. Ver `docs/03` |
| **fingerprint** | Hash del *layout* (no del contenido). Detecta cambios de plantilla. Ver `docs/05` |
| **fila** (`row`) | Una unidad de producto leída del documento. No es necesariamente una línea del PDF |
| **issue** | Una incidencia detectada en una fila o en el documento. No detiene el proceso |
| **estrategia** | El método de recorte de columnas: `columns`, `ruling` o `regex`. Ver `docs/05` |
