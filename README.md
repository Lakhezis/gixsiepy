# GixsiePy

Una interfaz nativa, suave y sencilla para Git, escrita en Python 3 y GTK4.
El desarrollo avanza por etapas. **Implementado: etapa 1, abrir e inicializar repositorios.**

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

## Arquitectura

`main.py` inicia GTK y carga CSS. `ui/window.py` coordina la interfaz y llama a
`GitService` mediante `ui/tasks.py`. `ui/dialogs.py` muestra confirmaciones y errores.
`git/git_service.py` no depende de GTK: ejecuta el Git del sistema con listas de
argumentos y `shell=False`, e interpreta sus resultados.

Los comandos se ejecutan en un trabajador. Los resultados vuelven al hilo principal
con `GLib.idle_add`, porque GTK debe actualizarse únicamente desde ese hilo.
Las acciones se desactivan durante una operación para evitar ejecuciones duplicadas.
Si intentás cerrar mientras Git trabaja, la ventana espera a que termine la acción.
Los comandos de esta etapa tienen un límite de 30 segundos por ejecución.

Los errores de acceso, repositorios dañados o propiedad dudosa no se interpretan como
carpetas nuevas. La aplicación no modifica automáticamente la configuración de seguridad.
Los repositorios bare y la carpeta interna `.git` no son carpetas de trabajo admitidas.

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

## Próximas etapas

2. Estado de archivos, stage y unstage.
3. Diff preparado y sin preparar.
4. Mensaje y creación de commits.
5. Pull y push con remoto, seguimiento y errores visibles.
6. Historial de commits recientes.

Cada etapa se implementa y verifica antes de continuar con la siguiente.
