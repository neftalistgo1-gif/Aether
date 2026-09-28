# Catálogo de códigos postales

El catálogo activo vive en `backend/private_storage/postal_codes.json`. Es el único archivo que consulta Aether para autocompletar domicilios.

Para ampliar la cobertura, inicia sesión como administrador y sube el archivo de Correos de México en formato `.xls` desde el importador de códigos postales. Aether reconoce el archivo HTML con extensión `.xls` que entrega Correos de México y requiere estas columnas: `Código Postal`, `Estado`, `Municipio`, `Ciudad`, `Tipo de Asentamiento` y `Asentamiento`.

La importación mezcla ciudades nuevas con las ya existentes; no elimina datos previos. El archivo inicial incluye únicamente Reynosa, Tamaulipas, México. Para una carga futura, descarga el catálogo de la ciudad nueva con el mismo formato y súbelo completo.
