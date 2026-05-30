FROM eclipse-temurin:21-jre
WORKDIR /opt/Lavalink

# Without application.yml
COPY Lavalink.jar .
COPY plugins ./plugins

# Port in application.yml (default 5000)
EXPOSE 5000

CMD ["java", "-jar", "Lavalink.jar"]