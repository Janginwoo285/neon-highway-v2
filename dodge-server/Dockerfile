FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn -q -DskipTests dependency:go-offline
COPY src ./src
RUN mvn -q -DskipTests package
FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=builder /build/target/dodge-server-1.0.0.jar /app/app.jar
ENV PORT=8080
CMD ["java","-jar","/app/app.jar"]
