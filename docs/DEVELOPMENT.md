<!--
SPDX-FileCopyrightText: 2026 GixsiePy contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Desarrollo

[Volver al README](../README.md) · [Guía de uso](USAGE.md)

El proyecto utiliza Python 3, GTK4 y PyGObject. GitService concentra las operaciones
Git; los widgets GTK presentan sus resultados. Las dependencias y el inicio desde
el código se describen en el [README](../README.md#ejecutar-desde-el-código-fuente).

## Arquitectura

La lógica Git está separada de la interfaz:

```text
GTK UI → GitService → subprocess → Git → Repositorio
```

```text
gixsiePy/
├── main.py
├── install.py
├── packaging/
│   ├── build_deb.py
│   ├── control.in
│   └── org.gixsie.GixsiePy.desktop.in
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
│   ├── flower-pattern.svg
│   └── org.gixsie.GixsiePy.svg
├── tests/
│   ├── test_git_service.py
│   ├── test_sync.py
│   ├── test_installation.py
│   ├── test_deb.py
│   └── test_ui.py
├── docs/
│   ├── USAGE.md
│   └── DEVELOPMENT.md
├── README.md
├── LICENSE
└── COPYRIGHT
```

| Archivo | Responsabilidad |
| --- | --- |
| `main.py` | Iniciar GTK y cargar los estilos. |
| `install.py` | Instalar, actualizar y desinstalar la copia del usuario. |
| `packaging/build_deb.py` | Construir el archivo .deb sin instalarlo en el equipo. |
| `packaging/control.in` | Declarar nombre, versión y dependencias del paquete Debian. |
| `packaging/org.gixsie.GixsiePy.desktop.in` | Definir la entrada del menú; el instalador completa la ruta de ejecución. |
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
| `assets/org.gixsie.GixsiePy.svg` | Identificar la aplicación en el menú y las ventanas. |
| `tests/` | Verificar Git y los flujos de la interfaz con repositorios temporales. |
| `docs/` | Mantener las guías de uso y desarrollo enlazadas desde el README. |
| `LICENSE` | Conservar el texto completo de la GNU GPL versión 3. |
| `COPYRIGHT` | Declarar la autoría, el alcance y la elección GPL-3.0-or-later. |

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

## Pruebas automatizadas

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
`test_installation.py` comprueba instalación, actualización, desinstalación,
protección de archivos ajenos y rutas con espacios o caracteres especiales, siempre
en carpetas temporales. También inicia la copia instalada en un proceso GTK separado
cuando se habilitan las pruebas gráficas. La validación adicional del archivo `.desktop`
utiliza `desktop-file-validate` si está disponible; no es una dependencia de la aplicación.
`test_deb.py` construye y extrae el paquete en carpetas temporales, verifica metadatos,
contenido, permisos, checksums y reproducibilidad. Su prueba gráfica inicia el código
extraído en un proceso nuevo. Las pruebas no instalan el paquete en el sistema.

## Comprobación manual del flujo de commit

En un repositorio de prueba:

1. Crear o modificar un archivo; comprobar que no se puede hacer commit sin prepararlo.
2. Prepararlo y comprobar que un mensaje vacío o con espacios deja el botón deshabilitado.
3. Editarlo otra vez, escribir un mensaje y hacer commit.
4. Comprobar que el mensaje se limpia y la edición posterior permanece en **CAMBIOS**.
5. Revisar desde la terminal con `git log -1` y `git status`.
6. Probar un error de identidad o un hook que rechace el commit: el mensaje debe conservarse
   y los detalles originales deben estar disponibles.
7. Comprobar la navegación con Tab y el acceso a los paneles en una ventana pequeña.

## Comprobación manual de Pull y Push

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

## Comprobación manual del historial

1. Abrir un repositorio y alternar entre **Cambios** e **Historial**.
2. Comparar los mensajes, autores, fechas y hashes con `git log` desde la terminal.
3. Escribir un borrador y seleccionar un archivo en **Cambios**; consultar el historial
   y volver. El borrador y la selección deben conservarse.
4. Crear un commit y comprobar que aparece al volver a **Historial**.
5. Crear un commit desde la terminal y pulsar **Actualizar** con el historial abierto.
6. Cambiar de repositorio y comprobar que no aparecen commits del anterior.
7. Abrir un repositorio sin commits y revisar su mensaje de bienvenida al historial.
8. Revisar el desplazamiento de la lista, copiar un hash y navegar con Tab.

## Construir el paquete Debian

Se necesitan Python 3 y `dpkg-deb`, incluido en `dpkg` en Debian. No hace falta
instalar herramientas de compilación ni usar sudo para construir el paquete:

```bash
/usr/bin/python3 packaging/build_deb.py
```

El resultado se guarda en `dist/` junto con un archivo SHA-256. El paquete declara
`Architecture: all`: contiene código Python y recursos independientes de la arquitectura.
Debian instala las dependencias para la arquitectura del equipo.

La versión inicial es `0.1.0-1`. Para generar otra versión:

```bash
/usr/bin/python3 packaging/build_deb.py --version 0.1.1-1
```

La mantenedora predeterminada es `Mina (Lakhezis) <silvina@tocci.ar>`.
Para construir un paquete con otros datos, utilizar la opción
`--maintainer "Nombre <correo@example.com>"`.
Los archivos generados no se guardan en Git. El constructor admite `SOURCE_DATE_EPOCH`
y normaliza fechas, permisos y propietarios para generar paquetes reproducibles.
No incluye instaladores que se ejecuten como root, hooks Git ni scripts de mantenimiento.

Referencias: [dpkg-deb en Debian 13](https://manpages.debian.org/trixie/dpkg/dpkg-deb.1.en.html)
y [campos de control de Debian](https://www.debian.org/doc/debian-policy/ch-controlfields.html).

## Preparar una publicación en GitHub

1. Ejecutar las pruebas correspondientes y revisar los cambios.
2. Generar el paquete con la versión y los datos del mantenedor de la publicación.
3. Crear una etiqueta Git que identifique el código utilizado para construirlo.
4. Crear una publicación en [Releases](https://github.com/Lakhezis/gixsiepy/releases)
   con sus notas de versión y adjuntar
   el archivo `.deb` y su archivo `.deb.sha256` generado en `dist/`.

Los binarios se adjuntan a la publicación; `dist/` permanece excluido del repositorio.
GitHub proporciona los archivos del código fuente asociados a la etiqueta.
El código fuente publicado debe corresponder exactamente al paquete y conservar
`LICENSE`, `COPYRIGHT` y los scripts de instalación y construcción, conforme a la GPL.
Los paquetes deben regenerarse si cambia la documentación, ya que incluyen el README
y las guías en `/usr/share/doc/gixsiepy/`. Esa carpeta también contiene `LICENSE`,
`COPYRIGHT` y el archivo `copyright` con el aviso y el texto completo de la licencia.

Referencia: [publicaciones en GitHub](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).
