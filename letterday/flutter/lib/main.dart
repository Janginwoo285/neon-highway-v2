import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() => runApp(const LetterdayApp());
class LetterdayApp extends StatelessWidget {
  const LetterdayApp({super.key});
  @override Widget build(BuildContext context)=>MaterialApp(
    title:'Letterday',
    theme:ThemeData(useMaterial3:true,scaffoldBackgroundColor:const Color(0xfffaf2e9),
      colorScheme:ColorScheme.fromSeed(seedColor:const Color(0xffb76e57))),
    home:const JournalHome());
}
class JournalHome extends StatefulWidget {
  const JournalHome({super.key});
  @override State<JournalHome> createState()=>_JournalHomeState();
}
class _JournalHomeState extends State<JournalHome> {
  final api=TextEditingController(),email=TextEditingController(),pass=TextEditingController(),
    title=TextEditingController(),body=TextEditingController();
  String token='',mood='평온',visibility='private'; int selected=0;
  List<dynamic> mine=[],publicLetters=[];
  void note(String m){ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text(m)));}
  Future<dynamic> request(String path,{String method='GET',Object? data})async{
    final base=api.text.trim().replaceAll(RegExp(r'/+$'),'');
    if(!base.startsWith('https://')&&!base.startsWith('http://localhost'))throw Exception('HTTPS API 주소를 입력해 주세요.');
    final r=await http.Request(method,Uri.parse(base+path))
      ..headers.addAll({'Content-Type':'application/json',if(token.isNotEmpty)'Authorization':'Bearer '+token})
      ..body=data==null?'':jsonEncode(data);
    final client=http.Client();
    try{
      final stream=await client.send(r),result=await http.Response.fromStream(stream);
      final json=result.body.isEmpty?{}:jsonDecode(result.body);
      if(result.statusCode>=400)throw Exception('서버 오류: '+result.statusCode.toString());
      return json;
    }finally{client.close();}
  }
  Future<void> login(bool register)async{
    try{
      final r=await request(register?'/api/auth/register':'/api/auth/login',
        method:'POST',data:{'email':email.text,'password':pass.text});
      token=r['token'] as String; pass.clear();await refresh();note('로그인했습니다.');
    }catch(e){note(e.toString());}
  }
  Future<void> refresh()async{
    try{
      if(token.isNotEmpty)mine=await request('/api/entries') as List;
      publicLetters=await request('/api/feed') as List;
      if(mounted)setState((){});
    }catch(e){note(e.toString());}
  }
  Future<void> save()async{
    if(token.isEmpty){note('먼저 로그인해 주세요.');return;}
    if(title.text.trim().isEmpty||body.text.trim().isEmpty){note('제목과 내용을 입력해 주세요.');return;}
    try{
      await request('/api/entries',method:'POST',data:{
        'date':DateTime.now().toIso8601String().substring(0,10),
        'title':title.text.trim(),'body':body.text.trim(),'mood':mood,
        'visibility':visibility,'photo':'','drawing':''
      });
      title.clear();body.clear();await refresh();setState(()=>selected=1);note('편지를 저장했습니다.');
    }catch(e){note(e.toString());}
  }
  Future<void> remove(String id)async{
    try{await request('/api/entries/'+Uri.encodeComponent(id),method:'DELETE');await refresh();}catch(e){note(e.toString());}
  }
  Widget box(TextEditingController c,String label,{int lines=1,bool secret=false})=>Padding(
    padding:const EdgeInsets.only(bottom:12),
    child:TextField(controller:c,maxLines:lines,obscureText:secret,decoration:InputDecoration(
      labelText:label,filled:true,fillColor:Colors.white,border:OutlineInputBorder(borderRadius:BorderRadius.circular(14)))));
  Widget write()=>ListView(padding:const EdgeInsets.all(18),children:[
    const Text('Dear, 오늘의 나에게',style:TextStyle(fontSize:26,fontFamily:'serif')),
    const SizedBox(height:16),box(title,'편지 제목'),box(body,'오늘의 마음',lines:8),
    DropdownButtonFormField<String>(value:mood,decoration:const InputDecoration(labelText:'감정'),
      items:['행복','평온','슬픔','불안'].map((m)=>DropdownMenuItem(value:m,child:Text(m))).toList(),
      onChanged:(x)=>setState(()=>mood=x??mood)),
    const SizedBox(height:14),
    DropdownButtonFormField<String>(value:visibility,decoration:const InputDecoration(labelText:'공개 범위'),
      items:const [DropdownMenuItem(value:'private',child:Text('비공개')),DropdownMenuItem(value:'public',child:Text('모두에게 공개'))],
      onChanged:(x)=>setState(()=>visibility=x??visibility)),
    const SizedBox(height:18),FilledButton(onPressed:save,child:const Text('편지 저장')),
    const SizedBox(height:14),const Text('사진·그림 첨부와 알림은 현재 웹 버전에서 제공됩니다.',style:TextStyle(fontSize:12))
  ]);
  Widget letters(List<dynamic> data,{bool own=false})=>RefreshIndicator(onRefresh:refresh,child:ListView(
    padding:const EdgeInsets.all(14),children:data.isEmpty?[const Padding(padding:EdgeInsets.all(25),child:Text('아직 편지가 없습니다.'))]:
    data.map((row){
      final e=Map<String,dynamic>.from(row as Map);
      return Card(color:const Color(0xfffffdf9),child:Padding(padding:const EdgeInsets.all(17),child:
        Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
          Text((e['date']??'').toString()+' · '+(e['mood']??'').toString(),
            style:const TextStyle(color:Color(0xff9d7968),fontSize:12)),
          const SizedBox(height:7),Text((e['title']??'').toString(),style:const TextStyle(fontSize:18,fontWeight:FontWeight.bold)),
          const SizedBox(height:8),Text((e['body']??'').toString(),style:const TextStyle(height:1.65)),
          if(own)Align(alignment:Alignment.centerRight,
            child:TextButton(onPressed:()=>remove((e['id']??'').toString()),child:const Text('삭제')))
        ]))));
    }).toList()));
  Widget settings()=>ListView(padding:const EdgeInsets.all(18),children:[
    const Text('서버 · 계정 설정',style:TextStyle(fontSize:25)),
    const SizedBox(height:18),box(api,'HTTPS Spring 서버 주소'),
    const Text('공개 서버를 배포한 후 주소를 입력하세요.',style:TextStyle(fontSize:12)),
    const SizedBox(height:15),box(email,'이메일'),box(pass,'비밀번호',secret:true),
    Wrap(spacing:8,children:[
      OutlinedButton(onPressed:()=>login(true),child:const Text('회원가입')),
      FilledButton(onPressed:()=>login(false),child:const Text('로그인')),
      TextButton(onPressed:(){setState((){token='';mine=[];});note('로그아웃했습니다.');},child:const Text('로그아웃'))
    ]),
    Text(token.isNotEmpty?'로그인된 상태입니다.':'로그인이 필요합니다.'),
    const SizedBox(height:12),const Text('이 Flutter MVP는 API 서버 연결 전에는 계정 기능이 동작하지 않으며, 재시작하면 로그인이 해제됩니다.',style:TextStyle(fontSize:12))
  ]);
  @override Widget build(BuildContext context)=>Scaffold(
    appBar:AppBar(title:const Text('letterday ✳',style:TextStyle(fontFamily:'serif',fontSize:28)),
      actions:[IconButton(onPressed:refresh,icon:const Icon(Icons.refresh))]),
    body:[write(),letters(mine,own:true),letters(publicLetters),settings()][selected],
    bottomNavigationBar:NavigationBar(selectedIndex:selected,onDestinationSelected:(i){setState(()=>selected=i);if(i==1||i==2)refresh();},
      destinations:const [
        NavigationDestination(icon:Icon(Icons.edit_note),label:'편지 쓰기'),
        NavigationDestination(icon:Icon(Icons.mail_outline),label:'내 편지함'),
        NavigationDestination(icon:Icon(Icons.people_outline),label:'모두의 편지'),
        NavigationDestination(icon:Icon(Icons.settings),label:'설정')
      ])
  );
  @override void dispose(){api.dispose();email.dispose();pass.dispose();title.dispose();body.dispose();super.dispose();}
}
