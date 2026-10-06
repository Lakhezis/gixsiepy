<!--
SPDX-FileCopyrightText: 2026 GixsiePy contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Guía de uso

[Volver al README](../README.md) · [Desarrollo](DEVELOPMENT.md)

Esta guía describe el trabajo con repositorios, la sincronización y los errores habituales.
Para instalar la aplicación, consultar el [README](../README.md#instalación).

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

## Instalación para un solo usuario

Descargar el código y, desde la carpeta del proyecto, ejecutar como el usuario habitual:

```bash
/usr/bin/python3 install.py
```

El instalador comprueba las dependencias y copia la aplicación a una carpeta propia.
Después se puede buscar **GixsiePy** en el menú de aplicaciones de Debian y agregarla
a favoritos. Incluye un ícono floral SVG propio, con los colores de la interfaz.
La instalación es solo para el usuario actual y se realiza **sin sudo**.

También se puede abrir desde la terminal:

```bash
~/.local/bin/gixsiepy
```

Si `~/.local/bin` está incluido en `PATH`, alcanza con ejecutar `gixsiepy`.
Si el menú todavía no muestra la entrada nueva, cerrar y volver a iniciar la sesión.

### Archivos instalados

| Ubicación predeterminada | Contenido |
| --- | --- |
| `~/.local/share/gixsiepy/` | Código, estilos, imágenes, README e instalador. |
| `~/.local/bin/gixsiepy` | Lanzador que utiliza `/usr/bin/python3`. |
| `~/.local/share/applications/org.gixsie.GixsiePy.desktop` | Entrada del menú de aplicaciones. |
| `~/.local/share/icons/hicolor/scalable/apps/org.gixsie.GixsiePy.svg` | Ícono de la aplicación. |

Si `XDG_DATA_HOME` contiene una ruta absoluta, se utiliza en lugar de
`~/.local/share`. La copia instalada funciona independientemente de la carpeta
original: moverla o quitarla no rompe el acceso del menú. No se copian `.git`, las
pruebas, entornos virtuales ni archivos temporales.

El instalador guarda un registro de los archivos que creó. Si encuentra un archivo
ajeno con el mismo nombre, o un archivo instalado modificado manualmente, detiene
la operación e indica cuál es. Para continuar, conservar una copia y mover ese
archivo. Los cambios al código conviene realizarlos en la carpeta del proyecto.

La organización de los archivos sigue las especificaciones
[XDG](https://specifications.freedesktop.org/basedir/latest/),
[Desktop Entry](https://specifications.freedesktop.org/desktop-entry/latest/) e
[Icon Theme](https://specifications.freedesktop.org/icon-theme/latest/).

### Actualizar o desinstalar

Para actualizar, cerrar GixsiePy, descargar o actualizar el código y volver a ejecutar:

```bash
/usr/bin/python3 install.py
```

Para desinstalar desde la carpeta del proyecto:

```bash
/usr/bin/python3 install.py --uninstall
```

También se puede desinstalar sin conservar el proyecto original:

```bash
/usr/bin/python3 ~/.local/share/gixsiepy/install.py --uninstall
```

Si se utiliza `XDG_DATA_HOME`, ajustar esa última ruta a la carpeta elegida.
Cerrar la aplicación antes de desinstalar. Se quitan los archivos registrados y la
entrada del menú; los repositorios Git y cualquier archivo ajeno se conservan.
Las dependencias del sistema siguen instaladas.

