package app.letterday;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import java.time.LocalDate;
import java.util.*;
import java.util.regex.Pattern;

@RestController
@RequestMapping("/api")
public class ApiController {
    private final JdbcTemplate db;
    private final BCryptPasswordEncoder passwords = new BCryptPasswordEncoder(12);
    private final SecureRandom rng = new SecureRandom();
    private static final Pattern EMAIL = Pattern.compile("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$");
    private static final Set<String> MOODS = Set.of("행복","평온","슬픔","불안");
    private static final Set<String> VISIBILITIES = Set.of("public","private");

    public ApiController(JdbcTemplate db) { this.db=db; }
    private ResponseStatusException error(HttpStatus code,String msg){ return new ResponseStatusException(code,msg); }
    private String hash(String plain){
        try { byte[] b=MessageDigest.getInstance("SHA-256").digest(plain.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(b);
        } catch(Exception e){throw new IllegalStateException(e);}
    }
    private String newToken(){byte[] x=new byte[32];rng.nextBytes(x);return Base64.getUrlEncoder().withoutPadding().encodeToString(x);}
    private String user(String authorization){
        if(authorization==null||!authorization.startsWith("Bearer "))throw error(HttpStatus.UNAUTHORIZED,"로그인이 필요합니다.");
        String token=authorization.substring(7);
        if(token.length()<32||token.length()>256)throw error(HttpStatus.UNAUTHORIZED,"로그인이 필요합니다.");
        List<String> ids=db.query("SELECT user_id FROM login_session WHERE token_hash=? AND expires_at>?",
            (rs,row)->rs.getString(1),hash(token),Instant.now().toString());
        if(ids.isEmpty())throw error(HttpStatus.UNAUTHORIZED,"로그인 세션이 만료되었습니다.");
        return ids.get(0);
    }
    private String value(JsonNode obj,String key,int max){
        String s=obj.path(key).asText("").trim();
        if(s.length()>max)throw error(HttpStatus.BAD_REQUEST,key+" 길이 제한을 초과했습니다.");
        return s;
    }
    private void require(boolean condition,String msg){if(!condition)throw error(HttpStatus.BAD_REQUEST,msg);}
    private Map<String,Object> session(String uid){
        String token=newToken();
        db.update("INSERT INTO login_session(token_hash,user_id,expires_at) VALUES(?,?,?)",
                hash(token),uid,Instant.now().plusSeconds(60L*60*24*7).toString());
        return Map.of("token",token);
    }
    @PostMapping("/auth/register")
    public Map<String,Object> register(@RequestBody JsonNode body){
        String email=value(body,"email",254).toLowerCase(Locale.ROOT),password=body.path("password").asText("");
        require(EMAIL.matcher(email).matches()&&email.length()>=5,"올바른 이메일을 입력해 주세요.");
        require(password.length()>=8&&password.length()<=72,"비밀번호는 8~72자여야 합니다.");
        if(!db.query("SELECT id FROM app_user WHERE email=?",(r,n)->r.getString(1),email).isEmpty())
            throw error(HttpStatus.CONFLICT,"이미 등록된 이메일입니다.");
        String uid=UUID.randomUUID().toString();
        db.update("INSERT INTO app_user(id,email,password_hash,created_at) VALUES(?,?,?,?)",
                uid,email,passwords.encode(password),Instant.now().toString());
        return session(uid);
    }
    @PostMapping("/auth/login")
    public Map<String,Object> login(@RequestBody JsonNode body){
        String email=value(body,"email",254).toLowerCase(Locale.ROOT),pass=body.path("password").asText("");
        List<Map<String,Object>> rows=db.queryForList("SELECT id,password_hash FROM app_user WHERE email=?",email);
        if(rows.isEmpty()||!passwords.matches(pass,(String)rows.get(0).get("password_hash")))
            throw error(HttpStatus.UNAUTHORIZED,"이메일 또는 비밀번호가 올바르지 않습니다.");
        return session((String)rows.get(0).get("id"));
    }
    @PostMapping("/auth/logout")
    public ResponseEntity<Void> logout(@RequestHeader(value="Authorization",required=false)String auth){
        user(auth);db.update("DELETE FROM login_session WHERE token_hash=?",hash(auth.substring(7)));
        return ResponseEntity.noContent().build();
    }
    private Map<String,Object> mapEntry(java.sql.ResultSet rs)throws java.sql.SQLException{
        Map<String,Object> m=new LinkedHashMap<>();
        m.put("id",rs.getString("id"));m.put("date",rs.getString("entry_date"));
        m.put("title",rs.getString("title"));m.put("body",rs.getString("body"));
        m.put("mood",rs.getString("mood"));m.put("visibility",rs.getString("visibility"));
        m.put("photo",rs.getString("photo"));m.put("drawing",rs.getString("drawing"));
        return m;
    }
    @GetMapping("/entries")
    public List<Map<String,Object>> entries(@RequestHeader(value="Authorization",required=false)String auth){
        return db.query("SELECT * FROM journal_entry WHERE user_id=? ORDER BY entry_date DESC,created_at DESC",
                (rs,n)->mapEntry(rs),user(auth));
    }
    private record Entry(String date,String title,String body,String mood,String visibility,String photo,String drawing){}
    private String image(JsonNode node,String key){
        String v=node.path(key).asText("");
        require(v.length()<=1_500_000,"첨부 이미지 용량이 너무 큽니다.");
        require(v.isEmpty()||v.matches("^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$"),
                "PNG, JPEG, WebP 데이터만 가능합니다.");
        return v;
    }
    private Entry parse(JsonNode b){
        String date=value(b,"date",10),title=value(b,"title",90),body=value(b,"body",10000),
               mood=value(b,"mood",20),visibility=value(b,"visibility",10);
        try {LocalDate.parse(date);}catch(Exception ex){throw error(HttpStatus.BAD_REQUEST,"날짜 형식이 올바르지 않습니다.");}
        require(!title.isBlank()&&!body.isBlank(),"제목과 내용을 입력해 주세요.");
        require(MOODS.contains(mood),"감정 값이 올바르지 않습니다.");
        require(VISIBILITIES.contains(visibility),"공개 설정 값이 올바르지 않습니다.");
        return new Entry(date,title,body,mood,visibility,image(b,"photo"),image(b,"drawing"));
    }
    @PostMapping("/entries")
    public Map<String,String> create(@RequestHeader(value="Authorization",required=false)String auth,@RequestBody JsonNode b){
        String uid=user(auth);Entry e=parse(b);String id=UUID.randomUUID().toString(),now=Instant.now().toString();
        db.update("INSERT INTO journal_entry(id,user_id,entry_date,title,body,mood,visibility,photo,drawing,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                id,uid,e.date,e.title,e.body,e.mood,e.visibility,e.photo,e.drawing,now,now);
        return Map.of("id",id);
    }
    @PutMapping("/entries/{id}")
    public Map<String,String> update(@RequestHeader(value="Authorization",required=false)String auth,@PathVariable String id,@RequestBody JsonNode b){
        String uid=user(auth);Entry e=parse(b);
        int n=db.update("UPDATE journal_entry SET entry_date=?,title=?,body=?,mood=?,visibility=?,photo=?,drawing=?,updated_at=? WHERE id=? AND user_id=?",
                e.date,e.title,e.body,e.mood,e.visibility,e.photo,e.drawing,Instant.now().toString(),id,uid);
        if(n==0)throw error(HttpStatus.NOT_FOUND,"편지를 찾을 수 없습니다.");
        return Map.of("id",id);
    }
    @DeleteMapping("/entries/{id}")
    public ResponseEntity<Void> delete(@RequestHeader(value="Authorization",required=false)String auth,@PathVariable String id){
        int n=db.update("DELETE FROM journal_entry WHERE id=? AND user_id=?",id,user(auth));
        if(n==0)throw error(HttpStatus.NOT_FOUND,"편지를 찾을 수 없습니다.");
        return ResponseEntity.noContent().build();
    }
    @GetMapping("/feed")
    public List<Map<String,Object>> feed(){
        return db.query("SELECT e.*,u.email FROM journal_entry e JOIN app_user u ON e.user_id=u.id WHERE e.visibility='public' ORDER BY e.created_at DESC LIMIT 50",
                (rs,n)->{Map<String,Object> m=mapEntry(rs);String email=rs.getString("email");m.put("author",email.split("@")[0].replaceAll("[^a-zA-Z0-9_.-]","").substring(0,Math.min(12,email.split("@")[0].replaceAll("[^a-zA-Z0-9_.-]","").length())));return m;});
    }
    @GetMapping("/health")
    public Map<String,String> health(){return Map.of("status","ok");}
}
