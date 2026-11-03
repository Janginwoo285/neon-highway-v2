package app.dodge;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;

import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/game")
public class GameController {
  private final JdbcTemplate jdbc;
  private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder(12);
  private final SecureRandom random = new SecureRandom();
  private static final long WEEK = 7L * 24 * 60 * 60 * 1000;
  GameController(JdbcTemplate jdbc) { this.jdbc = jdbc; }
  record Credentials(String username, String password, String nickname) {}
  record Score(double score, double survived) {}

  private long now() { return Instant.now().toEpochMilli(); }
  private ResponseEntity<?> bad(String message) { return ResponseEntity.badRequest().body(Map.of("error",message)); }
  private String hash(String token) {
    try {
      byte[] bytes=MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8));
      return HexFormat.of().formatHex(bytes);
    } catch(Exception e) { throw new IllegalStateException(e); }
  }
  private String newToken() {
    byte[] b = new byte[32]; random.nextBytes(b);
    return Base64.getUrlEncoder().withoutPadding().encodeToString(b);
  }
  private Long owner(String authorization) {
    if(authorization==null || !authorization.startsWith("Bearer ")) return null;
    String token=authorization.substring(7);
    if(token.length()<30 || token.length()>200) return null;
    List<Long> users=jdbc.query("SELECT user_id FROM game_sessions WHERE token_hash=? AND expires_at>?",
      (rs,i)->rs.getLong(1), hash(token), now());
    return users.isEmpty()?null:users.get(0);
  }
  private Map<String,Object> account(long id) {
    return jdbc.queryForMap("SELECT id,username,nickname FROM game_users WHERE id=?",id);
  }
  private ResponseEntity<?> issue(long id) {
    String token=newToken();
    jdbc.update("INSERT INTO game_sessions(token_hash,user_id,expires_at) VALUES(?,?,?)",hash(token),id,now()+WEEK);
    return ResponseEntity.ok(Map.of("token",token,"user",account(id)));
  }

  @GetMapping("/health")
  public Map<String,Object> health(){return Map.of("status","ok","service","dodge-api");}

  @PostMapping("/auth/register")
  public ResponseEntity<?> register(@RequestBody Credentials c) {
    if(c==null || c.username()==null || !c.username().matches("^[a-zA-Z0-9_]{4,20}$"))
      return bad("아이디는 영문, 숫자, 밑줄 4~20자여야 합니다.");
    if(c.password()==null || c.password().length()<8 || c.password().length()>72)
      return bad("비밀번호는 8~72자로 설정해 주세요.");
    String name=c.nickname()==null?"":c.nickname().trim();
    if(name.length()<2 || name.length()>12 || name.chars().anyMatch(ch -> Character.isISOControl(ch)))
      return bad("닉네임은 2~12자로 설정해 주세요.");
    String username=c.username().toLowerCase();
    try {
      jdbc.update("INSERT INTO game_users(username,pass_hash,nickname,created_at) VALUES(?,?,?,?)",
        username,encoder.encode(c.password()),name,now());
    } catch(DuplicateKeyException e) {return bad("이미 사용 중인 아이디입니다.");}
    long id=jdbc.queryForObject("SELECT id FROM game_users WHERE username=?",Long.class,username);
    return issue(id);
  }

  @PostMapping("/auth/login")
  public ResponseEntity<?> login(@RequestBody Credentials c) {
    if(c==null || c.username()==null || c.password()==null) return bad("아이디와 비밀번호를 입력해 주세요.");
    List<Map<String,Object>> matches=jdbc.queryForList("SELECT id,pass_hash FROM game_users WHERE username=?",
      c.username().toLowerCase());
    if(matches.isEmpty() || !encoder.matches(c.password(),(String)matches.get(0).get("pass_hash")))
      return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error","아이디 또는 비밀번호가 올바르지 않습니다."));
    return issue(((Number)matches.get(0).get("id")).longValue());
  }

  @GetMapping("/me")
  public ResponseEntity<?> me(@RequestHeader(value="Authorization",required=false) String auth) {
    Long id=owner(auth);
    return id==null?ResponseEntity.status(401).body(Map.of("error","로그인이 필요합니다.")):ResponseEntity.ok(account(id));
  }

  @PostMapping("/auth/logout")
  public ResponseEntity<?> logout(@RequestHeader(value="Authorization",required=false) String auth) {
    if(auth!=null && auth.startsWith("Bearer ")) jdbc.update("DELETE FROM game_sessions WHERE token_hash=?",hash(auth.substring(7)));
    return ResponseEntity.ok(Map.of("ok",true));
  }

  @GetMapping("/leaderboard")
  public Map<String,Object> leaderboard() {
    List<Map<String,Object>> top=jdbc.queryForList(
      "SELECT u.id AS id,u.nickname AS nick,s.score AS score,s.survived AS time FROM game_scores s JOIN game_users u ON u.id=s.user_id ORDER BY s.score DESC,s.updated_at ASC LIMIT 50");
    return Map.of("scores",top,"count",top.size());
  }

  @PostMapping("/scores")
  public ResponseEntity<?> submit(@RequestHeader(value="Authorization",required=false) String auth,@RequestBody Score s) {
    Long id=owner(auth);
    if(id==null) return ResponseEntity.status(401).body(Map.of("error","기록 등록은 로그인 후 이용할 수 있습니다."));
    if(s==null || !Double.isFinite(s.score()) || !Double.isFinite(s.survived()) ||
      s.score()<0.1 || s.score()>99999 || s.survived()<0.1 || s.survived()>7200 ||
      s.score()+0.1<s.survived() || s.score()>s.survived()*4.5+2)
      return bad("기록 값이 올바르지 않습니다.");
    double score=Math.floor(s.score()*10)/10.0;
    double survived=Math.floor(s.survived()*10)/10.0;
    long time=now();
    int changed=jdbc.update("UPDATE game_scores SET score=?,survived=?,updated_at=? WHERE user_id=? AND score<?",
      score,survived,time,id,score);
    if(changed==0) {
      Integer count=jdbc.queryForObject("SELECT COUNT(*) FROM game_scores WHERE user_id=?",Integer.class,id);
      if(count!=null && count==0) {
        try { jdbc.update("INSERT INTO game_scores(user_id,score,survived,updated_at) VALUES(?,?,?,?)",id,score,survived,time); }
        catch(DuplicateKeyException e) {
          jdbc.update("UPDATE game_scores SET score=?,survived=?,updated_at=? WHERE user_id=? AND score<?",score,survived,time,id,score);
        }
      }
    }
    return ResponseEntity.ok(Map.of("ok",true));
  }
}
