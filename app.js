const fallbackLeagues = {
  north: {
    title: '북부리그', english: 'NORTH LEAGUE', color: '#174ea6', leader: '상무', magic: 17,
    teams: [
      {name:'상무', g:77,w:48,l:29,d:0,remain:23,color:'#ef3124'},
      {name:'한화', g:87,w:50,l:37,d:0,remain:13,color:'#f37321'},
      {name:'LG', g:85,w:44,l:40,d:1,remain:15,color:'#c30452'},
      {name:'고양', g:83,w:38,l:45,d:0,remain:17,color:'#7d1638'},
      {name:'두산', g:88,w:38,l:50,d:0,remain:12,color:'#131230'},
      {name:'SSG', g:85,w:32,l:53,d:0,remain:15,color:'#ce0e2d'}
    ], daily:[21,21,20,19,18,17,17]
  },
  south: {
    title: '남부리그', english: 'SOUTH LEAGUE', color: '#e8472f', leader: '울산', magic: 20,
    teams: [
      {name:'울산', g:78,w:48,l:29,d:1,remain:22,color:'#0b4da2'},
      {name:'롯데', g:78,w:47,l:30,d:1,remain:22,color:'#041e42'},
      {name:'NC', g:83,w:44,l:39,d:0,remain:17,color:'#315288'},
      {name:'KIA', g:83,w:38,l:45,d:0,remain:17,color:'#ea0029'},
      {name:'KT', g:82,w:35,l:46,d:1,remain:18,color:'#231f20'},
      {name:'삼성', g:83,w:32,l:51,d:0,remain:17,color:'#074ca1'}
    ], daily:[24,23,23,22,21,21,20]
  }
};

const leagues = window.KBO_DATA?.leagues || fallbackLeagues;

let current='north';
const $=selector=>document.querySelector(selector);

function pct(team){return (team.w/(team.w+team.l)).toFixed(3).replace(/^0/,'')}

function gamesBehind(team, leader){
  const value=((leader.w-team.w)+(team.l-leader.l))/2;
  return value===0?'—':Number.isInteger(value)?String(value):value.toFixed(1);
}

function winsToClinchRank(team, teams, targetRank){
  const rivalMaximums=teams.filter(t=>t!==team).map(t=>(t.w+t.remain)/(t.w+t.l+t.remain)).sort((a,b)=>b-a);
  const threshold=rivalMaximums[targetRank-1];
  if(threshold===undefined) return 0;
  const finalDecisions=team.w+team.l+team.remain;
  for(let wins=0;wins<=team.remain;wins++) if((team.w+wins)/finalDecisions>threshold) return wins;
  return null;
}

function render(key){
  current=key; const league=leagues[key]; const leader=league.teams[0];
  document.documentElement.style.setProperty('--accent',league.color);
  $('#leagueTitle').textContent=league.title;
  $('#leagueEnglish').textContent=league.english;
  document.title=`${league.title} 매직넘버 · 퓨처스 넘버`;
  document.querySelectorAll('.league-tab').forEach(el=>el.classList.toggle('active',el.dataset.league===key));
  $('#leaderCard').innerHTML=`<div class="leader-name"><small>RANK SCENARIO · TOP 5</small><h3>${league.teams.length}개 팀 × 5개 순위</h3><p>현재 ${leader.name} 선두 · 모든 팀의 1~5위 자력 확정 가능성을 계산합니다.</p></div><div class="magic-display"><div><small>확인할 순위 시나리오</small><b>SELF-CLINCH<br>CASES</b></div><div class="magic-number">${league.teams.length*5}<sup>개</sup></div></div>`;
  $('#rankMatrixBody').innerHTML=league.teams.map((team,currentRank)=>{
    const cells=[1,2,3,4,5].map(target=>{
      const need=winsToClinchRank(team,league.teams,target);
      const value=need===0?'<span class="matrix-value done">확정</span>':need===null?'<span class="matrix-value help">타력</span>':`<span class="matrix-value">${need}</span>`;
      return `<td class="${target===currentRank+1?'matrix-target':''}" title="${target}위 이내 자력 확정">${value}</td>`;
    }).join('');
    return `<tr><td><div class="matrix-team"><span class="team-chip" style="--team:${team.color}"></span><div>${team.name}<small>현재 ${currentRank+1}위 · 잔여 ${team.remain}경기</small></div></div></td>${cells}</tr>`;
  }).join('');
  $('#standingsBody').innerHTML=league.teams.map((t,i)=>{
    return `<tr><td><span class="rank ${i===0?'one':''}">${String(i+1).padStart(2,'0')}</span></td><td><span class="team-chip" style="--team:${t.color}"></span>${t.name}</td><td>${t.g}</td><td>${t.w}-${t.l}-${t.d}</td><td>${pct(t)}</td><td>${gamesBehind(t,leader)}</td><td class="remain">${t.remain}</td><td>${t.g+t.remain}</td></tr>`
  }).join('');
}

document.querySelectorAll('.league-tab').forEach(button=>button.addEventListener('click',()=>render(button.dataset.league)));
$('#formulaButton').addEventListener('click',()=>{
  const panel=$('#formulaPanel'), open=panel.hidden;
  panel.hidden=!open; $('#formulaButton').setAttribute('aria-expanded',open); $('#formulaButton span').textContent=open?'−':'＋';
});
$('#matrixButton').addEventListener('click',()=>{
  const panel=$('#matrixPanel'), open=panel.hidden;
  panel.hidden=!open; $('#matrixButton').setAttribute('aria-expanded',open); $('#matrixButton span').textContent=open?'−':'＋';
});
$('#northLeader').textContent=`1위 ${leagues.north.teams[0].name}`;
$('#southLeader').textContent=`1위 ${leagues.south.teams[0].name}`;
if(window.KBO_DATA?.sourceDate){
  const [year,month,day]=window.KBO_DATA.sourceDate.split('-');
  $('#headerDate').textContent=`${month}.${day} 기준`;
  document.querySelector('.updated b').textContent=`${year}. ${month}. ${day}`;
}
render(current);
