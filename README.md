# GixsiePy

**Git a tu ritmo.** Una aplicación de escritorio para trabajar con repositorios Git
mediante una interfaz sencilla, con colores suaves y explicaciones claras.

GixsiePy está escrita en Python y GTK4, y utiliza el Git instalado en el sistema.
Está pensada tanto para aprender los conceptos básicos como para trabajar con
repositorios locales. Su entorno principal es **Debian 13**.

El proyecto está en desarrollo: ya permite abrir repositorios, preparar archivos,
revisar diferencias y crear commits. Pull, push y el historial gráfico son las
próximas incorporaciones.

## Funciones disponibles

- Abrir una carpeta o una subcarpeta de un repositorio y consultar la rama actual.
- Inicializar un repositorio con confirmación explícita.
- Ver archivos modificados, nuevos, eliminados y preparados para commit.
- Preparar un archivo, quitarlo de staging o preparar todos los cambios.
- Consultar las diferencias de archivos, con colores para las líneas añadidas y eliminadas.
- Crear commits con un mensaje de una o varias líneas.
- Actualizar el estado y consultar los mensajes originales de Git cuando ocurre un error.

Las operaciones Git se ejecutan en segundo plano para que la ventana siga respondiendo.
La interfaz utiliza una fuente sans-serif; el visor de diferencias utiliza una fuente
monoespaciada. El detalle floral es un SVG propio incluido en el proyecto.

## Instalación

Se necesita una sesión de escritorio, Python 3, Git, GTK **4.10 o posterior** y PyGObject.
En Debian 13 se pueden instalar las dependencias desde los repositorios del sistema:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-4.0 git
```

La fuente Quicksand es opcional:

```bash
sudo apt install fonts-quicksand
```

Si no está instalada, la aplicación utiliza una fuente sans-serif del sistema.
No se necesitan paquetes de pip ni un entorno virtual.

Referencias de los paquetes para Debian 13:
[GTK4](https://packages.debian.org/trixie/gir1.2-gtk-4.0),
[PyGObject](https://packages.debian.org/trixie/python3-gi) y
[Quicksand](https://packages.debian.org/trixie/fonts-quicksand).

## Ejecución

Descargar el código y, desde la carpeta del proyecto, ejecutar:

```bash
/usr/bin/python3 main.py
```

También se puede ejecutar `main.py` por su ruta absoluta desde otra carpeta.
Los estilos y las imágenes se buscan junto al código de la aplicación.

Se recomienda utilizar `/usr/bin/python3`: un intérprete instalado por separado o
un entorno virtual puede no tener acceso a los bindings GTK instalados con apt.

## Primeros pasos

1. Pulsar **Abrir carpeta…** y seleccionar una carpeta local.
2. Si todavía no tiene un repositorio, pulsar **Inicializar repositorio** y confirmar.
3. Seleccionar un archivo en **CAMBIOS** para revisar su diff.
4. Pulsar **Preparar archivo (Stage)** o **Preparar todos los cambios**.
5. Revisar las versiones en **PREPARADOS PARA COMMIT**.
6. Escribir un mensaje, por ejemplo `Agregar instrucciones de instalación`.
7. Pulsar **Hacer commit**. Al terminar, se limpia el mensaje y se actualiza el estado.

**Actualizar** vuelve a consultar Git. Es útil después de editar archivos en otra
aplicación o ejecutar comandos desde la terminal. Al abrir una subcarpeta, las
operaciones se realizan sobre la raíz de su repositorio.

El mensaje del commit se escribe debajo de las listas de archivos. Las listas y el
diff tienen desplazamiento independiente; en ventanas pequeñas también se puede
desplazar el contenido principal para acceder a todos los paneles.

### Cambios, staging y commit

**CAMBIOS** muestra lo que todavía no está preparado. **PREPARADOS PARA COMMIT**
muestra las versiones guardadas en el índice de Git, también llamado *staging*.

| Letra | Estado |
| --- | --- |
| `M` | Modificado |
| `A` | Añadido |
| `D` | Eliminado |
| `?` | Nuevo, sin seguimiento |
| `R` | Renombrado |
| `C` | Copiado |
| `T` | Cambio de tipo |
| `U` | Conflicto |

Preparar un archivo guarda su versión actual en el índice. Si se lo edita después,
aparece en ambos grupos: la versión preparada sigue lista para el commit y la
edición posterior queda pendiente. Prepararlo otra vez actualiza esa versión.

**Quitar de staging (Unstage)** conserva el contenido de la carpeta de trabajo y
retira los cambios del próximo commit. Funciona también antes del primer commit.
Quitar una eliminación de staging deja el archivo eliminado en la carpeta de trabajo.
Los archivos ignorados por `.gitignore` no se incluyen como archivos nuevos.

Un **commit** registra las versiones preparadas en el historial local. El botón se
habilita cuando hay archivos preparados, el mensaje contiene texto y no hay
conflictos pendientes. Las ediciones sin preparar quedan disponibles para otro commit.
Crear un commit no publica cambios en un servidor.

El mensaje puede incluir una primera línea breve y una explicación separada por una
línea vacía. Si Git rechaza el commit, el mensaje se conserva para corregir el problema
y volver a intentar. Actualizar conserva el borrador; abrir otro repositorio lo limpia.
El borrador dura mientras la aplicación está abierta.

### Leer las diferencias

El panel derecho muestra el diff del archivo seleccionado:

- En **CAMBIOS**, compara el índice con la carpeta de trabajo.
- En **PREPARADOS PARA COMMIT**, compara el último commit con el índice. Antes del
  primer commit, muestra el contenido preparado como nuevo.
- Para archivos sin seguimiento, compara el contenido con un archivo vacío.

`+` indica una línea añadida y `-` una eliminada. `@@` inicia un bloque de cambios.
Las líneas de contexto ayudan a ubicar las ediciones. Los encabezados `---` y `+++`
identifican los archivos de origen y destino.

El texto del diff se puede seleccionar y copiar. El separador permite ajustar el
ancho de los paneles. Los archivos binarios muestran una explicación; los diffs
mayores de **512 KiB o 5000 líneas** muestran una vista previa recortada con un aviso.

## Configuración de Git y errores frecuentes

GixsiePy utiliza la configuración existente de Git, incluidos la rama inicial,
la identidad del autor, los hooks y la firma de commits. No configura una identidad
ni desactiva las validaciones del repositorio automáticamente.

### Git pide un nombre y un correo

Git necesita una identidad para crear commits. Para configurarla únicamente en un
repositorio, abrir una terminal en su carpeta y ejecutar con los datos propios:

```bash
git config user.name "Tu nombre"
git config user.email "tu-correo@example.com"
```

Si se desea usar esa identidad como valor predeterminado para todos los repositorios,
agregar `--global` después de `git config` en ambos comandos.

### Un hook rechaza el commit o falla la firma

Consultar **Detalles de Git** en el diálogo de error. Los hooks pueden validar el
contenido o el mensaje; la firma depende de la configuración y las claves del usuario.
Resolver el problema y volver a intentar: el mensaje del commit se conserva.

### Hay conflictos, submódulos o HEAD separado

Los conflictos se muestran, pero su resolución requiere la terminal u otra herramienta.
Mientras existan conflictos, se desactiva el commit. Los cambios internos de submódulos
se gestionan en su propio repositorio; en esos casos no se permite preparar todos los
cambios juntos, aunque se pueden preparar los archivos normales individualmente.

`HEAD` indica el punto actual del historial. Normalmente sigue una rama. Con **HEAD
separado**, se está trabajando desde un commit concreto sin una rama activa. La
aplicación pide confirmación antes de crear un commit en esa situación. Para conservar
ese commit al cambiar de posición, crear una rama desde la terminal u otra herramienta.

### El commit se creó, pero la vista no se actualizó

Pulsar **Actualizar** para consultar el estado nuevamente. La aplicación informa que
el commit se creó y limpia el mensaje incluso si falla esa consulta posterior.

### No se puede abrir una carpeta

Los errores de permisos, propiedad dudosa o repositorios dañados muestran el mensaje
original de Git. Los repositorios bare y la carpeta interna `.git` no son carpetas de
trabajo admitidas. Seleccionar la carpeta que contiene los archivos del proyecto.

## Alcance y próximos pasos

| Etapa | Función | Estado |
| --- | --- | --- |
| 1 | Abrir e inicializar repositorios | Disponible |
| 2 | Estado de archivos y staging | Disponible |
| 3 | Diff de cambios locales y preparados | Disponible |
| 4 | Crear commits | Disponible |
| 5 | Pull y push | Pendiente |
| 6 | Historial de commits recientes | Pendiente |

El MVP no incluye clone, gestión de ramas, resolución visual de conflictos, rebase,
cherry-pick, stash avanzado, tags ni integraciones con GitHub o GitLab.
No ofrece reset destructivo, clean ni force push.

## Desarrollo

La lógica Git está separada de la interfaz:

```text
GTK UI → GitService → subprocess → Git → Repositorio
```

```text
gixsiePy/
├── main.py
├── git/
│   └── git_service.py
├── ui/
│   ├── window.py
│   ├── tasks.py
│   ├── dialogs.py
│   ├── files_panel.py
│   ├── diff_panel.py
│   └── commit_panel.py
├── styles/
│   └── style.css
├── assets/
│   └── flower-pattern.svg
├── tests/
│   ├── test_git_service.py
│   └── test_ui.py
└── README.md
```

| Archivo | Responsabilidad |
| --- | --- |
| `main.py` | Iniciar GTK y cargar los estilos. |
| `git/git_service.py` | Ejecutar Git e interpretar sus resultados, sin depender de GTK. |
| `ui/window.py` | Coordinar los paneles, las acciones y la actualización del repositorio. |
| `ui/tasks.py` | Ejecutar operaciones en un trabajador y devolver resultados al hilo de GTK. |
| `ui/dialogs.py` | Mostrar confirmaciones y errores con detalles. |
| `ui/files_panel.py` | Mostrar las listas de archivos y las acciones de staging. |
| `ui/diff_panel.py` | Mostrar el diff y resaltar sus líneas. |
| `ui/commit_panel.py` | Recoger el mensaje y habilitar el botón según el estado. |
| `styles/style.css` | Definir colores, tipografía y aspecto de los widgets. |
| `assets/flower-pattern.svg` | Aportar el detalle floral de la bienvenida. |
| `tests/` | Verificar Git y los flujos de la interfaz con repositorios temporales. |

Los comandos utilizan listas de argumentos con `shell=False` y rutas literales.
El estado se interpreta con `git status --porcelain=v2 -z`; staging utiliza `git add -A`.
Unstage utiliza `git restore --staged` o, antes del primer commit,
`git update-index --force-remove`, que solo modifica el índice.
Los diffs se leen con `git diff`, `git diff --cached` o `git diff --no-index` para
archivos nuevos, sin ejecutar conversores de texto ni programas de diff externos.
El commit utiliza `git commit --cleanup=whitespace -m <mensaje>`, sin preparar
archivos adicionales y conservando las líneas del mensaje que empiezan por `#`.

Las operaciones se serializan y sus botones se desactivan mientras Git trabaja.
Un segundo trabajador permite cargar diffs y descartar resultados de selecciones
anteriores. GTK recibe las actualizaciones mediante `GLib.idle_add`. Cada ejecución
Git tiene un límite de 30 segundos; la ventana pide esperar antes de cerrar durante
una operación del repositorio.

### Pruebas automatizadas

Desde la carpeta del proyecto:

```bash
/usr/bin/python3 -m unittest discover -v
```

Las pruebas gráficas se omiten por defecto. Para ejecutar toda la suite, incluyendo
ventanas GTK, se necesita una sesión gráfica disponible:

```bash
GIXSIE_RUN_UI_TESTS=1 /usr/bin/python3 -m unittest discover -v
```

Las pruebas utilizan repositorios temporales y configuración Git aislada. No modifican
repositorios personales ni la identidad Git del usuario. Verifican nombres especiales,
staging parcial, renombrados, binarios, diffs grandes, errores de Git, commits,
hooks, firma, respuesta de la interfaz y prevención de acciones duplicadas.

### Comprobación manual del flujo de commit

En un repositorio de prueba:

1. Crear o modificar un archivo; comprobar que no se puede hacer commit sin prepararlo.
2. Prepararlo y comprobar que un mensaje vacío o con espacios deja el botón deshabilitado.
3. Editarlo otra vez, escribir un mensaje y hacer commit.
4. Comprobar que el mensaje se limpia y la edición posterior permanece en **CAMBIOS**.
5. Revisar desde la terminal con `git log -1` y `git status`.
6. Probar un error de identidad o un hook que rechace el commit: el mensaje debe conservarse
   y los detalles originales deben estar disponibles.
7. Comprobar la navegación con Tab y el acceso a los paneles en una ventana pequeña.

Para proponer cambios, incluir pasos para reproducir el problema o describir la mejora,
y ejecutar las pruebas que correspondan. La arquitectura se mantiene sencilla para
facilitar su lectura y aprendizaje.
