
/* RoadChange Insight corporate-report workspace. Separate from baseline demo application. */
(function(){
 'use strict';
 const esc = x => String(x==null?'':x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const n=x=>Number(x||0).toLocaleString('ko-KR');
 const money=x=>n(x)+'원';
 const fmt=x=>x==null?'측정 전':Number(x).toLocaleString('ko-KR',{maximumFractionDigits:2});
 let root, strategy, pilots, tab='model',busy=false;
 async function req(url,options){
   const res=await fetch(url,Object.assign({credentials:'same-origin'},options||{}));
   let value;try{value=await res.json()}catch{value={detail:'서버 오류'}};
   if(!res.ok)throw Error(typeof value.detail==='string'?value.detail:'요청에 실패했습니다');
   return value;
 }
 const head=(num,name,explain)=>'<div class="rc-section"><span class="rc-number">'+num+'</span><h2>'+name+'</h2><p>'+explain+'</p></div>';
 const button=(action,label,cls='')=>'<button type="button" class="rc-button '+cls+'" data-report-action="'+action+'">'+label+'</button>';
 function main(){
   const hero='<div class="rc-head"><div class="rc-overline">MOBILITY DATA INTELLIGENCE / INVESTOR EDITION</div><div class="rc-head-layout"><div><h1>RoadChange Insight</h1><p class="rc-subtitle">도로 변경 정보로 학습 데이터를 더 정확하게 찾는 위치 기반 데이터 큐레이션. 현대오토에버의 정밀지도 역량에서 출발한 독립적인 교육용 사업 검증 보고서입니다.</p></div><span class="rc-eyebadge">HINT · BUSINESS REVIEW / 2026</span></div></div>';
   const stats='<div class="rc-hero"><div class="rc-hero-copy"><small>THE OPPORTUNITY</small><h2>변경된 도로에서<br>새로운 학습 장면을 찾다.</h2><p>기존의 이벤트 수집과 Hard Example Mining을 대체하지 않습니다. 도로 변경 위치·시점으로 새로운 후보를 탐색하고, 실제 추가 발견 효과를 동일 조건의 파일럿에서 검증합니다.</p></div><div class="rc-hero-stats"><article><small>유효 장면 확보시간 · 목표</small><strong>20 <i>→</i> 13.5</strong><span>분 / 건 · 검증 전 가정</span></article><article><small>검수 통과율 · 목표</small><strong>20 <i>→</i> 40</strong><span>% · 검증 전 가정</span></article></div></div>';
   const tabs='<div class="rc-tabs" role="tablist" aria-label="사업·실증 메뉴">'+[['model','사업모델 7칸'],['risks','투자 리스크'],['pilots','실증 지표'],['finance','수익성 가정']].map(([id,label])=>'<button type="button" role="tab" data-report-tab="'+id+'" aria-selected="'+(tab===id)+'">'+label+'</button>').join('')+'</div>';
   root.innerHTML='<section class="rc-report">'+hero+stats+'<div class="rc-disclaimer">시연용 사업 제안 · 현대자동차·기아·42dot·현대오토에버의 공식 제품이나 계약이 아닙니다. 목표·가정과 실측값을 구분합니다.</div>'+tabs+'<div id="rc-report-body">'+body()+'</div></section>';
 }
 function body(){
   if(tab==='model')return model();
   if(tab==='risks')return risks();
   if(tab==='pilots')return experiment();
   return finance();
 }
 function model(){
   return head('01 / BUSINESS MODEL','사업 한 장 · 7가지 질문','확인된 사실과 아직 검증해야 할 가정을 분리해 읽습니다.')
   +'<div class="rc-canvas">'+(strategy.sections||[]).map(x=>'<article class="rc-cell"><h3><span>'+esc(x.n)+'</span>'+esc(x.title)+'</h3><p>'+esc(x.text)+'</p><span class="rc-tag">'+esc(x.tag)+'</span></article>').join('')+'</div>'
   +head('02 / EVIDENCE & ASSUMPTIONS','근거의 경계','공식 기술 소개와 사업 성립 조건을 서로 구분합니다.')
   +'<div class="rc-cards"><section class="rc-card"><h3>기술적 출발점</h3><p>정밀지도·도로 변경 정보와 자율주행 데이터 선별에 관한 공개 자료를 바탕으로 가설을 세웠습니다. 회사 내부 시스템과 직접 연결된다는 뜻은 아닙니다.</p>'+(strategy.sources||[]).map(s=>'<a href="'+esc(s.url)+'" target="_blank" rel="noopener noreferrer">'+esc(s.title)+' ↗</a>').join('')+'</section><section class="rc-card"><h3>우선 확인할 부분</h3><p>주행 영상·지도 변경 데이터 접근권한, 기존 탐색 대비 신규 유효 장면 수, 고객의 지불 의사, 서비스 구축 원가와 계약 단위는 아직 확인되지 않았습니다.</p></section></div>';
 }
 function risks(){
   return head('01 / INVESTMENT RISKS','투자자가 먼저 물을 질문','다섯 가지 핵심 위험에 대한 증빙 상태와 근거를 기록합니다.')
   +'<div>'+strategy.risks.map((r,i)=>'<article class="rc-risk"><div class="rc-risk-index">'+String(i+1).padStart(2,'0')+'</div><div><strong>'+esc(r.title)+'</strong><span class="rc-status '+(r.state==='증빙 확보'?'done':'')+'">'+esc(r.state)+'</span><small>'+esc(r.question)+'</small><p>확인할 일: '+esc(r.action)+'</p>'+(r.note?'<small>기록: '+esc(r.note)+'</small>':'')+'</div>'+button('risk:'+esc(r.code),'증빙 관리')+'</article>').join('')+'</div>'
   +head('02 / PRIORITY','가장 먼저 검증할 2가지','기존 기술 대비 차별성과 유료 구매 의사를 우선 확인해야 합니다.')
   +'<div class="rc-cards"><div class="rc-card"><h3>유효 장면 추가 발견</h3><p>기존 방식과 제안 방식에 동일 데이터를 적용하고 중복 제외 후 추가 발견 건수를 비교합니다.</p></div><div class="rc-card"><h3>구매 담당자·데이터 접근 권한</h3><p>실증 데이터 접근 가능성과 실제 예산 집행·계약 승인을 확인해야 사업 추진 여부를 판단할 수 있습니다.</p></div></div>';
 }
 function experiment(){
   const summary=pilots.summary||{},a=summary.baseline||{},b=summary.proposal||{},records=pilots.records||[];
   const k=(label,value,desc)=>'<div class="rc-kpi"><small>'+label+'</small><strong>'+value+'</strong><p>'+desc+'</p></div>';
   return head('01 / PILOT VALIDATION','기존 방식과 제안 방식의 비교','아래 숫자는 입력된 기록만으로 산출됩니다. 사용자 입력은 별도의 외부 검증을 의미하지 않습니다.')
   +'<div class="rc-3col">'+k('기존 방식 검수 통과율',fmt(a.pass_rate_pct)+'%',n(a.inspected||0)+'건 검수')+k('제안 방식 검수 통과율',fmt(b.pass_rate_pct)+'%',n(b.inspected||0)+'건 검수')+k('유효 장면 1건당 소요시간',fmt(b.minutes_per_accepted)+'분','제안 방식 실측 기록 기준')+'</div>'
   +'<div class="rc-balance" style="margin-top:15px"><small>동일 조건 비교가 필요합니다 · 시간 단축률</small><strong>'+(summary.time_reduction_pct==null?'비교 데이터 없음':fmt(summary.time_reduction_pct)+'%')+'</strong></div>'
   +head('02 / ADD A TRIAL','검수 기록 등록','동일한 조건의 검수 기록을 입력해 비교합니다.')
   +'<div class="rc-2col"><section class="rc-card"><form class="rc-form" id="rc-pilot-form"><label>비교 방식<select name="mode"><option value="baseline">기존 방식</option><option value="proposal">제안 방식</option></select></label><label>실증 회차 이름<input name="label" placeholder="예: 광주 실증 시연" required minlength="2" maxlength="140"></label><div class="rc-2col"><label>검수 시도(건)<input name="inspected" type="number" min="1" required></label><label>유효 확정(건)<input name="accepted" type="number" min="0" required></label><label>중복 제외(건)<input name="duplicate_count" type="number" min="0" value="0" required></label><label>투입 시간(분)<input name="reviewer_minutes" type="number" min="0.01" step="any" required></label></div><label>운전자 비개입 유효 장면(건)<input name="no_intervention_accepted" type="number" min="0" value="0" required></label><label>검증 방법·실측 자료 메모<textarea name="evidence_note" rows="3" maxlength="1200"></textarea></label><button type="submit" class="rc-button primary">실증 기록 저장</button><div class="rc-message" id="rc-pilot-msg"></div></form></section><section class="rc-card"><h3>검수 기록</h3>'+(records.length?'<div style="overflow:auto"><table class="rc-table"><thead><tr><th>구분</th><th>검수</th><th>유효</th><th>시간</th><th></th></tr></thead><tbody>'+records.map(r=>'<tr><td>'+esc(r.mode==='baseline'?'기존':'제안')+'<br>'+esc(r.label)+'</td><td>'+n(r.inspected)+'</td><td>'+n(r.accepted)+'</td><td>'+n(r.reviewer_minutes)+'분</td><td>'+button('remove:'+r.id,'삭제')+'</td></tr>').join('')+'</tbody></table></div>':'<div class="rc-empty">아직 입력된 실증 기록이 없습니다.<br>실측값 없이 성과를 확정하지 않습니다.</div>')+'</section></div>';
 }
 function finance(){
   const s=strategy.scenario||{};
   const fields=[['annual_price','연간 계약가 (원)'],['one_time_build','초기 개발비 (원)'],['annual_fixed','공통 연간 운영비 (원)'],['annual_per_customer','고객별 연간 지원비 (원)'],['customer_count','계약 고객 수']];
   return head('01 / UNIT ECONOMICS','수익 구조 시나리오','실제 수주 실적이나 확정 비용이 아닌, 사용자가 변경할 수 있는 사업 가정입니다.')
   +'<div class="rc-2col"><section class="rc-card"><h3>사업 가정 입력</h3><form class="rc-form" id="rc-scenario-form">'+fields.map(([id,label])=>'<label>'+label+'<input name="'+id+'" type="number" min="0" max="10000000000" value="'+Number(s[id]||0)+'" required></label>').join('')+'<button type="submit" class="rc-button primary">가정 저장 · 재계산</button><div id="rc-scenario-msg" class="rc-message"></div></form></section><section class="rc-card"><h3>첫해 비용·매출 추정</h3><table class="rc-table"><tbody><tr><th>계약 고객</th><td>'+n(s.customer_count)+'건</td></tr><tr><th>연간 매출</th><td>'+money(s.revenue)+'</td></tr><tr><th>첫해 산입 비용</th><td>'+money(s.first_year_expense)+'</td></tr><tr><th>손익분기 고객 수</th><td>'+(s.break_even_customers==null?'계산 불가':n(s.break_even_customers)+'건')+'</td></tr></tbody></table><div class="rc-balance" style="margin-top:20px"><small>미반영 비용 차감 전 차액</small><strong>'+money(s.first_year_balance_before_unlisted_costs)+'</strong></div><p class="rc-note">세금, 추가 보안 심사, 영상 처리·저장, 법률·영업 비용은 미반영입니다. 손익이 보장되는 계산이 아닙니다.</p></section></div>';
 }
 async function load(){
   try{
     const result=await Promise.all([req('/api/strategy'),req('/api/strategy/pilots')]);
     strategy=result[0];pilots=result[1];busy=false;
     if(root && document.contains(root))main();
   }catch(e){busy=false;if(root)root.innerHTML='<div class="rc-empty">보고서를 불러오지 못했습니다. '+esc(e.message)+'</div>'}
 }
 function showEditor(code){
   const r=(strategy.risks||[]).find(x=>x.code===code);if(!r)return;
   const area=root.querySelector('#rc-report-body');
   area.innerHTML=head('UPDATE / EVIDENCE','증빙 관리 · '+esc(r.code),'상태와 증빙 기록은 로그인 계정의 데이터베이스에 저장됩니다.')
    +'<section class="rc-card"><h3>'+esc(r.title)+'</h3><p>'+esc(r.question)+'</p><form class="rc-form" id="rc-risk-form"><input type="hidden" name="code" value="'+esc(r.code)+'"><label>증빙 상태<select name="state">'+['미확인','검증 중','증빙 확보'].map(x=>'<option '+(x===r.state?'selected':'')+'>'+x+'</option>').join('')+'</select></label><label>증빙 URL · 실증 결과 · 아직 남은 쟁점<textarea name="note" rows="5" maxlength="1200">'+esc(r.note||'')+'</textarea></label><div style="display:flex;gap:9px">'+button('back','뒤로')+'<button type="submit" class="rc-button primary">저장</button></div><div id="rc-risk-msg" class="rc-message"></div></form></section>';
 }
 async function saveForm(form,url,method,notify){
   const data=Object.fromEntries(new FormData(form).entries());
   Object.keys(data).forEach(k=>{if(['inspected','accepted','duplicate_count','reviewer_minutes','no_intervention_accepted','annual_price','one_time_build','annual_fixed','annual_per_customer','customer_count'].includes(k))data[k]=Number(data[k])});
   if('code' in data)delete data.code;
   await req(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
   await load();notify();
 }
 function mount(node){
   root=node;root.innerHTML='<div class="rc-empty">사업 검증 보고서를 불러오는 중입니다.</div>';
   load();
   node.onclick=async function(e){
     const t=e.target.closest('button');if(!t||!node.contains(t))return;
     if(t.dataset.reportTab){tab=t.dataset.reportTab;main();return}
     const action=t.dataset.reportAction||'';
     if(action==='back'){main();return}
     if(action.startsWith('risk:')){showEditor(action.slice(5));return}
     if(action.startsWith('remove:')){
       if(!confirm('해당 실증 기록을 삭제하시겠습니까?'))return;
       try{await req('/api/strategy/pilots/'+encodeURIComponent(action.slice(7)),{method:'DELETE'});await load()}catch(err){alert(err.message)}
     }
   };
   node.onsubmit=async function(e){
     const f=e.target;if(!['rc-pilot-form','rc-scenario-form','rc-risk-form'].includes(f.id))return;
     e.preventDefault();if(!f.reportValidity())return;
     if(busy)return;busy=true;
     const target=f.querySelector('.rc-message')||root.querySelector('#rc-risk-msg');
     try{
       if(f.id==='rc-pilot-form')await saveForm(f,'/api/strategy/pilots','POST',()=>{});
       if(f.id==='rc-scenario-form')await saveForm(f,'/api/strategy/scenario','PUT',()=>{});
       if(f.id==='rc-risk-form'){
         const code=new FormData(f).get('code');
         await saveForm(f,'/api/strategy/risks/'+encodeURIComponent(code),'PUT',()=>{});
         main();
       }
     }catch(err){if(target)target.textContent=err.message;else alert(err.message)}
     finally{busy=false}
   };
 }
 window.RoadChangeReport={mount};
})();
