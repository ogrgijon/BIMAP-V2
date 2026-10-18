<div align="center">

<img src="logo_icon.png" alt="Logotipo de MerekaiBIMAP" width="108">

# MerekaiBIMAP
### Diseñador de mapas para inteligencia empresarial

[English](readme.md) | [Español](README.es.md)

**Convierte datos geográficos en mapas claros y listos para presentar, sin la curva de aprendizaje de un SIG.**

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-green)
![Licencia](https://img.shields.io/badge/licencia-MIT-lightgrey)

[Guía rápida](docs/QUICK_START.md) · [Instalación](docs/INSTALL.md) · [Manual completo](MANUAL.md) · [Versiones](https://github.com/ogrgijon/BIMAP-V2/releases)

<br/>

<img src="bimap_splash.png" alt="MerekaiBIMAP — mapas para inteligencia empresarial" width="500">

</div>

---

## ¿Qué es MerekaiBIMAP?

MerekaiBIMAP ayuda a los equipos a convertir datos empresariales en mapas fáciles de entender. Combina hojas de cálculo, bases de datos, APIs o fuentes en tiempo real; crea el mapa de forma visual y comparte un PDF listo para clientes y compañeros.

**Planifica territorios. Analiza resultados por ubicación. Presenta mapas con claridad.**

## Del dato a un mapa listo para decidir

1. **Elige una ubicación**: busca una dirección o selecciona un mapa base.
2. **Construye el mensaje**: dibuja zonas, añade puntos, etiquetas y datos empresariales.
3. **Prepara la presentación**: configura la página, añade título y leyenda, y exporta un PDF.

Empieza con la [guía rápida](docs/QUICK_START.md) para crear tu primer mapa.

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
Descarga cachés de mapas para una región y un rango de zoom. MerekaiBIMAP puede trabajar sin conexión usando los mosaicos almacenados.

---

## ⚡ Inicio rápido

Consulta la [guía rápida](docs/QUICK_START.md) para seguir el flujo de trabajo dentro de la aplicación.

### Ejecutar desde el código fuente

```bash
# 1. Clona y entra en el proyecto
git clone https://github.com/ogrgijon/BIMAP-V2.git
cd BIMAP-V2

# 2. Crea y activa un entorno virtual
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate       # macOS / Linux

# 3. Instala el proyecto
pip install -e .

# 4. Inicia MerekaiBIMAP
python -m bimap.app
```

Consulta la [guía de instalación](docs/INSTALL.md) para obtener información sobre desarrollo, empaquetado y CI.

---

## 📘 Documentación

| Documento | Descripción |
|----------|-------------|
| [docs/QUICK_START.md](docs/QUICK_START.md) | Guía breve para crear y exportar tu primer mapa |
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

## ⚠️ Estado y seguridad

MerekaiBIMAP es un proyecto experimental compartido para aprendizaje y colaboración; no está preparado para producción y se distribuye sin garantía. No guardes credenciales reales en archivos `.bimap`. Abre únicamente proyectos y extensiones HTML/JavaScript de fuentes confiables: las extensiones se ejecutan al visualizarlas.

Consulta las [notas de seguridad](docs/INSTALL.md#7-security-notes) para obtener más información.

## 📄 Licencia

Licencia MIT. Consulta [LICENSE](LICENSE).

Los datos cartográficos pertenecen a [OpenStreetMap y sus colaboradores](https://www.openstreetmap.org/copyright), bajo licencia [ODbL](https://opendatacommons.org/odbl/).
