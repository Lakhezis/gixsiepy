# GixsiePy

Una interfaz nativa, suave y sencilla para Git, escrita en Python 3 y GTK4.
El desarrollo avanza por etapas. **Implementadas: etapas 1 a 3, repositorios, staging y diff.**

## Instalación en Debian 13

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-4.0 git
sudo apt install fonts-quicksand
```

Quicksand es opcional. Si falta, la aplicación utiliza una fuente sans-serif del sistema.
Se requiere GTK 4.10 o posterior; Debian 13 proporciona GTK 4.18.
No es necesario instalar paquetes con pip ni usar un entorno virtual.

## Ejecución

Desde la carpeta del proyecto, en una sesión gráfica:

```bash
/usr/bin/python3 main.py
```

Los recursos se buscan junto a `main.py`, de modo que también se puede ejecutar
el archivo por su ruta absoluta desde otra carpeta.

## Qué podés hacer en la etapa 1

- Elegir una carpeta con el selector gráfico.
- Abrir un repositorio existente y consultar su nombre, raíz y rama actual.
- Elegir una subcarpeta y trabajar con la raíz del repositorio.
- Identificar una rama sin commits o un `HEAD` separado.
- Inicializar una carpeta después de pulsar **Inicializar repositorio** y confirmar.
- Actualizar manualmente los datos y consultar los errores originales de Git.

La aplicación no inicializa nada al abrir una carpeta. Inicializar crea los metadatos
Git, conserva los archivos y no los prepara ni hace commits. La rama inicial respeta
la configuración de Git del usuario (`init.defaultBranch`).

`HEAD` identifica el punto actual del historial. Normalmente sigue una rama; si está
separado, estás consultando un commit concreto. Un repositorio nuevo tiene una rama,
pero todavía no tiene un commit al que apuntar.

## Estado de archivos y staging (etapa 2)

Al abrir un repositorio aparecen dos grupos con contadores:

- **CAMBIOS**: archivos nuevos y cambios que todavía no están preparados.
- **PREPARADOS PARA COMMIT**: versiones que Git tiene en el índice para el próximo commit.

Cada fila muestra la ruta, una letra y una descripción: `M` modificado, `A` añadido,
`D` eliminado y `?` sin seguimiento. También se identifican renombrados (`R`),
cambios de tipo (`T`) y conflictos (`U`). Los archivos ignorados por `.gitignore`
no aparecen como nuevos ni se preparan automáticamente.

Seleccioná una fila en CAMBIOS y pulsá **Preparar archivo (Stage)**, o utilizá
**Preparar todos los cambios** para incluir modificaciones, archivos nuevos y eliminaciones
de todo el repositorio. Seleccionar una fila solamente selecciona el archivo.

En PREPARADOS PARA COMMIT, **Quitar de staging (Unstage)** conserva el contenido local
y retira esa versión del próximo commit. Funciona también antes del primer commit.
Si quitás de staging una eliminación, el archivo sigue eliminado en la carpeta de trabajo.
Después de cada operación se consulta Git y se actualizan ambas listas.

El índice es una copia de las versiones preparadas. Si preparás un archivo y luego lo
editás otra vez, aparecerá en ambos grupos: el índice conserva la versión preparada y
la carpeta contiene cambios adicionales. Prepararlo de nuevo actualiza esa copia.

Los conflictos existentes se muestran en CAMBIOS y requieren resolución externa.
Los cambios de submódulos también requieren trabajar en su propio repositorio.
En esos casos se desactiva **Preparar todos los cambios**, mientras que los archivos
normales se pueden preparar individualmente.

## Diff de archivos (etapa 3)

Seleccioná un archivo en cualquiera de los dos grupos. El panel derecho muestra su
diff con fuente monoespaciada, líneas añadidas en verde suave, eliminadas en rosa y
encabezados en crema. Podés seleccionar y copiar el texto. El separador entre los
paneles permite ajustar su ancho y las listas de archivos se desplazan por separado.

- En **CAMBIOS**, se compara el índice con la carpeta de trabajo.
- En **PREPARADOS PARA COMMIT**, se compara el último commit con el índice; antes del
  primer commit se muestran todas las líneas preparadas como nuevas.
- Para archivos nuevos sin seguimiento se compara su contenido con un archivo vacío.

`+` indica una línea añadida, `-` una eliminada y `@@` el comienzo de un bloque de
cambios. Las líneas de contexto ayudan a ubicar el cambio. `---` y `+++` identifican
los archivos de origen y destino; esos encabezados también tienen su propio color.

Leer el diff conserva los archivos y el índice. Después de stage, unstage o Actualizar,
el visor vuelve a cargar la selección. Al cambiar de archivo rápidamente se ignoran
los resultados anteriores. Los errores aparecen en el panel con acceso a los detalles
originales de Git.

Los binarios muestran una explicación. La vista previa se limita a **512 KiB o 5000
líneas** y avisa cuando se recorta; para ver un diff mayor, utilizá Git en la terminal.
Los conflictos siguen requiriendo resolución externa. Los renombrados y cambios de
permisos muestran los metadatos que Git incluye en el diff.

## Arquitectura

`main.py` inicia GTK y carga CSS. `ui/window.py` coordina la interfaz y llama a
`GitService` mediante `ui/tasks.py`. `ui/dialogs.py` muestra confirmaciones y errores.
`ui/files_panel.py` muestra las dos listas y comunica las acciones de sus botones a la ventana.
`ui/diff_panel.py` representa el diff y aplica etiquetas de color a sus líneas.
`git/git_service.py` no depende de GTK: ejecuta el Git del sistema con listas de
argumentos y `shell=False`, e interpreta sus resultados.

Las operaciones del repositorio se ejecutan en un trabajador. Una segunda instancia
de `TaskRunner` lee los diffs para permitir cambiar de selección mientras se cargan.
Los resultados vuelven al hilo principal
con `GLib.idle_add`, porque GTK debe actualizarse únicamente desde ese hilo.
Las acciones se desactivan durante una operación para evitar ejecuciones duplicadas.
Si intentás cerrar mientras Git trabaja, la ventana espera a que termine la acción.
Los comandos de esta etapa tienen un límite de 30 segundos por ejecución.

Los errores de acceso, repositorios dañados o propiedad dudosa no se interpretan como
carpetas nuevas. La aplicación no modifica automáticamente la configuración de seguridad.
Los repositorios bare y la carpeta interna `.git` no son carpetas de trabajo admitidas.

Para el estado se utiliza `git status --porcelain=v2 --branch -z --untracked-files=all`.
Los separadores nulos permiten conservar nombres con espacios, tabulaciones y saltos de línea.
Las rutas se pasan como argumentos literales, con `--literal-pathspecs` y `--` cuando corresponde.
Stage utiliza `git add -A`; unstage utiliza `git restore --staged`, o
`git update-index --force-remove` antes del primer commit (solo modifica el índice).
Los renombrados se quitan de staging considerando sus dos rutas.

El diff utiliza `git diff` para cambios locales y `git diff --cached` para staging.
Para archivos nuevos se utiliza `git diff --no-index -- /dev/null <ruta>`; el código
de salida 1 indica diferencias y se interpreta como un resultado normal. Se desactivan
colores ANSI, programas de diff externos y conversiones `textconv`. La salida del diff
se guarda temporalmente en disco y se lee con un límite para no cargarla entera en memoria.

## Pruebas

```bash
/usr/bin/python3 -m unittest discover -v
```

Las pruebas utilizan repositorios temporales y una configuración Git aislada.
No modifican tus repositorios personales ni tu identidad Git.

También hay pruebas gráficas opcionales. Abren ventanas brevemente, verifican el
estado de los botones, la confirmación, los errores y la respuesta del hilo principal:

```bash
GIXSIE_RUN_UI_TESTS=1 /usr/bin/python3 -m unittest tests.test_ui -v
```

Para revisar la interfaz de la etapa 1:

1. Abrir la aplicación y cancelar el selector: debe permanecer en la bienvenida.
2. Abrir un repositorio y luego una subcarpeta: deben mostrar la misma raíz y rama.
3. Abrir una carpeta nueva con un archivo de prueba: no debe aparecer `.git` todavía.
4. Cancelar la confirmación de inicialización: la carpeta debe permanecer intacta.
5. Confirmar inicialización: deben aparecer la rama y el aviso de que no hay commits.
6. Actualizar y volver a abrir otra carpeta; comprobar nombres con espacios y acentos.
7. Navegar con Tab y revisar la ventana a distintos tamaños.

Para revisar la etapa 2 con un repositorio de prueba:

1. Crear archivos nuevos y modificar o eliminar archivos ya guardados en un commit.
2. Abrirlo y comprobar las letras, los contadores y ambos grupos.
3. Seleccionar un archivo y prepararlo: debe moverse al grupo de preparados automáticamente.
4. Editarlo otra vez y pulsar Actualizar: debe aparecer en ambos grupos.
5. Quitar de staging y comprobar que la última edición local se conserva.
6. Preparar todos; verificar que `.gitignore` se respeta y se incluyen eliminaciones.
7. Repetir stage y unstage en un repositorio sin commits.

La suite incluye pruebas de nombres especiales, renombrados, archivos en ambos grupos,
bloqueos del índice y actualización tras errores. No se añadieron dependencias.

Para revisar la etapa 3:

1. Seleccionar un archivo modificado y comprobar las líneas añadidas, eliminadas y contexto.
2. Prepararlo, editarlo otra vez y comparar sus diffs en ambos grupos.
3. Hacer stage y unstage; el visor debe seguir la selección y actualizar el contenido.
4. Probar un archivo nuevo, uno eliminado, un renombrado y un archivo binario.
5. Cambiar de archivo rápidamente: solo debe mostrarse el resultado de la selección actual.
6. Crear un archivo de más de 5000 líneas y comprobar el aviso de vista previa recortada.

Las pruebas del diff verifican además que la lectura conserva el índice, los colores
de encabezados y líneas, la actualización manual y el descarte de resultados antiguos.

## Próximas etapas

4. Mensaje y creación de commits.
5. Pull y push con remoto, seguimiento y errores visibles.
6. Historial de commits recientes.

Cada etapa se implementa y verifica antes de continuar con la siguiente.
