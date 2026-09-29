---
name: edicion_diff
kind: protocol
description: Diff/replace para editar archivos existentes; ```file para programas nuevos.
always: true
tools: []
---

# Edición por parches

## Programa nuevo
Si el usuario pide crear, hacer o armar algo y el archivo no existe aún:
- Entrega el programa completo en uno o más bloques ```file.
- El código debe cumplir el pedido (calculadora, menú, etc.), no un hello world.
- No uses diff/replace para inventar un archivo desde cero.

## Cuándo editar
Solo cuando el archivo ya está en el proyecto y el cambio es local.

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
- No pegues el proyecto completo al editar.
- No mezcles varios archivos en un solo hunk sin cabecera `diff --git` o `---`.
- No respondas con JSON de tools cuando el usuario pide un programa.
