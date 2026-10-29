# Observatorio Electoral: Render sin crear otra base de datos

Este paquete usa **un único Web Service Free** y **ninguna base de datos nueva**. La app necesita PostgreSQL persistente en una base existente o externa.

## Importante: límite de 25 recursos

Render Hobby tiene un máximo de **25 servicios por workspace** (incluidos servicios suspendidos). Si tienes **25 ya creados**, este paquete tampoco podrá crear un servicio nuevo. Hay que liberar un espacio eliminando un recurso que no uses (respaldar antes si es una base de datos), o usar/reconfigurar un web service que ya exista.

Si tienes **24**, esta variante utiliza el espacio restante. El Blueprint anterior intentaba crear dos recursos y por eso fallaba.

## Despliegue

1. Coloca este proyecto actualizado en tu repositorio privado GitHub; el archivo `render.yaml` está en la raíz.
2. Consigue una URL de conexión PostgreSQL **de una base que ya tengas**, idealmente dedicada a este proyecto. Render permite copiar `Internal Database URL` de una base existente dentro del mismo workspace/región; si usas una base externa, utiliza su cadena de conexión y TLS según su proveedor.
3. En Render -> New -> Blueprint, conecta el repositorio. Debe decir **1 Web Service Free; 0 Databases**. No confirmes si aparece cualquier plan de pago.
4. Introduce las variables secretas: `DATABASE_URL`, `ADMIN_PASSWORD`, `REVIEWER_PASSWORD`, `OPENAI_API_KEY`. `APP_SECRET` se genera automáticamente. **No incluyas secretos en render.yaml ni en GitHub.**
5. Despliega. El servicio comprueba `/health` y crea automáticamente las tablas necesarias en la base de datos a la que está conectado.

## Si estás en 25/25

* Ve a Render Dashboard, selecciona el workspace e inspecciona **todos** los servicios y bases de datos, incluidos los suspendidos.
* Borra únicamente recursos de prueba que ya no necesitas, respaldando antes sus datos.
* O bien aprovecha un Web Service ya creado: configura su repositorio, build command `pip install -r requirements.txt`, start command `python -m app.free_server`, y las variables secretas indicadas arriba. No tienes que crear un Blueprint nuevo en ese caso.

## Advertencias

* El servicio Free se suspende tras inactividad, y el procesamiento embebido no garantiza analizar dos horas sin interrupciones.
* `DATABASE_URL` no puede quedar vacío: si falta, la app cambia a SQLite local, cuyo archivo en Render Free **no es persistente**. No uses esa modalidad para conservar menciones o revisiones.
* Una base de datos Render Postgres Free tiene límite de una por workspace, caduca a los 30 días y no tiene backups automáticos. Exporta la información antes de su vencimiento.
* No se incluye infraestructura de video: se mantienen enlaces de YouTube y marcas de tiempo.
