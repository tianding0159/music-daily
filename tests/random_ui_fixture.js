'use strict';
const assert=require('node:assert/strict'), vm=require('node:vm');
class Element {
  constructor(name='div'){
    this.name=name;this.tagName=name.toUpperCase();this.value='';this.checked=false;this.disabled=false;this.hidden=false;
    this.dataset={};this.style={};this.attributes={};this.children=[];this.handlers={};this.textContent='';this.isConnected=true;
    const classes=new Set();this.classList={add:x=>classes.add(x),remove:x=>classes.delete(x),contains:x=>classes.has(x),toggle:(x,on)=>{if(on===undefined)on=!classes.has(x);on?classes.add(x):classes.delete(x);return on;}};
  }
  set innerHTML(value){this.html=value;}
  get innerHTML(){return this.html||'';}
  setAttribute(key,value){this.attributes[key]=String(value);}
  getAttribute(key){return this.attributes[key];}
  removeAttribute(key){delete this.attributes[key];}
  hasAttribute(key){return key in this.attributes;}
  addEventListener(type,handler){(this.handlers[type]??=[]).push(handler);}
  dispatchEvent(event){for(const handler of this.handlers[event.type]||[])handler(event);}
  emit(type,event={}){this.dispatchEvent({type,target:this,...event});}
  append(...elements){this.children.push(...elements);}
  appendChild(element){this.append(element);return element;}
  replaceChildren(...elements){this.children=[...elements];}
  replaceWith(element){this.replacement=element;}
  querySelector(selector){this.parts??={};return this.parts[selector]??=new Element(selector);}
  querySelectorAll(){return this.children;}
  get options(){return this.children;}
  add(option){this.children.push(option);}
  focus(){this.focused=true;}
  scrollIntoView(){}
  remove(){this.isConnected=false;}
  closest(){return null;}
  getBoundingClientRect(){return {left:0,width:100};}
  getClientRects(){return [1];}
}
class AudioMock extends Element {
  constructor(src=''){super('audio');this.src=src;this.paused=true;this.currentTime=0;this.duration=30;this.pauseCount=0;this.loadCount=0;AudioMock.created.push(this);}
  play(){this.paused=false;this.emit('play');return this.nextPlay||Promise.resolve();}
  pause(){this.pauseCount++;this.paused=true;this.emit('pause');}
  load(){this.loadCount++;}
  removeAttribute(name){super.removeAttribute(name);if(name==='src')this.src='';}
}
AudioMock.created=[];
function fixture(){
  const elements=new Map(), timers=new Map();let timerNumber=0;
  const get=s=>{if(!elements.has(s))elements.set(s,new Element(s));return elements.get(s);};
  const document=new Element('document');document.body=new Element('body');document.activeElement=document.body;
  document.createElement=tag=>new Element(tag);document.querySelector=get;document.getElementById=id=>get('#'+id);
  document.querySelectorAll=selector=>selector==='.filter-control'?['#f-mood','#f-genre','#f-decade','#f-search','#f-preview'].map(get):[];
  const storage={value:'[]',getItem(){return this.value},setItem(key,value){this.value=value}};
  const context=vm.createContext({console,URL,URLSearchParams,AbortController,Set,Map,Audio:AudioMock,document,sessionStorage:storage,
    location:{href:'https://example.org/music-daily/random.html',search:''},history:{replaceState(_a,_b,url){context.location.href=String(url)}},navigator:{},
    Option:class extends Element{constructor(text,value){super('option');this.textContent=text;this.value=value;}},
    CustomEvent:class{constructor(type,opts){this.type=type;Object.assign(this,opts)}},HTMLImageElement:class{},
    setTimeout:(callback,delay)=>{const id=++timerNumber;timers.set(id,{callback,delay});return id;},clearTimeout:id=>timers.delete(id),requestAnimationFrame:fn=>fn(),
    fetch:async()=>{throw new Error('fixture offline')}});
  context.window=context;context.matchMedia=()=>({matches:false});context.addEventListener=()=>{};
  vm.runInContext(__UI_JS__,context);
  vm.runInContext('const TAGMAP={warm:"温暖"};const tgm=x=>TAGMAP[x]||x;const KNOB=["#d5aa88"];const PLAY="play",PAUSE="pause",HEART="heart";',context);
  vm.runInContext(__RANDOM_JS__.replace('bkRender();loadPool();loadArtists();',''),context);
  return {context,get,timers,storage,run:code=>vm.runInContext(code,context),document};
}
async function tests(){
  const f=fixture();const {run,get,timers}=f;
  run(`POOL=normalizePool([
    {id:'a',title:'A <script> & "quote"',artist:'Artist A',album:'The First Record',genres:['Dream Pop'],mood_tags:['warm'],year:1998,p:'https://example.org/a.m4a',c:'javascript:alert(1)'},
    {id:'b',title:'Quiet',artist:'Artist B',album:'Second',genres:['Ambient'],mood_tags:['calm'],year:2005,p:''},
    {id:'a',title:'duplicate',artist:'Artist A'},null,{id:'broken'}]);loaded=true;`);
  assert.equal(run('POOL.length'),2,'catalog schema and duplicate IDs must be validated');
  assert.equal(run('POOL[0].c'),'','unsafe cover URLs are rejected');
  assert.equal(run('esc(POOL[0].title)'),'A &lt;script&gt; &amp; &quot;quote&quot;');
  get('#f-search').value='first record';assert.equal(run('pool().length'),1,'search includes album');
  get('#f-search').value='artist record';assert.equal(run('pool()[0].id'),'a','separate terms can match across artist and album');
  assert.equal(run('searchText("Café")'),'cafe','search folds diacritics');
  get('#f-search').value='artist b';assert.equal(run('pool()[0].id'),'b','search includes artist');
  get('#f-search').value='';get('#f-mood').value='温暖';assert.equal(run('pool()[0].id'),'a','normalized mood filters match');
  get('#f-mood').value='';get('#f-decade').value='2000';assert.equal(run('pool()[0].id'),'b');
  get('#f-decade').value='';get('#f-preview').checked=true;assert.equal(run('pool().length'),1);
  get('#f-preview').checked=false;
  f.storage.value='{"unexpected":"shape"}';assert.equal(run('loadBasket().length'),0,'object storage payload cannot crash basket');
  f.storage.value='[null,42,"Valid - Artist","Valid - Artist","", "  "]';assert.equal(run('loadBasket().length'),1,'invalid and duplicate basket entries are discarded');
  run('roll();roll();roll();');assert.equal([...timers.values()].filter(t=>t.delay===220).length,1,'rapid roll clicks schedule only one pick');
  const previousRoll=[...timers.values()].find(t=>t.delay===220).callback;
  get('#f-search').value='no matches';run('filtersChanged()');previousRoll();
  assert.equal(run('current'),null,'filter change invalidates an already queued pick');
  assert.ok(get('#card').innerHTML.includes('还没有匹配的歌'));assert.equal(get('#roll').disabled,true);
  get('#f-search').value='';run('choose(POOL[0],false,false)');const first=AudioMock.created.at(-1);
  assert.equal(run('current.id'),'a');assert.ok(get('#card').innerHTML.includes('&lt;script&gt;'),'rendered text must be escaped');
  assert.ok(!get('#card').innerHTML.includes('<script>'));
  let rejectOld;first.nextPlay=new Promise((_resolve,reject)=>{rejectOld=reject});
  const pending=run('requestPlay()');
  run('choose(POOL[1],false,false)');assert.equal(first.pauseCount,1,'new song pauses previous media');assert.equal(first.src,'','old media source is unloaded');assert.equal(run('au'),null,'no-preview selection has no old media');
  const message=get('#play-status').textContent;rejectOld(Object.assign(new Error('blocked'),{name:'NotAllowedError'}));await pending;
  assert.equal(get('#play-status').textContent,message,'stale play rejection cannot overwrite current track status');
  run('choose(POOL[0],false,false)');const third=AudioMock.created.at(-1);third.nextPlay=Promise.reject(Object.assign(new Error('blocked'),{name:'NotAllowedError'}));
  await run('requestPlay()');assert.ok(get('#play-status').textContent.includes('点击播放按钮'));
  assert.equal(run('pendingPlay'),false,'failed play leaves controls retryable');
  third.paused=false;third.currentTime=30;third.emit('timeupdate');assert.equal(third.paused,true,'preview stops at 30 seconds');
  const oldGeneration=run('rollGeneration');
  f.document.emit('keydown',{key:' ',code:'Space',target:{closest:()=>true},preventDefault(){throw new Error('native button swallowed')}});
  assert.equal(run('rollGeneration'),oldGeneration,'native controls retain their keyboard behavior');
  await run('loadPool()');assert.ok(get('#card').innerHTML.includes('重新加载'),'network failure offers retry');
  assert.equal(get('#card').getAttribute('aria-busy'),undefined,'failed load exits busy state');
  // Lightbox uses canonical IDs across archive/daily/random contexts, even if titles collide.
  const lbCode=__LIGHTBOX_JS__;vm.runInContext(lbCode,f.context);
  const trigger=new Element('div');trigger.dataset={id:'a-id',title:'Same name',artist:'A',inpool:JSON.stringify([{id:'a-id',title:'Same name'},{id:'b-id',title:'Same name'}])};
  f.document.emit('click',{target:{closest:selector=>selector==='.art'?trigger:null},preventDefault(){}});
  const links=get('#lb-inpool').children;assert.equal(links.length,2);
  assert.equal(links[0].href,'../random.html?t=a-id');assert.equal(links[1].href,'../random.html?t=b-id');
  assert.equal(links[0].getAttribute('aria-current'),'true');assert.equal(links[1].getAttribute('aria-current'),undefined);
  get('#lb').dispatchEvent({type:'refresh',detail:{id:'a-id',artist:'A',bio:'Artist context arrived late',inpool:trigger.dataset.inpool}});
  assert.equal(get('#lb-bio').textContent,'Artist context arrived late','late artist context updates an open dialog');
  console.log('random UI state regressions: PASS');
}
tests().catch(error=>{console.error(error);process.exitCode=1;});
