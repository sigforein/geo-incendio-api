FROM docker.osgeo.org/geoserver:2.28.0

ENV EXTRA_JAVA_OPTS="-Xms64m -Xmx384m -XX:+UseSerialGC" \
    PORT=8080

COPY workspaces/incendios_ws /opt/geoserver_data/workspaces/incendios_ws
COPY data/susceptibilidad.tif /opt/geoserver_data/data/incendios/susceptibilidad.tif