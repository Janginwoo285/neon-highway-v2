package app.letterday;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@SpringBootApplication
public class LetterdayApplication {
    public static void main(String[] args) { SpringApplication.run(LetterdayApplication.class, args); }
    @Bean WebMvcConfigurer cors() {
        String specified = System.getenv().getOrDefault("APP_CORS_ORIGINS",
            "http://localhost:5500,http://localhost:5173,http://localhost:3000,https://janginwoo285.github.io");
        String[] origins = java.util.Arrays.stream(specified.split(",")).map(String::trim).filter(s -> !s.isBlank()).toArray(String[]::new);
        return new WebMvcConfigurer() {
            @Override public void addCorsMappings(CorsRegistry r) {
                r.addMapping("/api/**").allowedOrigins(origins).allowedMethods("GET","POST","PUT","DELETE","OPTIONS")
                    .allowedHeaders("Authorization","Content-Type").maxAge(3600);
            }
        };
    }
}
