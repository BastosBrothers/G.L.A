---
name: edicion_diff
kind: protocol
description: Obliga a devolver cambios como diff unificado o reemplazo por rango, nunca el archivo entero si el cambio es local.
always: true
tools: []
---

# Edición por parches

## Cuándo
Siempre que propongas un cambio de código.

## Diff unificado
Un bloque por archivo:

```diff
--- a/ruta/archivo.py
+++ b/ruta/archivo.py
@@ -12,7 +12,8 @@
 contexto
-linea vieja
+linea nueva
```

## Reemplazo por rango
Si no puedes armar un diff git:

```replace
path: ruta/archivo.py
start_line: 12
end_line: 20
---
codigo nuevo
```

`start_line` y `end_line` son 1-indexados e inclusivos.

## No hacer
- No pegues el proyecto completo.
- No mezcles varios archivos en un solo hunk sin cabecera `diff --git` o `---`.
