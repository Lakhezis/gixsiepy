# GixsiePy

**Git a tu ritmo.** Una aplicación de escritorio para trabajar con repositorios Git
mediante una interfaz sencilla, con colores suaves y explicaciones claras.

GixsiePy está escrita en Python y GTK4, y utiliza el Git instalado en el sistema.
Está pensada tanto para aprender los conceptos básicos como para trabajar con
repositorios locales. Su entorno principal es **Debian 13**.

El MVP permite abrir repositorios, preparar archivos, revisar diferencias, crear
commits, sincronizar una rama mediante Pull y Push y consultar su historial reciente.
El proyecto mantiene una arquitectura sencilla para facilitar su lectura y aprendizaje.

## Funciones disponibles

- Abrir una carpeta o una subcarpeta de un repositorio y consultar la rama actual.
- Inicializar un repositorio con confirmación explícita.
- Ver archivos modificados, nuevos, eliminados y preparados para commit.
- Preparar un archivo, quitarlo de staging o preparar todos los cambios.
- Consultar las diferencias de archivos, con colores para las líneas añadidas y eliminadas.
- Crear commits con un mensaje de una o varias líneas.
- Traer cambios con **Pull** y publicar commits con **Push**, confirmando el destino.
- Alternar entre **Cambios** e **Historial** para consultar los commits recientes.
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

## Consultar el historial

Al abrir un repositorio, los botones **Cambios | Historial** aparecen junto a su
nombre. **Cambios** reúne los archivos, el diff y el mensaje del próximo commit.
**Historial** muestra hasta **50 commits** desde la posición actual (`HEAD`), empezando
por los más recientes, con estos datos:

- **Mensaje:** el título o resumen del commit.
- **Autor:** el nombre guardado en el commit.
- **Fecha:** la fecha del autor, con su hora y zona horaria originales.
- **Hash corto:** un identificador que se puede seleccionar y copiar.

El historial sigue la rama actual o el commit consultado si `HEAD` está separado.
Incluye los commits de ambas líneas de desarrollo cuando hay un merge en el historial.
La lista no muestra un gráfico de ramas. Si el repositorio todavía no tiene commits,
aparece una explicación para crear el primero desde **Cambios**.

La lectura se realiza en segundo plano. Cambiar de vista conserva la selección de
archivos y el borrador del mensaje del commit. Después de crear un commit, hacer Pull
o Push, o pulsar **Actualizar**, se vuelve a consultar el historial cuando la vista
está abierta. Si está oculta, se carga al volver a **Historial**.

Los cambios realizados desde la terminal u otra aplicación se consultan con
**Actualizar**. Al abrir otro repositorio, la ventana vuelve a **Cambios** y descarta
el historial anterior. Un error de lectura ofrece acceso a los detalles originales
de Git; **Actualizar** permite volver a intentar.

## Sincronizar con un remoto

Un **remoto** es otro repositorio con el que se intercambian commits. Puede estar en
un servidor, como GitHub o GitLab, o ser un repositorio accesible en otra carpeta.
El nombre habitual es `origin`, aunque se admiten otros nombres. Esta versión de
GixsiePy trabaja con **un único remoto configurado**.

Si el repositorio todavía no tiene remoto, agregarlo desde una terminal en su carpeta.
Reemplazar la dirección de este ejemplo por la del repositorio de destino:

```bash
git remote add origin "https://example.com/usuario/proyecto.git"
```

Después, pulsar **Actualizar** en GixsiePy. El resumen del repositorio muestra el
remoto y, cuando existe, la rama de seguimiento o *upstream*: la rama remota con la
que se sincroniza la rama local.

### Enviar commits con Push

1. Crear los commits que se desea publicar.
2. Pulsar **↑ Push** y revisar la rama local y el destino en la confirmación.
3. Confirmar con **Hacer Push**. La ventana muestra que la operación está en curso.

Cuando todavía no existe seguimiento, el primer Push propone publicar la rama con
el mismo nombre en el remoto y establecer su upstream. Esa configuración se guarda
si el envío tiene éxito. Si ya hay seguimiento, se utiliza su destino, incluso si el
nombre de la rama remota difiere del local.

Push envía los commits; los archivos sin preparar y el borrador del mensaje quedan
en el equipo. Se publica únicamente la rama confirmada, sin force push, envío de
tags ni publicación de otras ramas.

### Traer cambios con Pull

1. Guardar en commits los cambios pendientes, incluidos los archivos nuevos.
2. Pulsar **↓ Pull** y revisar el origen y la rama local.
3. Confirmar con **Hacer Pull**. Al terminar se actualizan la rama y los archivos.

Pull necesita una rama activa con commits, un único remoto, seguimiento configurado
y una carpeta de trabajo sin cambios pendientes. Utiliza **avance rápido** (*fast-forward*):
la rama local se mueve hacia los commits del remoto sin crear un commit de merge ni
reescribir commits mediante rebase.

Si las ramas divergen, Git detiene la operación y la aplicación muestra el error.
La divergencia se resuelve desde la terminal u otra herramienta. También se detiene
si un archivo local ignorado sería sobrescrito por un archivo del remoto.

Las confirmaciones se pueden cancelar. La aplicación vuelve a comprobar la rama y
el destino antes de ejecutar; si cambiaron mientras se confirmaba, pide repetir la
acción. Mientras Git trabaja, los botones se desactivan para evitar acciones duplicadas.

Después de una operación exitosa, **Detalles de Pull** o **Detalles de Push** permite
consultar la salida original de Git, incluido el aviso de que todo estaba actualizado.
Los errores muestran una explicación y sus detalles originales. Si la sincronización
se completó pero falla la consulta posterior, la aplicación distingue ambos resultados
y ofrece actualizar la vista manualmente.

### Autenticación y conexión

La autenticación utiliza los mecanismos existentes de Git, como un gestor de
credenciales para HTTPS o una clave disponible en el agente SSH. GixsiePy no incluye
un formulario de contraseñas ni guarda credenciales. Si el acceso requiere una
configuración inicial o aceptar la identidad de un servidor SSH, realizar ese paso
desde la terminal y después volver a intentar en la aplicación.

Las operaciones de red tienen un límite de **120 segundos**. Ante un timeout o una
interrupción de la conexión, consultar el estado local y remoto antes de repetir el
envío: el servidor podría haber recibido los commits aunque no llegara la respuesta.

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

## Alcance del MVP

| Etapa | Función | Estado |
| --- | --- | --- |
| 1 | Abrir e inicializar repositorios | Disponible |
| 2 | Estado de archivos y staging | Disponible |
| 3 | Diff de cambios locales y preparados | Disponible |
| 4 | Crear commits | Disponible |
| 5 | Pull y push | Disponible |
| 6 | Historial de commits recientes | Disponible |

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
│   ├── commit_panel.py
│   └── history_panel.py
├── styles/
│   └── style.css
├── assets/
│   └── flower-pattern.svg
├── tests/
│   ├── test_git_service.py
│   ├── test_sync.py
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
| `ui/history_panel.py` | Mostrar los commits recientes, su estado de carga y los errores de lectura. |
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

El historial utiliza `git log --max-count=50 --topo-order` con un formato fijo para
hash corto (`%h`), resumen (`%s`), autor (`%an`) y fecha ISO 8601 (`%aI`). Los campos
y registros se separan con bytes nulos, para conservar espacios y tabulaciones sin
confundirlos con separadores. Se solicitan textos UTF-8 y se desactivan parches,
colores, notas, decoraciones y verificación de firmas en esta lectura. Referencia:
[git log](https://git-scm.com/docs/git-log).

La sincronización consulta `git remote`, `git config --get-all` y `git remote get-url`
antes de confirmar. Verifica la referencia de destino con `git check-ref-format`.
Pull utiliza `git pull --ff-only --no-rebase --no-autostash` con el remoto y la rama
explícitos. Push utiliza `git push` con un refspec explícito y añade `--set-upstream`
solo para el primer envío sin seguimiento. Referencias:
[git pull](https://git-scm.com/docs/git-pull/2.47.1) y
[git push](https://git-scm.com/docs/git-push).

Se desactivan la recursión de submódulos, el envío automático de tags y el pruning.
Solo para esa ejecución se anula el modo mirror del remoto y se limitan las opciones
de merge de la rama para proteger archivos ignorados. Estos ajustes no cambian los
archivos de configuración del usuario. Los hooks de Git siguen ejecutándose.

Las operaciones se serializan y sus botones se desactivan mientras Git trabaja.
Un segundo trabajador permite cargar diffs o el historial de la vista activa y
descartar resultados de selecciones o repositorios anteriores. El historial se conserva
al cambiar de vista y se invalida al actualizar el repositorio. GTK recibe las
actualizaciones mediante `GLib.idle_add`. Las consultas y
operaciones locales tienen un límite de 30 segundos por comando; Pull y Push tienen
120 segundos. Los prompts de Git por terminal se desactivan. Para SSH se utiliza
`BatchMode=yes` cuando no hay un comando SSH personalizado en el entorno ni en
`core.sshCommand`; si existe, se conserva. La ventana pide esperar antes de cerrar
durante una operación del repositorio.

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
Las pruebas del historial verifican sus metadatos, el límite de 50 commits, ramas,
merges, actualización después de commit y sincronización, conservación de borradores,
lecturas lentas y descarte de resultados anteriores.
`test_sync.py` utiliza remotos bare locales: verifica el primer Push, Pull con avance
rápido, divergencias, ramas con distintos nombres, archivos ignorados y configuración
de push especial. Las pruebas de sincronización no necesitan acceso a Internet.

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

### Comprobación manual de Pull y Push

Utilizar dos carpetas de prueba que compartan un remoto, preferentemente un repositorio
bare local creado con `git init --bare`:

1. Abrir un repositorio sin remoto y comprobar que Pull y Push están deshabilitados.
2. Configurar un remoto, actualizar y cancelar el primer Push: el remoto debe seguir intacto.
3. Confirmar el primer Push y verificar que se publica la rama y se establece su upstream.
4. Publicar un commit desde la segunda carpeta y traerlo con Pull desde la primera.
5. Crear commits distintos en ambas carpetas: el Push debe rechazarse y Pull debe explicar
   que las ramas divergen, sin iniciar un merge ni un rebase.
6. Revisar los detalles de una operación exitosa y de un error, y comprobar que la ventana
   sigue respondiendo mientras Git trabaja.

### Comprobación manual del historial

1. Abrir un repositorio y alternar entre **Cambios** e **Historial**.
2. Comparar los mensajes, autores, fechas y hashes con `git log` desde la terminal.
3. Escribir un borrador y seleccionar un archivo en **Cambios**; consultar el historial
   y volver. El borrador y la selección deben conservarse.
4. Crear un commit y comprobar que aparece al volver a **Historial**.
5. Crear un commit desde la terminal y pulsar **Actualizar** con el historial abierto.
6. Cambiar de repositorio y comprobar que no aparecen commits del anterior.
7. Abrir un repositorio sin commits y revisar su mensaje de bienvenida al historial.
8. Revisar el desplazamiento de la lista, copiar un hash y navegar con Tab.

Para proponer cambios, incluir pasos para reproducir el problema o describir la mejora,
y ejecutar las pruebas que correspondan. La arquitectura se mantiene sencilla para
facilitar su lectura y aprendizaje.
