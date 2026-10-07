<!--
SPDX-FileCopyrightText: 2026 GixsiePy contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# GixsiePy

<img src="assets/org.gixsie.GixsiePy.svg" alt="Ícono de GixsiePy: una flor y una rama Git" width="96" height="96">

**Git a tu ritmo.**

GixsiePy es una aplicación de escritorio nativa para trabajar con Git mediante una
interfaz sencilla, con colores suaves y mensajes claros. Está desarrollada en
**Python 3 y GTK4** y utiliza el Git instalado en el sistema.

El proyecto ofrece las operaciones cotidianas de un repositorio y una arquitectura
legible para facilitar el aprendizaje y las contribuciones. **Debian 13** es la
plataforma de referencia; la interfaz está disponible en español.

## Contenido

- [Características](#características)
- [Instalación](#instalación)
- [Ejecutar desde el código fuente](#ejecutar-desde-el-código-fuente)
- [Uso básico](#uso-básico)
- [Documentación](#documentación)
- [Alcance](#alcance)
- [Contribuir](#contribuir)
- [Desarrollo con IA](#desarrollo-con-ia)
- [Licencia](#licencia)

## Características

- Apertura de repositorios y subcarpetas, con detección de la rama actual.
- Inicialización de Git con confirmación explícita.
- Listas independientes de cambios pendientes y archivos preparados para commit.
- Stage y unstage por archivo, y preparación de todos los cambios.
- Diff de cambios locales y preparados, con líneas añadidas y eliminadas resaltadas.
- Commits con mensajes de una o varias líneas.
- Pull con avance rápido y Push con confirmación del destino.
- Historial de hasta 50 commits, con mensaje, autor, fecha y hash corto.
- Operaciones en segundo plano y acceso a los mensajes originales de Git.

La interfaz incluye un ícono y un patrón floral SVG propios. El visor de diferencias
utiliza una fuente monoespaciada; el resto de la aplicación mantiene una tipografía
sans-serif, con Quicksand como opción preferida.

## Instalación

### Paquete Debian (.deb)

Para instalar una versión publicada, descargar el archivo `.deb` desde la sección
[Releases](https://github.com/Lakhezis/gixsiepy/releases) del repositorio en GitHub.
El archivo `.deb.sha256` permite verificar
la integridad de la descarga.

Desde la carpeta donde se descargaron los archivos, ejecutar estos comandos
(ejemplo para la versión `0.1.0-1`):

```bash
sha256sum -c gixsiepy_0.1.0-1_all.deb.sha256
sudo apt install ./gixsiepy_0.1.0-1_all.deb
```

APT resuelve las dependencias del sistema. El paquete instala la aplicación para
todos los usuarios e incluye el lanzador del menú y el ícono. Después de la
instalación, buscar **GixsiePy** en el menú de aplicaciones o ejecutar:

```bash
gixsiepy
```

Para actualizar, cerrar la aplicación e instalar el paquete de la nueva versión.
Para desinstalar:

```bash
sudo apt remove gixsiepy
```

Los repositorios Git permanecen en sus carpetas al desinstalar la aplicación.
Si aún no hay una publicación disponible, el paquete puede
[construirse desde el código fuente](docs/DEVELOPMENT.md#construir-el-paquete-debian).

Si existe una instalación previa mediante `install.py`, desinstalar esa copia
antes de utilizar el `.deb` para evitar que el menú siga abriendo la versión local:

```bash
/usr/bin/python3 install.py --uninstall
```

### Requisitos

| Componente | Requisito |
| --- | --- |
| Sistema de referencia | Debian 13 con una sesión de escritorio |
| Python | 3.10 o posterior |
| Interfaz | GTK 4.10 o posterior y PyGObject |
| Git | Instalado y disponible en `PATH` |
| Fuente opcional | Quicksand (`fonts-quicksand`) |

La fuente Quicksand se puede instalar con:

```bash
sudo apt install fonts-quicksand
```

Cuando no está disponible, se utiliza una fuente sans-serif del sistema.

## Ejecutar desde el código fuente

El código está disponible en el [repositorio de GitHub](https://github.com/Lakhezis/gixsiepy).
Se puede clonar el repositorio o descargar y extraer el
[archivo ZIP de la rama master](https://github.com/Lakhezis/gixsiepy/archive/refs/heads/master.zip).

Instalar las dependencias en Debian 13:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-4.0 git
```

Para obtener el código mediante Git:

```bash
git clone https://github.com/Lakhezis/gixsiepy.git
cd gixsiepy
```

Desde la carpeta del código fuente, ejecutar:

```bash
/usr/bin/python3 main.py
```

Se utiliza `/usr/bin/python3` para acceder a los bindings de GTK instalados por APT.
No se requieren paquetes de pip ni un entorno virtual. Los estilos y las imágenes
se cargan desde la carpeta del proyecto.

También está disponible una
[instalación para un solo usuario](docs/USAGE.md#instalación-para-un-solo-usuario)
mediante `install.py`, sin permisos de administrador.

## Uso básico

1. Abrir una carpeta con **Abrir carpeta…**. Si no contiene un repositorio, la
   aplicación permite inicializar Git después de confirmar.
2. Seleccionar un archivo en **CAMBIOS** para revisar su diff.
3. Preparar los archivos con **Preparar archivo (Stage)** o **Preparar todos los cambios**.
4. Revisar **PREPARADOS PARA COMMIT**, escribir un mensaje y pulsar **Hacer commit**.
5. Utilizar **Pull** y **Push** para sincronizar los commits con el remoto configurado.
6. Abrir **Historial** para consultar los commits recientes, o pulsar **Actualizar**
   para consultar cambios realizados desde otra aplicación.

Git necesita un nombre y un correo configurados para crear commits. La autenticación
con remotos utiliza los mecanismos existentes de Git, como un gestor de credenciales
o el agente SSH. La configuración y los errores habituales se describen en la
[guía de uso](docs/USAGE.md).

## Documentación

- [Guía de uso](docs/USAGE.md): staging, commits, diffs, historial, sincronización
  y resolución de problemas habituales.
- [Desarrollo](docs/DEVELOPMENT.md): arquitectura, pruebas, construcción del `.deb`
  y preparación de publicaciones.

## Alcance

La versión actual permite trabajar con un único remoto. Pull requiere una rama
con seguimiento configurado y una carpeta de trabajo sin cambios pendientes;
utiliza avance rápido para evitar merges o rebases automáticos.

Los conflictos se muestran en la interfaz, pero se resuelven desde la terminal u
otra herramienta. Los archivos binarios muestran una explicación y los diffs
mayores de 512 KiB o 5000 líneas muestran una vista previa recortada.

La gestión de ramas, clone, rebase, cherry-pick, stash avanzado, tags, resolución
visual de conflictos y gráficos de ramas quedan fuera del alcance actual.
La aplicación no ofrece `reset --hard`, `clean` ni force push.

## Contribuir

Se reciben reportes de errores, propuestas de mejoras, cambios de documentación
y contribuciones de código a través del
[repositorio en GitHub](https://github.com/Lakhezis/gixsiepy).

### Reportar un problema

Antes de abrir un [issue](https://github.com/Lakhezis/gixsiepy/issues), comprobar
si el problema ya fue reportado. Incluir:

- Versión de GixsiePy, distribución y versión de Git.
- Método de instalación: `.deb`, código fuente o instalador de usuario.
- Pasos para reproducir el problema y comportamiento esperado.
- Mensaje de error y detalles originales de Git, si están disponibles.

Los ejemplos reproducibles pueden utilizar repositorios de prueba. Los mensajes y
capturas compartidos deben omitir credenciales y datos privados.

### Proponer un cambio

Los cambios deben conservar la separación entre la interfaz y `GitService`, mantener
el código sencillo y explicar cualquier dependencia nueva. Para cambios importantes,
abrir primero un issue para discutir su alcance.

Las [pull requests](https://github.com/Lakhezis/gixsiepy/pulls) deben describir
el problema, el cambio propuesto y su validación.
Las pruebas se ejecutan desde la carpeta del proyecto:

```bash
/usr/bin/python3 -m unittest discover -v
```

Para incluir las pruebas gráficas, se requiere una sesión de escritorio:

```bash
GIXSIE_RUN_UI_TESTS=1 /usr/bin/python3 -m unittest discover -v
```

Las pruebas de Git, instalación y empaquetado utilizan carpetas temporales. La
[guía de desarrollo](docs/DEVELOPMENT.md) detalla las comprobaciones manuales y
los comandos para generar paquetes.

## Desarrollo con IA

Desarrollé este proyecto con la asistencia de **Codex, una IA de OpenAI**, para
escribir y revisar código, preparar documentación y realizar pruebas. La idea,
la dirección del proyecto y las decisiones finales estuvieron a mi cargo.

## Licencia

GixsiePy es software libre bajo la **GNU General Public License, versión 3 o
cualquier versión posterior** (`GPL-3.0-or-later`). La licencia se aplica al código,
la documentación y los recursos gráficos propios del proyecto; las dependencias
externas conservan sus respectivas licencias.

Se permite utilizar, estudiar, modificar y redistribuir la aplicación, incluso
comercialmente. Al distribuir la aplicación o versiones modificadas, deben
conservarse los avisos de licencia y proporcionarse el código fuente correspondiente
según los términos de la GPL. Las versiones derivadas también deben respetar esta
licencia. La aplicación se distribuye sin garantía.

El texto completo está en [LICENSE](LICENSE) y el aviso de autoría y licencia en
[COPYRIGHT](COPYRIGHT). Las contribuciones al proyecto se reciben bajo esta misma
licencia.
