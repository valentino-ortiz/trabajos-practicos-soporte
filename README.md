# Estacionamiento con OpenCV

El programa de `opencv2/main.py` procesa `Park_final.mp4`, detecta los autos con
YOLO y publica el estado de cada espacio en un dashboard Flask.

## Ejecucion

Desde la carpeta `opencv2`:

```bash
python main.py
```

Mientras el procesamiento esta activo, abrir `http://127.0.0.1:5000`. El mapa se
actualiza una vez por segundo y usa los mismos poligonos de `bounding_boxes.json`
que se dibujan sobre el video.

La pagina tambien permite modificar las tarifas por tipo de vehiculo. Los
valores se guardan en `opencv2/tarifas.json` y se aplican al tracking activo.
Para evitar titilaciones, un espacio ocupado no se libera ante una sola ausencia:
debe permanecer sin deteccion durante 3 segundos consecutivos.
La facturacion usa una regla similar: el vehiculo debe mantener su centro de
deteccion dentro de una tolerancia de 8 pixeles durante 3 segundos. Antes de
confirmar esa quietud figura como `esperando quietud` y su importe es `$0`.
Al confirmarse, comienza el tiempo facturable y se aplica el minimo configurado.
El modelo actual reconoce autos, por lo que las detecciones se facturan como
`auto`; las demas categorias quedan precargadas para un modelo futuro o una
clasificacion manual.

## Video en vivo

El analisis en vivo es viable si la fuente entrega una URL directa y estable,
por ejemplo RTSP, HTTP/MJPEG o una webcam local. YouTube agrega una capa de
extraccion temporal, restricciones de sesion y limites de peticiones; un error
409 puede impedir obtener la URL antes de que OpenCV y YOLO lleguen a trabajar.
Por eso el dashboard y el detector quedan independientes de YouTube: se puede
usar luego una camara directa reemplazando `VIDEO_PATH` por su URL.
