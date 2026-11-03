package app.dodge;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@SpringBootApplication
public class DodgeApplication {
  public static void main(String[] args) { SpringApplication.run(DodgeApplication.class, args); }
  @Bean WebMvcConfigurer cors() {
    return new WebMvcConfigurer() {
      @Override public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/game/**")
          .allowedOrigins(System.getenv().getOrDefault("APP_CORS_ORIGINS","https://janginwoo285.github.io,http://localhost:8080,http://localhost:3000").split(","))
          .allowedMethods("GET","POST","OPTIONS")
          .allowedHeaders("Authorization","Content-Type");
      }
    };
  }
}
