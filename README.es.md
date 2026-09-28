<div align="center">

# BIMAP
### Diseñador de mapas para inteligencia empresarial

[English](readme.md) | [Español](README.es.md)

**Convierte tus datos en mapas PDF de calidad profesional, sin necesidad de conocimientos de SIG.**

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-green)
![Licencia](https://img.shields.io/badge/licencia-MIT-lightgrey)

[Inicio rápido](#-inicio-rápido) · [Manual de usuario](MANUAL.md) · [Arquitectura](docs/ARCHITECTURE.md) · [Extensiones](docs/EXTENSIONS.md)

<br/>

![Captura de BIMAP](bimap_splash.png)

</div>

---

## ¿Qué es BIMAP?

BIMAP es una **aplicación de escritorio para Python** que permite a analistas, consultores y equipos de operaciones diseñar mapas basados en datos y exportarlos como documentos PDF profesionales, sin depender de una herramienta SIG ni de un servicio web.

Dibuja territorios. Conecta tus datos. Exporta un PDF.

## Funciones principales

### 🗺️ Lienzo de mapas interactivo
Dibuja directamente sobre mapas de OpenStreetMap. Cambia entre distintos proveedores, busca direcciones y navega hasta cualquier ubicación.

### 📐 Herramientas de dibujo
- **Zonas**: polígonos, rectángulos y círculos con dimensiones métricas.
- **Puntos clave**: marcadores con fichas informativas, imágenes y enlaces.
- **Anotaciones**: textos, llamadas, flecha norte, barras de escala, bloques de título y tablas.
- **Selección por lazo** para gestionar varios elementos a la vez.

### 📊 Integración de datos
Conecta tus mapas con:

- Archivos CSV y Excel.
- Bases de datos PostgreSQL, MySQL y SQLite mediante consultas de solo lectura.
- APIs REST con mapeo de campos JSONPath.
- Archivos o URLs HTTPS GeoJSON.

### 📡 Fuentes en tiempo real
Representa activos en movimiento mediante fuentes REST, iconos configurables, historial de recorridos y actualización periódica.

### 📄 Exportación profesional a PDF
El compositor de mapas permite crear documentos en formatos A4, A3, Letter y Legal, con orientación, DPI, bloques de título, leyendas y tablas de referencias configurables.

### 🌐 Trabajo sin conexión
Descarga cachés de mapas para una región y un rango de zoom. BIMAP puede trabajar sin conexión usando los mosaicos almacenados.

---

## ⚡ Inicio rápido

```bash
# 1. Clona y entra en el proyecto
git clone https://github.com/ogrgijon/BIMAP-V2.git
cd BIMAP-V2

# 2. Crea y activa un entorno virtual
python -m venv .venv
.venv\\Scripts\\activate       # Windows
source .venv/bin/activate       # macOS / Linux

# 3. Instala el proyecto
pip install -e .

# 4. Inicia BIMAP
python -m bimap.app
```

Consulta la [guía de instalación](docs/INSTALL.md) para obtener información sobre desarrollo, empaquetado y CI.

---

## 📘 Documentación

| Documento | Descripción |
|----------|-------------|
| [MANUAL.md](MANUAL.md) | Manual completo de usuario |
| [docs/EXTENSIONS.md](docs/EXTENSIONS.md) | Extensiones HTML5 y referencia de `BIMAP_DATA` |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitectura, tecnologías y decisiones de diseño |
| [docs/INSTALL.md](docs/INSTALL.md) | Instalación, generación del ejecutable y CI |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Guía para contribuir y flujo de pull requests |

---

## 🛠️ Tecnologías

| Capa | Tecnología |
|------|------------|
| Lenguaje | Python 3.11+ |
| Interfaz gráfica | PyQt6 ≥ 6.6 |
| PDF | QPdfWriter incluido en Qt |
| Mapas | OpenStreetMap y cualquier TMS |
| Geocodificación | geopy y Nominatim |
| SQL | SQLAlchemy ≥ 2.0 |
| Modelos | Pydantic ≥ 2.5 |
| Empaquetado | PyInstaller |

---

## ⚠️ Aviso

Este proyecto es un **prototipo experimental de investigación**, compartido para aprendizaje y colaboración. No está preparado para producción y se distribuye sin garantía. No guardes credenciales reales en archivos de proyecto `.bimap`.

Consulta las [notas de seguridad](docs/INSTALL.md#7-security-notes) para obtener más información.

## 📄 Licencia

Licencia MIT. Consulta [LICENSE](LICENSE).

Los datos cartográficos pertenecen a [OpenStreetMap y sus colaboradores](https://www.openstreetmap.org/copyright), bajo licencia [ODbL](https://opendatacommons.org/odbl/).
