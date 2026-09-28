"""Simple EN/ES translation support for BIMAP.

Usage
-----
    from bimap.i18n import t, set_language, get_language

    set_language("es")   # or "en"
    label = t("Save")    # → "Guardar"
"""

from __future__ import annotations

_ES: dict[str, str] = {
    # ── Menu bar ────────────────────────────────────────────────────────────
    "File": "Archivo",
    "Edit": "Editar",
    "View": "Vista",
    "Map": "Mapa",
    "Data": "Datos",
    "External Data": "Datos Externos",
    "Help": "Ayuda",

    # ── File menu ────────────────────────────────────────────────────────────
    "New Project": "Nuevo Proyecto",
    "Open…": "Abrir…",
    "Recent Projects": "Proyectos Recientes",
    "Save": "Guardar",
    "Save As…": "Guardar Como…",
    "Import GeoJSON…": "Importar GeoJSON…",
    "📤  Export Data Backup…": "📤  Exportar Copia de Seguridad…",
    "📥  Import Data Backup…": "📥  Importar Copia de Seguridad…",
    "Print / Export PDF…": "Imprimir / Exportar PDF…",
    "Quit": "Salir",

    # ── Unsaved-changes / exit dialogs ──────────────────────────────────────
    "Unsaved Changes": "Cambios sin guardar",
    "You have unsaved changes. Discard them?": "Hay cambios sin guardar. ¿Descartarlos?",
    "Replace Project?": "¿Reemplazar proyecto?",
    "This will replace the current project with the backup.\nUnsaved changes will be lost. Continue?": "Esto reemplazará el proyecto actual con la copia de seguridad.\nSe perderán los cambios sin guardar. ¿Continuar?",

    # ── Edit menu ────────────────────────────────────────────────────────────
    "Undo": "Deshacer",
    "Redo": "Rehacer",
    "Delete Selected": "Eliminar Seleccionado",
    "Draw Polygon Zone": "Dibujar Zona Polígono",
    "Draw Rectangle Zone": "Dibujar Zona Rectángulo",
    "Draw Circle Zone": "Dibujar Zona Círculo",
    "Place Keypoint": "Colocar Punto Clave",
    "Place Text Annotation": "Colocar Anotación de Texto",

    # ── View menu ────────────────────────────────────────────────────────────
    "Save Bookmark…": "Guardar Marcador…",
    "Bookmarks": "Marcadores",

    # ── Map menu ─────────────────────────────────────────────────────────────
    "Search Location…": "Buscar Ubicación…",
    "Zoom In": "Acercar",
    "Zoom Out": "Alejar",
    "Set Delimitation…": "Establecer Delimitación…",
    "Clear Delimitation": "Borrar Delimitación",
    "Place by Coordinates…": "Colocar por Coordenadas…",

    # ── Data menu ────────────────────────────────────────────────────────────
    "Add Data Source…": "Agregar Fuente de Datos…",
    "Add WFS Source…": "Añadir fuente WFS…",
    "Open": "Abrir",
    "🔗  Open: {name}": "🔗  Abrir: {name}",
    "🔗  Open: {name}": "🔗  Abrir: {name}",
    "Refresh All Sources": "Actualizar Todas las Fuentes",
    "Browse OGC Catalog…": "Explorar Catálogo OGC…",
    "Import Source Pack…": "Importar Paquete de Fuentes…",
    "Export Source Pack…": "Exportar Paquete de Fuentes…",

    "📊  Export Elements CSV…": "📊  Exportar Elementos a CSV…",

    # ── OGC Catalog Browser dialog ───────────────────────────────────────────
    "Browse OGC Catalog": "Explorar Catálogo OGC",
    "Catalog endpoint": "Punto de conexión del catálogo",
    "Connect": "Conectar",
    "Search datasets…": "Buscar conjuntos de datos…",
    "No URL": "Sin URL",
    "Enter a catalog URL first.": "Introduzca primero una URL de catálogo.",
    "Searching…": "Buscando…",
    "{n} results": "{n} resultados",
    "Add as WFS Data Source": "Añadir como Fuente de Datos WFS",
    "WFS URL": "URL WFS",
    "Copy this endpoint URL into a new WFS data source:\n\n{url}": (
        "Copie esta URL en una nueva fuente de datos WFS:\n\n{url}"
    ),

    # ── OGC Discover dialog ──────────────────────────────────────────────────
    "Discover {svc} Layers": "Descubrir capas {svc}",
    "Service URL": "URL del servicio",
    "Connect & Discover": "Conectar y Descubrir",
    "Layer Name": "Nombre de capa",
    "Queryable": "Consultable",
    "Feature Type": "Tipo de entidad",
    "Fetching GetCapabilities…": "Obteniendo GetCapabilities…",
    "No layers found.": "No se encontraron capas.",
    "{n} layer(s) found — double-click or select and press OK.": (
        "{n} capa(s) encontrada(s) — doble clic o seleccionar y Aceptar."
    ),
    "Connection Error": "Error de conexión",
    "Enter a service URL first.": "Introduzca primero una URL de servicio.",
    "🔍 Discover…": "🔍 Descubrir…",
    "Fetch GetCapabilities and pick a feature type": (
        "Obtener GetCapabilities y elegir un tipo de entidad"
    ),
    "Fetch GetCapabilities and pick a layer": "Obtener GetCapabilities y elegir una capa",

    # ── Source Pack Import dialog ────────────────────────────────────────────    "Import Source Pack": "Importar Paquete de Fuentes",
    "No pack loaded.  Click 'Open Pack…' to begin.": "Sin paquete cargado. Haz clic en 'Abrir paquete…' para empezar.",
    "Open Pack…": "Abrir paquete…",
    "Category:": "Categoría:",
    "All": "Todo",
    "Search:": "Buscar:",
    "name, tag, description…": "nombre, etiqueta, descripción…",
    "Check All": "Marcar todo",
    "Uncheck All": "Desmarcar todo",
    "Service configuration (fixed)": "Configuración del servicio (fijo)",
    "Your parameters": "Tus parámetros",
    "Name in project:": "Nombre en proyecto:",
    "Add This Source ▶": "Agregar esta fuente ▶",
    "Add All Checked ({n})": "Agregar marcadas ({n})",
    "Sources Added": "Fuentes añadidas",
    "{n} data source(s) added to the project.": "{n} fuente(s) de datos añadida(s) al proyecto.",
    "Source Pack Files (*.bsp *.xml);;All Files (*.*)": "Archivos de paquete (*.bsp *.xml);;Todos los archivos (*.*)",

    # ── Source Pack Export dialog ────────────────────────────────────────────
    "Export Source Pack": "Exportar Paquete de Fuentes",
    "Pack information": "Información del paquete",
    "e.g. Spain Open Data": "p.ej. Datos Abiertos España",
    "Pack name": "Nombre del paquete",
    "Author": "Autor",
    "Description": "Descripción",
    "Version": "Versión",
    "License": "Licencia",
    "URL": "URL",
    "Select sources to include": "Seleccionar fuentes a incluir",
    "Nothing selected": "Sin selección",
    "Choose at least one source.": "Elige al menos una fuente.",
    "Save Source Pack": "Guardar Paquete de Fuentes",
    "Source Pack Files (*.bsp);;XML Files (*.xml)": "Archivos de paquete (*.bsp);;Archivos XML (*.xml)",
    "Pack saved": "Paquete guardado",
    "Source pack saved to:\n{path}": "Paquete de fuentes guardado en:\n{path}",
    "No Sources": "Sin fuentes",
    "Add at least one data source to the project before exporting a pack.": "Añade al menos una fuente de datos al proyecto antes de exportar un paquete.",
    "Open Source Pack": "Abrir Paquete de Fuentes",
    "Error": "Error",

    # ── Measurement menu ─────────────────────────────────────────────────────
    "Measurement": "Medición",
    "Start Measuring": "Iniciar Medición",
    "Place Dimension": "Colocar Cota",
    "Place a persistent dimension (click two points)": "Colocar cota persistente (clic en dos puntos)",
    "Clear Measurement": "Limpiar Medición",
    "Cursor / Select": "Cursor / Seleccionar",
    "Pan": "Desplazar",
    "Rotate": "Rotar",
    "Move": "Mover",
    "Lasso Selector": "Selector de Lazo",

    # ── Help menu ────────────────────────────────────────────────────────────
    "About BIMAP": "Acerca de BIMAP",
    "Language": "Idioma",
    "English": "English",
    "Spanish": "Español",
    "Restart required": "Reinicio requerido",
    "Language changed. Please restart BIMAP to apply.": (
        "Idioma cambiado. Por favor reinicie BIMAP para aplicar."
    ),

    # ── Toolbar tooltips ─────────────────────────────────────────────────────
    "Select / move elements": "Seleccionar / mover elementos",
    "Pan the map": "Desplazar el mapa",
    "Dynamic Selector": "Selector Dinámico",
    "Rotate zone (click zone, then ↑/↓ to rotate 1° at a time)": (
        "Rotar zona (clic en zona, luego ↑/↓ para rotar 1° a la vez)"
    ),
    "Move element (click to pick, click to drop)": "Mover elemento (clic para seleccionar, clic para soltar)",
    "Rotation angle — type a value or use ↑/↓ on the map": (
        "Ángulo de rotación — escriba un valor o use ↑/↓ en el mapa"
    ),
    "Measure distance on map (click points, Esc to clear)": (
        "Medir distancia en el mapa (clic para agregar puntos, Esc para borrar)"
    ),
    "Lasso: area-select to batch remove": "Zona Dinámica: selección de área para eliminar en lote",
    "Draw polygon zone": "Dibujar zona polígono",
    "Draw rectangle zone": "Dibujar zona rectángulo",
    "Draw circle zone": "Dibujar zona círculo",
    "Place keypoint marker": "Colocar marcador de punto clave",
    "Place text annotation": "Colocar anotación de texto",
    "Add and configure a new data source": "Añadir y configurar una nueva fuente de datos",
    "Edit the selected data source configuration": "Editar la configuración de la fuente seleccionada",
    "Reload data from the selected source": "Recargar datos de la fuente seleccionada",
    "Remove the selected data source from the project": "Eliminar la fuente seleccionada del proyecto",
    "Check layers and elements to show or hide them; right-click for actions": (
        "Marque capas y elementos para mostrarlos u ocultarlos; clic derecho para ver acciones"
    ),
    "Check data layers to show or hide them; adjust opacity with the slider": (
        "Marque capas de datos para mostrarlas u ocultarlas; ajuste la opacidad con el deslizador"
    ),
    "Fill color used inside the zone": "Color de relleno usado dentro de la zona",
    "Fill opacity from transparent to opaque": "Opacidad del relleno, de transparente a opaco",
    "Color of the zone border": "Color del borde de la zona",
    "Border width in pixels (0 to 20)": "Anchura del borde en píxeles (de 0 a 20)",
    "Label font size in points (6 to 72)": "Tamaño de fuente de la etiqueta en puntos (de 6 a 72)",
    "Label text color": "Color del texto de la etiqueta",
    "Background color behind the label text": "Color de fondo detrás del texto de la etiqueta",
    "Horizontal label offset in pixels; positive values move right": (
        "Desplazamiento horizontal de la etiqueta en píxeles; los valores positivos mueven a la derecha"
    ),
    "Vertical label offset in pixels; positive values move down": (
        "Desplazamiento vertical de la etiqueta en píxeles; los valores positivos mueven hacia abajo"
    ),
    "Column whose value will be displayed or aggregated": "Columna cuyo valor se mostrará o agregará",
    "Optional source field used to match this element": "Campo opcional de la fuente usado para coincidir con este elemento",
    "Value to match; supports {{element.name}} and {{element.id}}": "Valor a coincidir; admite {{element.name}} y {{element.id}}",
    "How multiple matching source values are combined": "Cómo se combinan varios valores coincidentes de la fuente",
    "Metadata attribute name": "Nombre del atributo de metadatos",
    "Metadata attribute value": "Valor del atributo de metadatos",
    "Add this metadata attribute": "Añadir este atributo de metadatos",
    "Delete the selected metadata attributes": "Eliminar los atributos de metadatos seleccionados",
    "Namespace-qualified WFS feature type to request": "Tipo de entidad WFS cualificado por espacio de nombres que se solicitará",
    "Maximum number of features requested from the service": "Número máximo de entidades solicitadas al servicio",
    "Optional bbox as minx,miny,maxx,maxy; leave empty when using viewport tracking": "BBox opcional como minx,miny,maxx,maxy; déjelo vacío al usar el seguimiento de la vista",
    "Optional OGC CQL filter expression sent to the WFS service": "Expresión de filtro CQL de OGC opcional enviada al servicio WFS",
    "File Path": "Ruta del archivo",
    "Sheet": "Hoja",
    "Sheet name or index (default: 0)": "Nombre o índice de hoja (predeterminado: 0)",
    "Connection": "Conexión",
    "Query": "Consulta",
    "Data Path": "Ruta de datos",
    "Auth Token": "Token de autenticación",
    "Source": "Fuente",
    "WFS URL": "URL de WFS",
    "Feature Type": "Tipo de entidad",
    "Max Features": "Máximo de entidades",
    "Bounding Box": "Cuadro delimitador",
    "CQL Filter": "Filtro CQL",
    "Open File": "Abrir archivo",
    "All Files (*.*)": "Todos los archivos (*.*)",
    "e.g. postgresql://user:pass@host/db": "p.ej. postgresql://usuario:contraseña@servidor/bd",
    "SELECT * FROM table": "SELECT * FROM tabla",
    "Local path or https://…": "Ruta local o https://…",
    "URL of a WFS service exposing GetCapabilities": "URL de un servicio WFS que expone GetCapabilities",
    "Retrieve the available feature types from this service": "Obtener los tipos de entidad disponibles de este servicio",
    "CSW catalog endpoint used to search datasets": "Punto de conexión del catálogo CSW usado para buscar conjuntos de datos",
    "Connect to the catalog endpoint": "Conectar con el punto de conexión del catálogo",
    "Search the connected catalog by title or keywords": "Buscar en el catálogo conectado por título o palabras clave",
    "Search the catalog": "Buscar en el catálogo",
    "Create a WFS data source from the selected catalog record": "Crear una fuente de datos WFS a partir del registro seleccionado",
    "Add a live data feed": "Añadir un feed de datos en vivo",
    "Edit the selected live feed configuration": "Editar la configuración del feed en vivo seleccionado",
    "Pause or resume polling for the selected live feed": "Pausar o reanudar la consulta del feed en vivo seleccionado",
    "Remove the selected live feed": "Eliminar el feed en vivo seleccionado",
    "Refresh the debug log contents": "Actualizar el contenido del registro de depuración",
    "Clear the debug log": "Borrar el registro de depuración",
    "Copy the complete debug log to the clipboard": "Copiar todo el registro de depuración al portapapeles",
    "Assign #": "Asignar n.º",
    "Clear #": "Borrar n.º",
    "Assign the next number to the selected key point": "Asignar el siguiente número al punto clave seleccionado",
    "Clear the number from the selected key point": "Borrar el número del punto clave seleccionado",
    "Import HTML from a saved extension library template": "Importar HTML desde una plantilla guardada de la biblioteca de extensiones",
    "Inject current data and open in the system browser": "Inyectar los datos actuales y abrirlos en el navegador del sistema",
    "min": "mín.",
    "max": "máx.",
    "Export all zones and keypoints as a GeoJSON file": "Exportar todas las zonas y puntos clave como archivo GeoJSON",
    "Save a portable backup file you can transfer to another PC": "Guardar una copia portátil que pueda transferir a otro equipo",
    "Load a backup or .bimap file and replace the current project": "Cargar una copia o archivo .bimap y reemplazar el proyecto actual",
    "Export all zones and keypoints with their attributes to CSV": "Exportar todas las zonas y puntos clave con sus atributos a CSV",
    "Download and cache map tiles for the current region so the map works without internet access": "Descargar y guardar en caché los mosaicos de la región actual para usar el mapa sin internet",
    "Open the HTML5/CSS/JS Extension Library manager": "Abrir el gestor de la biblioteca de extensiones HTML5/CSS/JS",
    "Design forms to fill in on zones and keypoints": "Diseñar formularios para completar en zonas y puntos clave",
    "Connect to an OGC WFS service and add a feature layer": "Conectar a un servicio OGC WFS y añadir una capa de entidades",
    "Search an OGC CSW catalogue (e.g. IDEE Spain) and add WFS layers as data sources": "Buscar en un catálogo OGC CSW (p.ej. IDEE España) y añadir capas WFS como fuentes de datos",
    "Open a .bsp source pack file and add its entries as data sources": "Abrir un paquete de fuentes .bsp y añadir sus entradas como fuentes de datos",
    "Bundle selected project data sources into a shareable .bsp pack file": "Agrupar las fuentes de datos seleccionadas en un paquete .bsp compartible",
    "Element name; changing it can also update the label text": (
        "Nombre del elemento; al cambiarlo también puede actualizar el texto de etiqueta"
    ),
    "Visible label text; changing it can also update the element name": (
        "Texto de etiqueta visible; al cambiarlo también puede actualizar el nombre del elemento"
    ),
    "Update label text?": "¿Actualizar texto de etiqueta?",
    "Update the label text to match the new name?": (
        "¿Actualizar el texto de etiqueta para que coincida con el nuevo nombre?"
    ),
    "Update name?": "¿Actualizar nombre?",
    "Update the name to match the new label text?": (
        "¿Actualizar el nombre para que coincida con el nuevo texto de etiqueta?"
    ),

    # ── Search bar ───────────────────────────────────────────────────────────
    "Search location…": "Buscar ubicación…",
    "Search location (Enter)": "Buscar ubicación (Enter)",
    "Search": "Buscar",
    "  Map: ": "  Mapa: ",
    "Tile provider": "Proveedor de mosaicos",
    "Zoom in  [ + ]": "Acercar  [ + ]",
    "Zoom out  [ - ]": "Alejar  [ - ]",

    # ── Dock widget titles ───────────────────────────────────────────────────
    "Layers": "Capas",
    "Properties": "Propiedades",
    "Panel Help": "Ayuda del panel",
    "Application Help": "Ayuda de la aplicación",
    "Open help for this panel": "Abrir la ayuda de este panel",
    "Open help for this window": "Abrir la ayuda de esta ventana",
    "Layers panel help": (
        "<h2>Panel de Capas</h2>"
        "<p>Organiza los elementos del mapa por capas. Haz clic en una zona, punto clave o anotación para seleccionarlo y abrir sus propiedades.</p>"
        "<p>Usa las casillas para mostrar u ocultar capas y elementos. Puedes arrastrar un elemento a otra capa y abrir acciones adicionales con el botón derecho.</p>"
        "<p>La sección de capas de datos muestra fuentes WFS, CSV o API. Ajusta su opacidad, visibilidad y acciones desde el menú contextual.</p>"
    ),
    "Data Sources panel help": (
        "<h2>Panel de Fuentes de Datos</h2>"
        "<p>Aquí se configuran las conexiones que aportan información externa al proyecto, como WFS, GeoJSON, CSV, Excel, API REST, SQL o Google Sheets.</p>"
        "<p><b>Añadir:</b> crea y configura una fuente. <b>Editar:</b> modifica su conexión. <b>Actualizar:</b> vuelve a cargar los datos.</p>"
        "<p><b>Ir a:</b> encuadra en el mapa la extensión de la fuente. El punto de estado indica si la última carga fue correcta, está en curso o produjo un error.</p>"
    ),
    "Live Feeds panel help": (
        "<h2>Panel de Feeds en Vivo</h2>"
        "<p>Gestiona capas que consultan datos periódicamente y actualizan sus elementos en el mapa.</p>"
        "<p><b>Añadir:</b> configura un feed. <b>Editar:</b> cambia su URL, intervalo o filtros. <b>Pausar/Reanudar:</b> detiene o continúa la consulta automática.</p>"
        "<p>El punto de color indica el estado del feed y el número entre paréntesis muestra cuántos elementos se han recibido. Haz doble clic o usa el menú contextual para acciones rápidas.</p>"
    ),
    "Key Points panel help": (
        "<h2>Panel de Puntos Clave</h2>"
        "<p>Lista todos los puntos clave del proyecto y muestra su número asignado cuando existe.</p>"
        "<p>Selecciona un punto para centrarlo en el mapa. <b>Asignar n.º</b> le da el siguiente número disponible para usarlo en leyendas o documentos. <b>Borrar n.º</b> elimina esa numeración.</p>"
        "<p>Para editar título, notas, icono, posición y metadatos, usa el panel <b>Propiedades</b> del punto seleccionado.</p>"
    ),
    "Properties Help": "Ayuda de Propiedades",
    "Open contextual help for the Properties panel": "Abrir ayuda contextual del panel de Propiedades",
    "Properties help with no selection": (
        "<h2>Panel de Propiedades</h2>"
        "<p>Selecciona una zona, un punto clave, una anotación o un elemento de datos en el mapa o en el panel Capas para ver sus propiedades.</p>"
        "<p>Los cambios se aplican al terminar de editar cada campo. Usa la pestaña <b>Metadatos</b> para añadir información libre, controlar su visibilidad y vincular valores a fuentes de datos.</p>"
    ),
    "Properties help for zones": (
        "<h2>Propiedades de zonas</h2>"
        "<p><b>Nombre y grupo:</b> identifican la zona y ayudan a organizarla.</p>"
        "<p><b>Relleno y borde:</b> controlan su apariencia en el mapa. La opacidad permite ver elementos situados debajo.</p>"
        "<p><b>Etiqueta:</b> define el texto, fuente, tamaño, color y posición del rótulo. El nombre y la etiqueta pueden mantenerse sincronizados cuando los cambias.</p>"
        "<p><b>Geometría:</b> ajusta radio, ancho, alto y rotación según el tipo de zona. Las medidas están expresadas en metros.</p>"
        "<p><b>Relleno SVG:</b> permite usar un patrón vectorial en lugar de un color plano. La pestaña <b>Metadatos</b> contiene extensiones, formularios y atributos adicionales.</p>"
    ),
    "Properties help for key points": (
        "<h2>Propiedades de puntos clave</h2>"
        "<p><b>Título, subtítulo y notas:</b> forman el contenido de la ficha informativa del punto.</p>"
        "<p><b>URL:</b> añade un enlace asociado que puede abrirse desde la ficha.</p>"
        "<p><b>Pin, icono y tamaño:</b> controlan cómo se representa el punto en el mapa. Puedes elegir un icono incluido o cargar una imagen.</p>"
        "<p><b>Latitud y longitud:</b> definen la posición geográfica exacta. La pestaña <b>Metadatos</b> permite añadir atributos, formularios y extensiones.</p>"
    ),
    "Properties help for annotations": (
        "<h2>Propiedades de anotaciones</h2>"
        "<p><b>Texto:</b> es el contenido que se muestra en la anotación.</p>"
        "<p><b>Tamaño y color del texto:</b> controlan la legibilidad del contenido.</p>"
        "<p><b>Fondo:</b> define el color de la caja de la anotación. La pestaña <b>Metadatos</b> permite guardar información adicional.</p>"
    ),
    "Properties help for data features": (
        "<h2>Propiedades de elementos de datos</h2>"
        "<p>Esta vista muestra información proporcionada por una fuente WFS, CSV o API. El origen, el tipo geométrico y las coordenadas describen el elemento seleccionado.</p>"
        "<p>La tabla de atributos permite consultar los valores recibidos. Para cambiar la fuente, sus filtros o su actualización, usa el panel <b>Fuentes de Datos</b>.</p>"
    ),
    "Data Layers help": (
        "<h2>Capas de Datos</h2>"
        "<p>Esta sección muestra las capas creadas a partir de fuentes externas, como WFS, CSV o API. Cada fila representa una fuente cargada en el mapa.</p>"
        "<p>Usa la casilla para mostrar u ocultar una capa. El control de opacidad ajusta cuánto se ve sobre el mapa base. El menú contextual permite editar la fuente o realizar acciones relacionadas.</p>"
        "<p>Si una capa no contiene datos visibles, revisa su extensión, filtros y estado de actualización en <b>Fuentes de Datos</b>.</p>"
    ),
    "Map tools help": (
        "<h2>Herramientas del mapa</h2>"
        "<p><b>Seleccionar:</b> elige elementos para ver o editar sus propiedades. <b>Desplazar:</b> mueve el mapa sin modificar elementos.</p>"
        "<p><b>Girar:</b> rota una zona seleccionada. <b>Mover:</b> cambia la posición de un elemento. <b>Selector dinámico:</b> selecciona elementos según una región o criterio.</p>"
        "<p><b>Medir:</b> calcula distancias entre puntos del mapa. <b>Dibujar:</b> crea zonas poligonales, rectangulares o circulares, puntos clave y anotaciones de texto.</p>"
        "<p><b>Cuadrícula:</b> ayuda a mover elementos con precisión. <b>Importar:</b> carga GeoJSON. <b>PDF:</b> abre la exportación o impresión del proyecto.</p>"
        "<p>La barra de búsqueda localiza lugares y el selector <b>Map</b> cambia el proveedor de teselas.</p>"
    ),
    "Data Source window help": (
        "<h2>Fuente de datos</h2><p>Define el nombre, tipo y conexión de una fuente externa.</p>"
        "<p>Configura la actualización automática o manual. En fuentes WFS puedes descubrir tipos, filtros y límites de consulta. Usa <b>Aceptar</b> para guardar la conexión.</p>"
    ),
    "Export PDF window help": (
        "<h2>Exportar PDF</h2><p>Elige tamaño, orientación y resolución del documento.</p>"
        "<p>Indica una ruta de salida para generar un PDF con el mapa, leyenda, elementos y tabla de puntos clave del proyecto.</p>"
    ),
    "Search Location window help": (
        "<h2>Buscar ubicación</h2><p>Escribe una dirección o nombre de lugar y pulsa Buscar.</p>"
        "<p>Selecciona un resultado para centrar el mapa. La búsqueda utiliza un servicio de geocodificación y necesita conexión a Internet.</p>"
    ),
    "Place by Coordinates window help": (
        "<h2>Colocar por coordenadas</h2><p>Elige entre colocar un punto clave o crear una zona con vértices.</p>"
        "<p>Para un punto, introduce latitud y longitud. Para una zona, escribe un vértice por línea con el formato <b>lat, lon</b>; se necesitan al menos tres.</p>"
    ),
    "Set Delimitation window help": (
        "<h2>Delimitación</h2><p>Busca una ciudad, provincia, país u otro límite administrativo.</p>"
        "<p>Selecciona un resultado con polígono para aplicarlo al mapa. Usa <b>Borrar delimitación</b> para quitar el límite actual.</p>"
    ),
    "Live Feed window help": (
        "<h2>Feed en vivo</h2><p>Configura la URL, formato, filtros e intervalo de consulta de una capa actualizada automáticamente.</p>"
        "<p>La pestaña de estilo controla la apariencia de los elementos recibidos. Pausar el feed detiene las consultas sin eliminar su configuración.</p>"
    ),
    "Offline Map window help": (
        "<h2>Mapa sin conexión</h2><p>Descarga y guarda teselas del área seleccionada para utilizarlas sin conexión.</p>"
        "<p>Define los límites y niveles de zoom. Usa <b>Estimar teselas</b> para comprobar el tamaño de la descarga antes de iniciarla.</p>"
    ),
    "Discover WFS window help": (
        "<h2>Descubrir capas WFS</h2><p>Introduce la URL de un servicio WFS y pulsa Conectar para consultar sus tipos de entidad.</p>"
        "<p>Selecciona una fila para añadirla como fuente de datos. El servicio debe publicar una respuesta GetCapabilities accesible.</p>"
    ),
    "Preferences window help": (
        "<h2>Preferencias</h2><p>Configura idioma, autoguardado, historial de deshacer, mapa inicial y comportamiento de las fuentes.</p>"
        "<p><b>Aplicar</b> guarda los cambios sin cerrar esta ventana. <b>Aceptar</b> los guarda y cierra; <b>Cancelar</b> descarta los cambios pendientes.</p>"
    ),
    "Browse OGC Catalog window help": (
        "<h2>Catálogo OGC</h2><p>Conecta con un catálogo CSW y busca conjuntos de datos por título o palabras clave.</p>"
        "<p>Selecciona un resultado para consultar sus detalles y pulsa <b>Añadir como fuente WFS</b> cuando el registro contenga un servicio compatible.</p>"
    ),
    "Form Designer window help": (
        "<h2>Diseñador de formularios</h2><p>Crea formularios reutilizables para rellenar metadatos de zonas y puntos clave.</p>"
        "<p>Define nombre, descripción y destino. Añade campos, indica su tipo, obligatoriedad y valor inicial, y ordénalos con las flechas.</p>"
    ),
    "Extension Library window help": (
        "<h2>Biblioteca de extensiones</h2><p>Gestiona plantillas HTML, CSS y JavaScript reutilizables en los elementos.</p>"
        "<p>Usa el filtro para encontrar una plantilla, edítala en el panel derecho y pulsa <b>Vista previa</b> para comprobarla con datos de ejemplo.</p>"
    ),
    "Import Source Pack window help": (
        "<h2>Importar paquete de fuentes</h2><p>Abre un archivo .bsp y revisa sus fuentes antes de añadirlas al proyecto.</p>"
        "<p>Puedes filtrar entradas, editar sus parámetros y añadir una fuente individual o todas las seleccionadas.</p>"
    ),
    "Export Source Pack window help": (
        "<h2>Exportar paquete de fuentes</h2><p>Selecciona las fuentes del proyecto que quieres compartir en un archivo .bsp.</p>"
        "<p>Completa la información del paquete, revisa la selección y pulsa <b>Guardar</b> para elegir la ruta de salida.</p>"
    ),
    "Map Composer window help": (
        "<h2>Compositor de mapas</h2><p>Prepara la página final antes de imprimir o exportar a PDF.</p>"
        "<p>Configura página y zoom, leyenda, bloque de título e información adicional. La vista previa se actualiza mientras editas.</p>"
        "<p>Indica la ruta de salida para PDF. <b>Imprimir</b> envía el diseño a la impresora y <b>Exportar PDF</b> crea el archivo.</p>"
    ),
    "Debug Log window help": (
        "<h2>Registro de depuración</h2><p>Muestra los mensajes de registro capturados durante la ejecución de BIMAP.</p>"
        "<p>Usa <b>Actualizar</b> para cargar los mensajes recientes, <b>Limpiar</b> para vaciar el registro en memoria y <b>Copiar todo</b> para compartirlo al diagnosticar un problema.</p>"
    ),
    "Element Editor window help": (
        "<h2>Editor de elementos</h2><p>Edita las propiedades de una zona o punto clave en una copia temporal.</p>"
        "<p>Los cambios se aplican al proyecto al pulsar <b>Aceptar</b>. <b>Cancelar</b> cierra la ventana sin guardar los cambios.</p>"
    ),
    "Form Fill window help": (
        "<h2>Rellenar formulario</h2><p>Completa los campos definidos por el formulario seleccionado.</p>"
        "<p>Los campos obligatorios están marcados con un asterisco. Pulsa <b>Guardar</b> para escribir las respuestas en los metadatos del elemento.</p>"
    ),
    "Extension Editor window help": (
        "<h2>Editor de extensiones</h2><p>Crea o modifica una plantilla HTML, CSS y JavaScript para mostrar información del elemento.</p>"
        "<p>Selecciona una plantilla, edita el código y usa la vista previa para comprobar el resultado. Guarda solo cuando el contenido esté listo para reutilizarse.</p>"
    ),
    "Extension Viewer window help": (
        "<h2>Visor de extensiones</h2><p>Renderiza la extensión del elemento seleccionado con sus datos actuales.</p>"
        "<p>Usa <b>Recargar</b> después de cambiar los datos. <b>Abrir en navegador</b> permite consultar el mismo contenido fuera de BIMAP.</p>"
    ),
    "Metadata Viewer window help": (
        "<h2>Visor de metadatos</h2><p>Muestra los pares clave-valor guardados como información adicional del elemento.</p>"
        "<p>Esta vista es solo de lectura. Para modificar los datos, vuelve al editor de propiedades o al formulario del elemento.</p>"
    ),
    "Apply a saved style to this zone": "Aplicar un estilo guardado a esta zona",
    "Choose the font family used by the label": "Elegir la familia tipográfica de la etiqueta",
    "Make the label text bold": "Mostrar el texto de la etiqueta en negrita",
    "Make the label text italic": "Mostrar el texto de la etiqueta en cursiva",
    "Circle radius in metres": "Radio del círculo en metros",
    "Rectangle width in metres": "Ancho del rectángulo en metros",
    "Rectangle height in metres": "Alto del rectángulo en metros",
    "Rotate the zone in degrees clockwise": "Girar la zona en grados en sentido horario",
    "Choose an SVG file to use as the zone fill": "Elegir un archivo SVG para rellenar la zona",
    "Remove the SVG fill from the zone": "Quitar el relleno SVG de la zona",
    "Open the selected form and write its answers to metadata": "Abrir el formulario seleccionado y guardar sus respuestas en los metadatos",
    "Main title shown in the key point information card": "Título principal de la ficha informativa del punto clave",
    "Secondary text shown below the key point title": "Texto secundario mostrado bajo el título del punto clave",
    "Additional information shown in the key point information card": "Información adicional mostrada en la ficha informativa del punto clave",
    "Optional web link associated with this key point": "Enlace web opcional asociado a este punto clave",
    "Color used for the key point marker": "Color usado para el marcador del punto clave",
    "Marker size in pixels (8 to 40)": "Tamaño del marcador en píxeles (8 a 40)",
    "Choose the marker shape or a custom icon": "Elegir la forma del marcador o un icono personalizado",
    "Choose an image file for a custom marker icon": "Elegir una imagen para el icono personalizado del marcador",
    "Latitude in decimal degrees (-90 to 90)": "Latitud en grados decimales (-90 a 90)",
    "Longitude in decimal degrees (-180 to 180)": "Longitud en grados decimales (-180 a 180)",
    "Text displayed inside the annotation": "Texto mostrado dentro de la anotación",
    "Annotation font size in points (6 to 72)": "Tamaño de fuente de la anotación en puntos (6 a 72)",
    "Color used for annotation text": "Color usado para el texto de la anotación",
    "Background color of the annotation box": "Color de fondo de la caja de anotación",
    "Select a form design to populate metadata fields": "Seleccionar un diseño de formulario para rellenar campos de metadatos",
    "Read-only attributes received from the selected data source": "Atributos de solo lectura recibidos de la fuente de datos seleccionada",
    "Choose the data source that provides values for this metadata key": "Elegir la fuente de datos que proporciona valores para esta clave de metadatos",
    "Remove the data-source binding from this metadata key": "Quitar la vinculación con la fuente de datos de esta clave de metadatos",
    "Choose an extension from the library or edit custom HTML": "Elegir una extensión de la biblioteca o editar HTML personalizado",
    "Open the selected extension with the current element data": "Abrir la extensión seleccionada con los datos actuales del elemento",
    "Key Points": "Puntos Clave",
    "Data Sources": "Fuentes de Datos",

    # ── Geocode dialog ───────────────────────────────────────────────────────
    "Search Location": "Buscar Ubicación",
    "Enter address or place name:": "Introduzca una dirección o nombre de lugar:",
    "e.g. Madrid, Spain": "Ej: Madrid, España",
    "Searching…": "Buscando…",
    "No results found.": "No se encontraron resultados.",

    # ── Place by Coordinates dialog ──────────────────────────────────────────
    "Place by Coordinates": "Colocar por Coordenadas",
    "Keypoint (single point)": "Punto clave (un punto)",
    "Zone (polygon vertices)": "Zona (vértices de polígono)",
    "Enter one vertex per line as:  lat, lon\n(minimum 3 vertices to create a zone)": (
        "Introduzca un vértice por línea como:  lat, lon\n(mínimo 3 vértices para crear una zona)"
    ),
    "At least 3 vertices are required to create a zone.": (
        "Se necesitan al menos 3 vértices para crear una zona."
    ),
    "No forms match this element type. Select from all available forms:": (
        "No hay formularios para este tipo de elemento. Seleccione de los disponibles:"
    ),

    # ── Export dialog ────────────────────────────────────────────────────────
    "Export PDF": "Exportar PDF",
    "Page Settings": "Configuración de Página",
    "Page Size": "Tamaño de Página",
    "Orientation": "Orientación",
    "DPI": "DPI",
    "Output file path…": "Ruta del archivo de salida…",
    "Browse…": "Examinar…",
    "Output File:": "Archivo de Salida:",
    "Save PDF": "Guardar PDF",
    "PDF Files (*.pdf)": "Archivos PDF (*.pdf)",

    # ── Properties panel tabs ────────────────────────────────────────────────
    "Style": "Estilo",
    "Metadata": "Metadatos",
    "Extension": "Extensión",
    "Select an element to view its metadata.": "Seleccione un elemento para ver sus metadatos.",

    # ── Extension editor / viewer ────────────────────────────────────────────
    "Edit Extension…": "Editar Extensión…",
    "Create Extension…": "Crear Extensión…",
    "Launch Viewer": "Abrir Visor",
    "No extension configured for this element.": "Sin extensión configurada para este elemento.",
    "Extension Editor": "Editor de Extensión",
    "Load Template": "Cargar Plantilla",
    "Hello World (starter)": "Hola Mundo (plantilla inicial)",
    "From Library\u2026": "De la Biblioteca\u2026",
    "Extension Library": "Biblioteca de Extensiones",
    "Choose from Library": "Elegir de la Biblioteca",
    "Select a template to load into the editor:": "Selecciona una plantilla para cargar en el editor:",
    "Bar Chart (metadata values)": "Gráfico de Barras (valores metadata)",
    "Gauge (single value)": "Medidor (valor único)",
    "Table (all metadata)": "Tabla (toda la metadata)",
    "Open in Browser": "Abrir en Navegador",
    "Save": "Guardar",
    "HTML content is required.": "Se requiere contenido HTML.",
    "No element selected.": "Ningún elemento seleccionado.",

    # ── Properties panel form labels ─────────────────────────────────────────
    "Properties": "Propiedades",
    "Zone": "Zona",
    "New Zone": "Nueva Zona",
    "New Circle": "Nuevo Círculo",
    "Refresh map tiles": "Actualizar teselas del mapa",
    "Keypoint": "Punto de Interés",
    "Annotation": "Anotación",
    "Preset": "Preajuste",
    "Name": "Nombre",
    "Group": "Grupo",
    "Fill": "Relleno",
    "Color": "Color",
    "Opacity": "Opacidad",
    "Border": "Borde",
    "Width": "Ancho",
    "Label": "Etiqueta",
    "Text": "Texto",
    "Font": "Fuente",
    "Size": "Tamaño",
    "Bold": "Negrita",
    "Italic": "Cursiva",
    "Bg Color": "Color Fondo",
    "Offset X": "Desp. X",
    "Offset Y": "Desp. Y",
    "Geometry": "Geometría",
    "Radius (m)": "Radio (m)",
    "Width (m)": "Ancho (m)",
    "Height (m)": "Alto (m)",
    "Rotation": "Rotación",
    "SVG Fill": "Relleno SVG",
    "Browse\u2026": "Examinar\u2026",
    "Clear": "Limpiar",
    "No file selected": "Sin archivo seleccionado",
    "Toggle coordinate grid (precision move)": "Activar cuadrícula de coordenadas (mover con precisión)",
    "Rotate zone (click zone, then \u2191/\u2193 to rotate 1\u00b0 at a time)": "Rotar zona (clic en zona, luego \u2191/\u2193 para rotar 1\u00b0)",
    "Form Designer": "Diseñador de Formularios",
    "Form Designer\u2026": "Diseñador de Formularios\u2026",
    "Forms": "Formularios",
    "Form": "Formulario",
    "Design": "Diseño",
    "--- none ---": "--- ninguno ---",
    "Fill Form...": "Rellenar Formulario...",
    "Fill Form…": "Rellenar Formulario…",
    "Open Form Designer...": "Abrir Diseñador de Formularios...",
    "No forms defined. Use Data > Form Designer to create one.": (
        "Sin formularios definidos. Use Datos > Diseñador de Formularios para crear uno."
    ),
    "+ General Info": "+ Info General",
    "Insert a pre-built General Information form with common fields": (
        "Insertar un formulario de Información General predefinido con campos comunes"
    ),
    "General Information": "Información General",
    "Standard general-purpose information form for zones and keypoints.": (
        "Formulario de información general para zonas y puntos clave."
    ),
    "Active": "Activo",
    "Inactive": "Inactivo",
    "Pending": "Pendiente",
    "Under Review": "En Revisión",
    "Low": "Bajo",
    "Medium": "Medio",
    "High": "Alto",
    "Critical": "Crítico",
    "Tags": "Etiquetas",
    "\ud83d\udcdd  Edit Info\u2026": "\ud83d\udcdd  Editar Info\u2026",
    "Edit Info": "Editar Info",
    "Select form:": "Seleccionar formulario:",
    "Icon": "Icono",
    "Pin": "Pin",
    "Circle": "Círculo",
    "Square": "Cuadrado",
    "Diamond": "Diamante",
    "Star": "Estrella",
    "Custom\u2026": "Personalizado\u2026",
    "Choose Icon": "Elegir Icono",
    "New Form": "Nuevo Formulario",
    "Add Field": "Añadir Campo",
    "+ Add Field": "+ Añadir Campo",
    "New Field": "Nuevo Campo",
    "Remove Field": "Eliminar Campo",
    "Field Label": "Etiqueta del Campo",
    "Field Type": "Tipo de Campo",
    "Type": "Tipo",
    "Status": "Estado",
    "Priority": "Prioridad",
    "Fields": "Campos",
    "Default value": "Valor por defecto",
    "Options (one per line):": "Opciones (una por línea):",
    "Required": "Obligatorio",
    "Default Value": "Valor por Defecto",
    "Target": "Destino",
    "Zone & Keypoint": "Zona y Punto de Interés",
    "Form Properties": "Propiedades del Formulario",
    "Field Editor": "Editor de Campo",
    "Default": "Por Defecto",
    "Move field up": "Subir campo",
    "Move field down": "Bajar campo",
    "Confirm Delete": "Confirmar Eliminación",
    "Delete form '{name}'? This cannot be undone.": "¿Eliminar formulario '{name}'? No se puede deshacer.",
    "Required Field": "Campo Obligatorio",
    "Field '{label}' is required.": "El campo '{label}' es obligatorio.",
    "* Required fields": "* Campos obligatorios",
    "+ New Form": "+ Nuevo Formulario",
    "Delete": "Eliminar",
    "Title": "Título",
    "Subtitle": "Subtítulo",
    "Notes": "Notas",
    "URL": "URL",
    "Pin Color": "Color Pin",
    "Pin Size": "Tamaño Pin",
    "Latitude": "Latitud",
    "Longitude": "Longitud",
    "Font Size": "Tamaño Fuente",
    "Text Color": "Color Texto",
    "Background": "Fondo",
    "Key": "Clave",
    "Value": "Valor",
    "+ Add": "+ Añadir",
    "Remove Selected": "Eliminar Selección",
    "Source": "Fuente",
    "Bind Metadata Key": "Vincular Clave de Metadato",
    "Data Source": "Fuente de Datos",
    "Column": "Columna",
    "Filter Field": "Campo Filtro",
    "Filter Value": "Valor Filtro",
    "Aggregate": "Agregar",
    "Clear Binding": "Eliminar Vínculo",
    "— none —": "— ninguno —",
    "(optional) e.g. zone_name": "(opcional) ej. nombre_zona",
    "Use {{element.name}} or {{element.id}} as dynamic filter values.": "Usa {{element.name}} o {{element.id}} como valores de filtro dinámicos.",
    "Double-click Source column to bind a key to a data source": "Doble clic en columna Fuente para vincular una clave a un origen de datos",
    "Select from library or choose Custom:": "Seleccionar de biblioteca o elegir Personalizado:",
    "Choose Color": "Elegir color",
    "➕ New Data Source…": "➕ Nueva fuente de datos…",
    "Select an element to view its extension.": "Seleccione un elemento para ver su extensión.",

    # ── Context menu (tile_widget) ───────────────────────────────────────────
    "📝  Add Text here": "📝  Agregar Texto aquí",
    "✏  Edit…": "✏  Editar…",
    "↔  Move": "↔  Mover",
    "📋  View Metadata…": "📋  Ver Metadatos…",
    "🗑  Remove…": "🗑  Eliminar…",
    "🔗  Open Extension…": "🔗  Abrir Extensión…",

    # ── Data source dialog ───────────────────────────────────────────────────
    "Add Data Source": "Agregar Fuente de Datos",
    "Refresh": "Actualizar",
    "Mode": "Modo",
    "Interval": "Intervalo",
    "File Path": "Ruta de Archivo",
    "Sheet": "Hoja",
    "Connection": "Conexión",
    "Query": "Consulta",
    "Auth Token": "Token de Autenticación",
    "Data Path": "Ruta de Datos",
    "Host": "Host",
    "Port": "Puerto",
    "Database": "Base de datos",
    "User": "Usuario",
    "Password": "Contraseña",
    "Table": "Tabla",
    "Filter": "Filtro",
    "Sheet name or index (default: 0)": "Nombre de hoja o índice (por defecto: 0)",

    # ── Layers panel ─────────────────────────────────────────────────────────
    "+ Layer": "+ Capa",
    "Add a new layer": "Añadir nueva capa",
    "Export Layer CSV…": "Exportar Capa a CSV…",
    "Export elements of the selected layer to CSV": "Exportar elementos de la capa seleccionada a CSV",
    "🗑  Remove Layer…": "🗑  Eliminar Capa…",
    "Cannot Remove": "No se puede eliminar",
    "The 'Default' layer cannot be removed.": "La capa 'Default' no se puede eliminar.",
    "🎯  Go to": "🎯  Ir a",
    "🔄  Update": "🔄  Actualizar",
    "📊 Data Layers": "📊 Capas de Datos",

    # ── Data Sources panel ───────────────────────────────────────────────────
    "just now": "ahora mismo",
    "{m}m ago": "hace {m}m",
    "Connecting…": "Conectando…",
    "Error": "Error",
    "Connected": "Conectado",
    "{n} rows": "{n} filas",
    "Not refreshed": "Sin actualizar",
    "Never refreshed  [{mode}]": "Sin actualizar  [{mode}]",
    "⟳ Refresh": "⟳ Actualizar",
    "⟳ Connecting…": "⟳ Conectando…",
    "🎯 Fly to": "🎯 Ir a",
    "Zoom map to the extent of this data source": "Enfocar mapa en la extensión de esta fuente de datos",
    "Refreshing data source…": "Actualizando fuente de datos…",
    "{n} rows loaded in {ms} ms": "{n} filas cargadas en {ms} ms",

    # ── Delimitation dialog ──────────────────────────────────────────────────
    "Set Delimitation": "Fijar Delimitación",
    "Current delimitation:": "Delimitación actual:",
    "Search for a city, province, country, etc.:": "Buscar ciudad, provincia, país, etc.:",

    "Please select a result first.": "Seleccione primero un resultado.",

    # ── Dynamic Zone / multi-select ────────────────────────────────────────────────
    "Dynamic Zone": "Zona Dinámica",
    "No elements found inside Dynamic Zone.": "No se encontraron elementos dentro de la Zona Dinámica.",
    "{n} element(s) inside the Dynamic Zone.": "{n} elemento(s) dentro de la Zona Dinámica.",

    # ── GeoJSON / CSV export ────────────────────────────────────────────────────
    "Export GeoJSON": "Exportar GeoJSON",
    "Export GeoJSON…": "Exportar GeoJSON…",
    "Export Elements CSV": "Exportar Elementos a CSV",
    "CSV Exported": "CSV exportado",
    "Exported": "Exportados",
    "zone(s)": "zona(s)",
    "keypoint(s)": "punto(s) de interés",
    "and": "y",
    "to": "en",

    # ── main_window.py dialog titles / messages ──────────────────────────────
    "Open Project": "Abrir proyecto",
    "Save Project As": "Guardar proyecto como",
    "Open Failed": "Error al abrir",
    "Save Failed": "Error al guardar",
    "Import GeoJSON": "Importar GeoJSON",
    "Import Failed": "Error al importar",
    "Export Data Backup": "Exportar copia de seguridad",
    "Backup Exported": "Copia exportada",
    "Backup saved to:\n{path}\n\nCopy this file to transfer your project to another PC.": (
        "Copia guardada en:\n{path}\n\nCopie este archivo para transferir su proyecto a otro PC."
    ),
    "Export Failed": "Error al exportar",
    "Import Data Backup": "Importar copia de seguridad",
    "Backup imported successfully.": "Copia importada correctamente.",
    "Print Error": "Error al imprimir",
    "Save Bookmark": "Guardar marcador",
    "Bookmark name:": "Nombre del marcador:",
    "Add Layer": "Añadir capa",
    "Layer name:": "Nombre de la capa:",
    "Duplicate Layer": "Capa duplicada",
    "A layer named '{name}' already exists.": "Ya existe una capa llamada '{name}'.",
    "Delimitation cleared.": "Delimitación eliminada.",
    "Confirm Remove": "Confirmar eliminación",
    "Remove '{name}'?": "¿Eliminar '{name}'?",
    "🗑  Delete {n} element(s)": "🗑  Eliminar {n} elemento(s)",
    "⬠  Create Polygon Zone": "⬠  Crear zona polígono",

    # ── Metadata view dialog ─────────────────────────────────────────────────
    "No metadata entries for this element.": "Sin entradas de metadatos para este elemento.",
    "Close": "Cerrar",
    "Copy All": "Copiar Todo",
    "Copied to clipboard.": "Copiado al portapapeles.",

    # ── Map Composer dialog ──────────────────────────────────────────────────
    "Map Composer": "Compositor de Mapa",
    "Page && Zoom": "Página y Zoom",
    "Legend": "Leyenda",
    "Title Block": "Bloque de Título",
    "Info Box": "Cuadro de Info",
    "Cancel": "Cancelar",
    "Yes": "Sí",
    "No": "No",
    "🖶  Print…": "🖶  Imprimir…",
    "📄  Export PDF": "📄  Exportar PDF",
    "Capture Zoom": "Zoom Captura",
    "Show legend overlay on output": "Mostrar leyenda en salida",
    "Legend Title": "Título de Leyenda",
    "Zones (uncheck to hide, edit Display Label to rename):": "Zonas (desmarcar para ocultar, editar Etiqueta para renombrar):",
    "Layer": "Capa",
    "Display Label": "Etiqueta Mostrada",
    "Show architectural title block on output": "Mostrar bloque de título arquitectónico en salida",
    "Project Name": "Nombre del Proyecto",
    "Description": "Descripción",
    "Drawn by": "Dibujado por",
    "Checked by": "Verificado por",
    "Revision": "Revisión",
    "Scale": "Escala",
    "Show info box overlay on output": "Mostrar cuadro de info en salida",
    "Text block (appears in the info box):": "Bloque de texto (aparece en el cuadro de info):",
    "Author": "Autor",
    "Date": "Fecha",
    "Output File  (required for Export PDF)": "Archivo de Salida  (requerido para Exportar PDF)",
    "Choose output .pdf path…": "Elegir ruta del archivo .pdf de salida…",
    "landscape": "horizontal",
    "portrait": "vertical",

    # ── Extension library / manager ──────────────────────────────────────────
    "Extension Library": "Biblioteca de Extensiones",
    "Manage Extensions": "Gestionar Extensiones",
    "New Extension": "Nueva Extensión",
    "Extension Name": "Nombre de Extensión",
    "Custom Extension": "Extensión personalizada",
    "Name of the extension assigned to this element": "Nombre de la extensión asignada a este elemento",
    "Extension Description": "Descripción de Extensión",
    "Filter extensions…": "Filtrar extensiones…",
    "Duplicate": "Duplicar",
    "Create a copy of the selected extension": "Crear una copia de la extensión seleccionada",
    "Preview": "Vista previa",
    "Render the selected extension with sample data": "Renderizar la extensión seleccionada con datos de ejemplo",
    "Data Reference": "Referencia de datos",
    "Show BIMAP_DATA fields and JavaScript examples": "Mostrar campos BIMAP_DATA y ejemplos JavaScript",
    "BIMAP_DATA Reference": "Referencia de BIMAP_DATA",
    "Copy JavaScript Example": "Copiar ejemplo JavaScript",
    "The extension receives the selected zone or keypoint as the global JavaScript object BIMAP_DATA.": "La extensión recibe la zona o punto clave seleccionado como el objeto JavaScript global BIMAP_DATA.",
    "Available fields": "Campos disponibles",
    "JavaScript": "JavaScript",
    "Contents": "Contenido",
    "or": "o",
    "Object UUID": "UUID del objeto",
    "Object name": "Nombre del objeto",
    "Object group": "Grupo del objeto",
    "Map layer": "Capa del mapa",
    "Visible custom metadata": "Metadatos personalizados visibles",
    "All metadata and object attributes": "Todos los metadatos y atributos del objeto",
    "Geometry type and coordinates": "Tipo de geometría y coordenadas",
    "Keypoint information card": "Tarjeta de información del punto clave",
    "Common object attributes": "Atributos comunes del objeto",
    "and": "y",
    "JavaScript examples": "Ejemplos JavaScript",
    "Tip": "Consejo",
    "Use attributes for dimensions, hidden derived values, and object defaults.": "Usa attributes para dimensiones, valores derivados ocultos y valores predeterminados del objeto.",
    "Delete Extension": "Eliminar Extensión",
    "Apply from Library": "Aplicar desde Biblioteca",
    "From Library…": "Desde Biblioteca…",
    "Select Extension": "Seleccionar Extensión",
    "No extensions in library.": "Sin extensiones en la biblioteca.",
    "No extensions match the filter.": "Ninguna extensión coincide con el filtro.",
    "HTML content is required.": "El contenido HTML es obligatorio.",
    "Sample Element": "Elemento de ejemplo",
    "Sample Group": "Grupo de ejemplo",
    "Sample Layer": "Capa de ejemplo",
    "View Extension": "Ver Extensión",
    "Open Extension…": "Abrir Extensión…",
    "Open Data Viewer": "Abrir Visor de Datos",
    "Confirm Delete": "Confirmar Eliminación",
    "Delete extension '{name}'? This cannot be undone.": "¿Eliminar extensión '{name}'? Esta acción no se puede deshacer.",
    "Set Extension": "Establecer Extensión",
    "Set Extension…": "Establecer Extensión…",
    "✏\u2002Custom (open editor)": "✏\u2002Personalizado (abrir editor)",
    "Reload": "Recargar",
    "— Apply Preset —": "— Aplicar Preajuste —",

    # ── Preferences dialog ───────────────────────────────────────────────────
    "Preferences…": "Preferencias…",
    "Preferences": "Preferencias",
    "General": "General",
    "Map": "Mapa",
    "Cache": "Caché",
    "Appearance": "Apariencia",
    "Advanced": "Avanzado",
    "Autosave interval": "Intervalo de autoguardado",
    "Autosave interval in seconds (10–600)": "Intervalo de autoguardado en segundos (10–600)",
    "Undo stack limit": "Límite de historial deshacer",
    "Maximum number of undo steps (10–500)": "Número máximo de pasos deshacer (10–500)",
    "On startup": "Al iniciar",
    "Empty project": "Proyecto vacío",
    "Reopen last project": "Reabrir último proyecto",
    "Default zoom": "Zoom predeterminado",
    "Default latitude": "Latitud predeterminada",
    "Default longitude": "Longitud predeterminada",
    "Show Key Points": "Mostrar Puntos Clave",
    "Show Data Sources": "Mostrar Fuentes de Datos",
    "Show scale bar": "Mostrar barra de escala",
    "Show north arrow": "Mostrar flecha norte",
    "Grid size": "Tamaño de cuadrícula",
    "Fine (0.5×)": "Fina (0.5×)",
    "Normal (1×)": "Normal (1×)",
    "Coarse (2×)": "Gruesa (2×)",
    "Very Coarse (4×)": "Muy gruesa (4×)",
    "Max tile cache size": "Tamaño máximo de caché",
    "Tile expiry": "Caducidad de mosaicos",
    " days": " días",
    "Cache size and expiry take effect on next launch.": "El tamaño y caducidad de caché se aplican al próximo inicio.",
    "Clear cache now": "Limpiar caché ahora",
    "Current size": "Tamaño actual",
    "Theme settings are not yet available.\nThis page is reserved for a future release.": (
        "Los ajustes de tema aún no están disponibles.\nEsta página está reservada para una versión futura."
    ),
    "Projects folder": "Carpeta de proyectos",
    "(default)": "(predeterminado)",
    "Choose folder": "Elegir carpeta",
    "Reset all to defaults": "Restablecer todo a valores predeterminados",
    "Reset all preferences to their default values?": "¿Restablecer todas las preferencias a sus valores predeterminados?",

    # ── Live Feeds — Preferences page ───────────────────────────────────────
    "Live Feeds": "Feeds en Vivo",
    "live_network_timeout": "Tiempo de espera de red",
    "live_timeout_tip": "Segundos antes de que falle una solicitud de feed (1–60)",
    "live_max_markers": "Marcadores máximos",
    "live_trail_default": "Longitud de historial predeterminada",
    "live_follow_fastest": "Centrar mapa en el marcador más rápido",
    "live_show_error_badge": "Mostrar errores de feed en la barra de estado",
    "trail_off": "Desactivado",

    # ── Live Feed layer dialog ───────────────────────────────────────────────
    "add_live_feed": "Agregar Feed en Vivo",
    "edit_live_feed": "Editar Feed en Vivo",
    "manage_live_feeds": "Gestionar Feeds en Vivo",
    "tab_feed": "Feed",
    "tab_style": "Estilo",
    "quick_start": "Inicio rápido",
    "preset_choose": "— Elegir preset —",
    "feed_name": "Nombre",
    "feed_name_placeholder": "p.ej. Autobuses en tiempo real",
    "feed_url": "URL del Feed",
    "poll_interval": "Intervalo de actualización",
    "auth_header": "Cabecera de autenticación",
    "lat_field": "Campo latitud",
    "lon_field": "Campo longitud",
    "label_field": "Campo etiqueta",
    "test_connection": "Probar conexión",
    "test_preview_placeholder": "El JSON de respuesta aparecerá aquí…",
    "preview": "Vista previa",
    "icon_type": "Tipo de icono",
    "icon_color": "Color del icono",
    "icon_size": "Tamaño del icono",
    "trail_length": "Longitud del rastro",
    "visible": "Visible",
    "enter_url_first": "Ingrese primero la URL del feed.",
    "connecting": "Conectando…",
    "network_unavailable": "Módulo de red no disponible.",
    "unnamed_feed": "Feed sin nombre",
    "pick_color": "Elegir color",
    "Invalid URL": "URL no válida",
    "URL must start with http:// or https://": "La URL debe comenzar con http:// o https://",

    # ── Live Layers panel ────────────────────────────────────────────────────
    "edit": "Editar",
    "pause": "Pausar",
    "resume": "Reanudar",
    "remove": "Eliminar",
    "remove_live_feed": "Eliminar Feed en Vivo",
    "confirm_remove_live_feed": "¿Eliminar este feed en vivo?",
    # ── Keypoint → Zone conversion ──────────────────────────────────────────
    "\u2b21  Convert to Zone by Color\u2026": "\u2b21  Convertir a Zona por Color\u2026",
    "Convert to Zone by Color": "Convertir a Zona por Color",
    "Color tolerance (0 = exact match, 100 = all colors):": (
        "Tolerancia de color (0 = exacto, 100 = todos los colores):"
    ),

    # ── Offline map dialog ───────────────────────────────────────────────────
    "Offline Map…": "Mapa sin conexión…",
    "🗺  Work Offline — Save Map Region…": "🗺  Trabajar sin conexión — Guardar región del mapa…",
    "Work Offline — Save Map Region": "Trabajar sin conexión — Guardar región del mapa",
    "Bounding Box": "Área de cobertura",
    "Lat min (South):": "Lat mín (Sur):",
    "Lat max (North):": "Lat máx (Norte):",
    "Lon min (West):": "Lon mín (Oeste):",
    "Lon max (East):": "Lon máx (Este):",
    "Use Current View": "Usar vista actual",
    "Zoom Levels": "Niveles de zoom",
    "Min zoom:": "Zoom mín:",
    "Max zoom:": "Zoom máx:",
    "Estimate Tile Count": "Estimar número de teselas",
    "Invalid bounds or zoom range": "Límites o rango de zoom no válidos",
    " ⚠ exceeds limit — reduce zoom or area": " ⚠ supera el límite — reduzca el zoom o el área",
    " (large — may take a while)": " (grande — puede tardar un momento)",
    "tiles": "teselas",
    "⬇  Download && Cache Tiles": "⬇  Descargar y guardar teselas",
    "Cancel Download": "Cancelar descarga",
    "Invalid Region": "Región no válida",
    "Please check bounds and zoom levels.": "Compruebe los límites y niveles de zoom.",
    "Region Too Large": "Región demasiado grande",
    "This region requires {count} tiles, which exceeds the safety limit of {limit}.\n"
    "Reduce the area or zoom range and try again.": (
        "Esta región requiere {count} teselas, lo que supera el límite de {limit}.\n"
        "Reduzca el área o el rango de zoom e inténtelo de nuevo."
    ),
    "Start Download?": "¿Iniciar descarga?",
    "Download {count} tiles for offline use?\n\nTiles already in cache will be skipped.": (
        "¿Descargar {count} teselas para uso sin conexión?\n\nLas teselas ya en caché se omitirán."
    ),
    "Downloading {done} / {total} tiles…": "Descargando {done} / {total} teselas…",
    "Cancelling…": "Cancelando…",
    "Done — {downloaded} tiles downloaded, {skipped} already cached / skipped.": (
        "Listo — {downloaded} teselas descargadas, {skipped} ya en caché / omitidas."
    ),
}

_EN_HELP: dict[str, str] = {
    "Properties help with no selection": (
        "<h2>Properties panel</h2>"
        "<p>Select a zone, key point, annotation, or data feature on the map or in Layers to inspect its properties.</p>"
        "<p>Changes are applied when each field is finished. Use <b>Metadata</b> to add free-form information, control visibility, and bind values to data sources.</p>"
    ),
    "Properties help for zones": (
        "<h2>Zone properties</h2>"
        "<p><b>Name and group:</b> identify the zone and help organize it.</p>"
        "<p><b>Fill and border:</b> control its map appearance. Opacity lets you see items underneath.</p>"
        "<p><b>Label:</b> controls the text, font, size, color, and position of the label. Name and label can be kept in sync when edited.</p>"
        "<p><b>Geometry:</b> adjusts radius, width, height, and rotation for the zone type. Measurements are in metres.</p>"
        "<p><b>SVG fill:</b> uses a vector pattern instead of a flat color. The <b>Metadata</b> tab contains extensions, forms, and extra attributes.</p>"
    ),
    "Properties help for key points": (
        "<h2>Key point properties</h2>"
        "<p><b>Title, subtitle, and notes:</b> make up the point information card.</p>"
        "<p><b>URL:</b> adds a link associated with the point.</p>"
        "<p><b>Pin, icon, and size:</b> control how the point is drawn on the map. You can choose a built-in icon or load an image.</p>"
        "<p><b>Latitude and longitude:</b> define the exact geographic position. The <b>Metadata</b> tab adds attributes, forms, and extensions.</p>"
    ),
    "Properties help for annotations": (
        "<h2>Annotation properties</h2>"
        "<p><b>Text:</b> is the content displayed by the annotation.</p>"
        "<p><b>Text size and color:</b> control content readability.</p>"
        "<p><b>Background:</b> sets the annotation box color. The <b>Metadata</b> tab stores additional information.</p>"
    ),
    "Properties help for data features": (
        "<h2>Data feature properties</h2>"
        "<p>This view shows information supplied by a WFS, CSV, or API source. The source, geometry type, and coordinates describe the selected feature.</p>"
        "<p>The attributes table lets you inspect received values. Change the source, filters, or refresh behavior in <b>Data Sources</b>.</p>"
    ),
    "Data Layers help": (
        "<h2>Data Layers</h2>"
        "<p>This section shows layers created from external sources such as WFS, CSV, or APIs. Each row represents a source loaded on the map.</p>"
        "<p>Use the checkbox to show or hide a layer. The opacity control adjusts how strongly it appears over the base map. The context menu provides source editing and related actions.</p>"
        "<p>If a layer has no visible data, check its extent, filters, and refresh status in <b>Data Sources</b>.</p>"
    ),
    "Map tools help": (
        "<h2>Map tools</h2>"
        "<p><b>Select:</b> choose elements to inspect or edit their properties. <b>Pan:</b> move the map without changing elements.</p>"
        "<p><b>Rotate:</b> rotate a selected zone. <b>Move:</b> change an element's position. <b>Dynamic Selector:</b> select elements by region or criteria.</p>"
        "<p><b>Measure:</b> calculate distances between map points. <b>Draw:</b> create polygon, rectangle, or circle zones, key points, and text annotations.</p>"
        "<p><b>Grid:</b> helps move elements precisely. <b>Import:</b> load GeoJSON. <b>PDF:</b> open project export or printing.</p>"
        "<p>The search bar finds places and the <b>Map</b> selector changes the tile provider.</p>"
    ),
    "Data Source window help": (
        "<h2>Data source</h2><p>Define the name, type, and connection for an external source.</p>"
        "<p>Configure manual or automatic refresh. For WFS sources you can discover types, filters, and query bounds. Use <b>OK</b> to save the connection.</p>"
    ),
    "Export PDF window help": (
        "<h2>Export PDF</h2><p>Choose the document size, orientation, and resolution.</p>"
        "<p>Set an output path to create a PDF containing the map, legend, elements, and project key-point table.</p>"
    ),
    "Search Location window help": (
        "<h2>Search location</h2><p>Enter an address or place name and press Search.</p>"
        "<p>Select a result to center the map. Geocoding uses an online service and requires an internet connection.</p>"
    ),
    "Place by Coordinates window help": (
        "<h2>Place by coordinates</h2><p>Choose between placing a key point or creating a zone from vertices.</p>"
        "<p>For a point, enter latitude and longitude. For a zone, enter one vertex per line as <b>lat, lon</b>; at least three are required.</p>"
    ),
    "Set Delimitation window help": (
        "<h2>Delimitation</h2><p>Search for a city, province, country, or other administrative boundary.</p>"
        "<p>Select a result with a polygon to apply it to the map. Use <b>Clear Delimitation</b> to remove the current boundary.</p>"
    ),
    "Live Feed window help": (
        "<h2>Live feed</h2><p>Configure the URL, format, filters, and polling interval for an automatically updated layer.</p>"
        "<p>The style tab controls the appearance of received features. Pausing a feed stops requests without deleting its configuration.</p>"
    ),
    "Offline Map window help": (
        "<h2>Offline map</h2><p>Download and cache tiles for a selected area so they can be used without an internet connection.</p>"
        "<p>Set the bounds and zoom levels. Use <b>Estimate Tile Count</b> to check download size before starting.</p>"
    ),
    "Discover WFS window help": (
        "<h2>Discover WFS layers</h2><p>Enter a WFS service URL and press Connect to retrieve its feature types.</p>"
        "<p>Select a row to add it as a data source. The service must expose an accessible GetCapabilities response.</p>"
    ),
    "Preferences window help": (
        "<h2>Preferences</h2><p>Configure language, autosave, undo history, initial map view, and source behavior.</p>"
        "<p><b>Apply</b> saves changes without closing this window. <b>OK</b> saves and closes; <b>Cancel</b> discards pending changes.</p>"
    ),
    "Browse OGC Catalog window help": (
        "<h2>OGC catalog</h2><p>Connect to a CSW catalog and search datasets by title or keywords.</p>"
        "<p>Select a result to inspect its details and press <b>Add as WFS Data Source</b> when the record contains a compatible service.</p>"
    ),
    "Form Designer window help": (
        "<h2>Form Designer</h2><p>Create reusable forms for entering metadata on zones and key points.</p>"
        "<p>Set the name, description, and target. Add fields, choose their type, required state, and default value, then reorder them with the arrows.</p>"
    ),
    "Extension Library window help": (
        "<h2>Extension Library</h2><p>Manage reusable HTML, CSS, and JavaScript templates for elements.</p>"
        "<p>Use the filter to find a template, edit it in the right panel, and press <b>Preview</b> to test it with sample data.</p>"
    ),
    "Import Source Pack window help": (
        "<h2>Import Source Pack</h2><p>Open a .bsp file and review its sources before adding them to the project.</p>"
        "<p>Filter entries, edit their parameters, and add one source or all checked sources.</p>"
    ),
    "Export Source Pack window help": (
        "<h2>Export Source Pack</h2><p>Select project sources to share in a .bsp file.</p>"
        "<p>Complete the pack information, review the selection, and press <b>Save</b> to choose the output path.</p>"
    ),
    "Map Composer window help": (
        "<h2>Map Composer</h2><p>Prepare the final page before printing or exporting to PDF.</p>"
        "<p>Configure page and zoom, legend, title block, and additional information. The preview updates as you edit.</p>"
        "<p>Set an output path for PDF. <b>Print</b> sends the layout to a printer and <b>Export PDF</b> creates the file.</p>"
    ),
    "Debug Log window help": (
        "<h2>Debug log</h2><p>Shows log messages captured while BIMAP is running.</p>"
        "<p>Use <b>Refresh</b> to load recent messages, <b>Clear</b> to empty the in-memory log, and <b>Copy All</b> to share it when diagnosing a problem.</p>"
    ),
    "Element Editor window help": (
        "<h2>Element Editor</h2><p>Edit the properties of a zone or key point in a temporary copy.</p>"
        "<p>Changes are applied to the project when you press <b>OK</b>. <b>Cancel</b> closes the window without saving them.</p>"
    ),
    "Form Fill window help": (
        "<h2>Form Fill</h2><p>Complete the fields defined by the selected form.</p>"
        "<p>Required fields are marked with an asterisk. Press <b>Save</b> to write the answers to the element metadata.</p>"
    ),
    "Extension Editor window help": (
        "<h2>Extension Editor</h2><p>Create or edit an HTML, CSS, and JavaScript template for displaying element information.</p>"
        "<p>Select a template, edit the code, and use preview to check the result. Save when the content is ready to reuse.</p>"
    ),
    "Extension Viewer window help": (
        "<h2>Extension Viewer</h2><p>Renders the selected element's extension with its current data.</p>"
        "<p>Use <b>Reload</b> after changing data. <b>Open in Browser</b> lets you inspect the same content outside BIMAP.</p>"
    ),
    "Metadata Viewer window help": (
        "<h2>Metadata Viewer</h2><p>Shows the key-value pairs stored as additional information for the element.</p>"
        "<p>This view is read-only. To change the data, return to the element properties editor or form.</p>"
    ),
    "Layers panel help": (
        "<h2>Layers panel</h2>"
        "<p>Organizes map elements by layer. Click a zone, key point, or annotation to select it and open its properties.</p>"
        "<p>Use checkboxes to show or hide layers and elements. Drag an element to another layer, or right-click for more actions.</p>"
        "<p>The data-layers section shows WFS, CSV, or API sources. Adjust visibility and opacity, and use the context menu for source actions.</p>"
    ),
    "Data Sources panel help": (
        "<h2>Data Sources panel</h2>"
        "<p>Configure external connections that provide project data, such as WFS, GeoJSON, CSV, Excel, REST API, SQL, or Google Sheets.</p>"
        "<p><b>Add:</b> create and configure a source. <b>Edit:</b> change its connection. <b>Refresh:</b> load its data again.</p>"
        "<p><b>Fly to:</b> fit the source extent on the map. The status indicator shows whether the last load succeeded, is in progress, or failed.</p>"
    ),
    "Live Feeds panel help": (
        "<h2>Live Feeds panel</h2>"
        "<p>Manage layers that query data periodically and update their map features.</p>"
        "<p><b>Add:</b> configure a feed. <b>Edit:</b> change its URL, interval, or filters. <b>Pause/Resume:</b> stop or continue automatic polling.</p>"
        "<p>The colored dot shows feed status and the number in parentheses shows received features. Double-click or use the context menu for quick actions.</p>"
    ),
    "Key Points panel help": (
        "<h2>Key Points panel</h2>"
        "<p>Lists every key point in the project and shows its assigned number when present.</p>"
        "<p><b>Assign #</b> gives the point the next available number for legends or documents. <b>Clear #</b> removes its number.</p>"
        "<p>To edit title, notes, icon, position, and metadata, use the selected point's <b>Properties</b> panel.</p>"
    ),
}


_current_lang: str = "en"


def set_language(lang: str) -> None:
    """Set the active language.  Supported: ``'en'``, ``'es'``."""
    global _current_lang
    if lang in ("en", "es"):
        _current_lang = lang


def get_language() -> str:
    """Return the current language code (``'en'`` or ``'es'``)."""
    return _current_lang


def t(key: str) -> str:
    """Translate *key* to the current language.  Returns *key* unchanged when
    running in English or when no translation is found."""
    if _current_lang == "en":
        return _EN_HELP.get(key, key)
    return _ES.get(key, key)
