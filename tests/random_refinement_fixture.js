'use strict';
const assert=require('node:assert/strict'), vm=require('node:vm');
class Node {
  constructor(name='div'){
    this.name=name;this.tagName=name.toUpperCase();this.attributes={};this.parts={};this.dataset={};this.style={};this.events={};this.children=[];this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.textContent='';
    const classes=new Set();this.classList={add:x=>classes.add(x),remove:x=>classes.delete(x),contains:x=>classes.has(x),toggle:(x,on)=>{if(on===undefined)on=!classes.has(x);on?classes.add(x):classes.delete(x);return on;}};
  }
  addEventListener(type,fn){(this.events[type]??=[]).push(fn);}
  emit(type,data={}){return Promise.all((this.events[type]||[]).map(fn=>fn({type,target:this,...data})));}
  dispatchEvent(event){return this.emit(event.type,event);}
  setAttribute(key,value){this.attributes[key]=String(value);}
  getAttribute(key){return this.attributes[key];}
  removeAttribute(key){delete this.attributes[key];}
  querySelector(selector){return this.parts[selector]??=new Node(selector);}
  append(...nodes){this.children.push(...nodes);}
  appendChild(node){this.append(node);}
  replaceChildren(...nodes){this.children=[...nodes];}
  replaceWith(node){this.replacement=node;}
  add(node){this.children.push(node);}
  get options(){return this.children;}
  focus(){this.focused=true;}
  scrollIntoView(){}
  remove(){this.removed=true;}
  closest(){return null;}
  getBoundingClientRect(){return {left:0,width:100};}
}
class Media extends Node {
  constructor(src=''){super('audio');this.src=src;this.paused=true;this.duration=90;this.currentTime=0;this.pauseCalls=0;this.loadCalls=0;Media.created.push(this);}
  play(){this.paused=false;this.emit('playing');return this.nextPlay||Promise.resolve();}
  pause(){this.paused=true;this.pauseCalls++;this.emit('pause');}
  load(){this.loadCalls++;this.error=null;}
  removeAttribute(name){super.removeAttribute(name);if(name==='src')this.src='';}
}
Media.created=[];
function setup(){
  const nodes=new Map(),timers=new Map();let timerId=0;
  const get=selector=>{if(!nodes.has(selector))nodes.set(selector,new Node(selector));return nodes.get(selector);};
  const document=new Node('document');document.body=new Node('body');document.querySelector=get;document.getElementById=id=>get('#'+id);document.createElement=name=>new Node(name);
  document.querySelectorAll=selector=>selector==='.filter-control'?['#f-search','#f-mood','#f-genre','#f-decade','#f-preview'].map(get):[];
  const selectedRange={removeAllRanges(){},addRange(value){this.value=value;}};
  document.createRange=()=>({selectNodeContents(node){this.node=node;}});
  const storage={value:'[]',getItem(){return this.value;},setItem(_key,value){this.value=value;}};
  const context=vm.createContext({console,document,URL,URLSearchParams,AbortController,Audio:Media,sessionStorage:storage,navigator:{},location:{search:''},history:{replaceState(){}},
    Option:class extends Node{constructor(text,value){super('option');this.textContent=text;this.value=value;}},
    CustomEvent:class{constructor(type,options){this.type=type;Object.assign(this,options);}},
    requestAnimationFrame:fn=>fn(),setTimeout:(fn,delay)=>{const id=++timerId;timers.set(id,{fn,delay});return id;},clearTimeout:id=>timers.delete(id),fetch:async()=>{throw new Error('offline');},matchMedia:()=>({matches:false}),getSelection:()=>selectedRange});
  context.window=context;context.addEventListener=()=>{};
  vm.runInContext('const TAGMAP={warm:"温暖"};const tgm=x=>TAGMAP[x]||x;const KNOB=["#888"];const PLAY="play",PAUSE="pause",HEART="heart";',context);
  vm.runInContext(__SOURCE__.replace('bkRender();loadPool();loadArtists();',''),context);
  return {run:source=>vm.runInContext(source,context),get,timers,context,storage,document,selectedRange};
}
async function main(){
  const f=setup(),{run,get}=f;
  run(`POOL=normalizePool([{id:'a',title:'Café <safe>',artist:'Artist A',album:'First Album',year:'1998',genres:['Dream Pop'],mood_tags:['warm'],p:'https://audio.example/a.m4a',c:'javascript:alert(1)'},{id:'b',title:'Quiet',artist:'Artist B',album:'Second',year:'2005',genres:['Ambient'],mood_tags:['calm'],p:''},{id:'c',title:'Quiet',artist:'Artist C',year:'2000',genres:['Ambient'],p:'https://audio.example/c.m4a'},null,{id:'a',title:'Duplicate',artist:'A'}]);loaded=true;`);
  assert.equal(run('POOL.length'),3);assert.equal(run('POOL[0].c'),'');
  get('#f-search').value='cafe album';assert.equal(run('pool()[0].id'),'a','accent-insensitive terms cross title/album');
  get('#f-genre').value='ambient';assert.equal(run('pool().length'),0,'search and genre intersect');get('#f-search').value='';
  get('#f-preview').checked=true;assert.equal(run('pool()[0].id'),'c');get('#f-preview').checked=false;
  get('#f-genre').value='';get('#f-decade').value='1990';get('#f-mood').value='温暖';assert.equal(run('pool()[0].id'),'a');
  get('#f-decade').value='';get('#f-mood').value='';
  assert.equal(run("findSeed(new URLSearchParams('t=Quiet&artist=Artist+C')).id"),'c','legacy title link is scoped by artist');
  assert.equal(run("findSeed(new URLSearchParams('t=Quiet')).id"),'b');assert.equal(run("findSeed(new URLSearchParams('t=a&artist=other')).id"),'a','canonical ID wins');
  f.storage.value='{"bad":true}';assert.equal(run('ld().length'),0);f.storage.value='[null,17,""," ","A - B","A - B"]';assert.equal(run('ld().length'),1);
  run('roll();roll();roll();');const picks=[...f.timers.values()].filter(t=>t.delay===240);assert.equal(picks.length,1,'rapid rolls never queue multiple selections');
  get('#f-search').value='no results';run('filtersChanged()');picks[0].fn();assert.equal(run('selected'),null,'cancelled old roll cannot replace empty result');assert.equal(get('#roll').disabled,true);
  get('#f-search').value='';run('selectTrack(POOL[0],false,false)');const first=Media.created.at(-1);assert.ok(get('#card').innerHTML.includes('Café &lt;safe&gt;'));assert.equal(get('#card').getAttribute('aria-busy'),undefined);
  assert.ok(!get('#card').innerHTML.includes('class="c-scene"'),'missing scene must not render an empty use label');
  assert.ok(get('#card').innerHTML.includes('<div class="big-art"><button class="cover-open cover-zoom" type="button"'));
  assert.ok(get('#card').innerHTML.includes('</button><button class="pbtn"'),'cover and play must be sibling native controls');
  run("POOL[0].scene='A <quiet> room';render(POOL[0],false)");assert.ok(get('#card').innerHTML.includes('A &lt;quiet&gt; room'));run('delete POOL[0].scene');
  let reject;first.nextPlay=new Promise((_resolve,no)=>{reject=no;});const old=run('resume()');run('selectTrack(POOL[1],false,false)');
  assert.equal(first.src,'');assert.equal(first.pauseCalls,1);assert.equal(run('au'),null,'no-preview has no old media');const status=get('#play-status').textContent;
  reject(new Error('old rejected'));await old;first.error={code:2};await first.emit('error');assert.equal(get('#play-status').textContent,status,'old promises and media events do not overwrite new status');
  first.paused=false;await first.emit('playing');assert.equal(first.paused,true,'stale source cannot restart after another song was selected');
  run('selectTrack(POOL[0],false,false)');const current=Media.created.at(-1);current.error={code:2};await current.emit('error');await run('resume()');assert.equal(current.loadCalls,1);assert.ok(get('#play-status').textContent.includes('正在试听'));
  current.currentTime=31;await current.emit('timeupdate');assert.equal(current.paused,true);assert.equal(get('#np-time').textContent,'0:30 / 0:30');await run('resume()');assert.equal(current.currentTime,0);
  await current.pause();assert.ok(get('#play-status').textContent.includes('已暂停'));
  await get('#np-bar').emit('keydown',{key:'End',preventDefault(){},stopPropagation(){}});assert.equal(current.currentTime,30);
  let resolveCancelled;current.nextPlay=new Promise(resolve=>{resolveCancelled=resolve;});const cancelled=run('resume()');
  assert.equal(get('#cpb').disabled,false,'card button stays usable while loading');assert.equal(get('#np-toggle').disabled,false,'player button stays usable while loading');
  await get('#np-toggle').emit('click');assert.equal(run('playPending'),false);assert.equal(current.playRequested,false);assert.equal(current.paused,true);
  resolveCancelled();await cancelled;current.paused=false;await current.emit('playing');assert.equal(current.paused,true,'late playing event cannot undo cancel');assert.ok(get('#play-status').textContent.includes('已暂停'));
  let rejectCancelled;current.nextPlay=new Promise((_resolve,no)=>{rejectCancelled=no;});const superseded=run('resume()');await get('#cpb').emit('click');
  current.nextPlay=Promise.resolve();await run('resume()');rejectCancelled(new Error('previous cancelled attempt'));await superseded;
  assert.equal(current.playRequested,true);assert.equal(current.paused,false);assert.ok(get('#play-status').textContent.includes('正在试听'),'old rejection cannot fail the new play attempt');
  const version=run('rollVersion');await f.document.emit('keydown',{key:' ',code:'Space',target:{closest:()=>true},preventDefault(){throw new Error('native control intercepted');}});assert.equal(run('rollVersion'),version);
  await run('loadPool()');assert.ok(get('#card').innerHTML.includes('重新加载'));assert.equal(get('#card').getAttribute('aria-busy'),undefined);
  f.context.location.search='?t=a';f.context.fetch=async()=>({ok:true,json:async()=>[{id:'a',title:'Recovered',artist:'A',genres:[],mood_tags:[]}]});await run('loadPool()');assert.equal(run('selected.title'),'Recovered');assert.equal(get('#f-search').disabled,false);
  run("hearts=['Saved - Artist'];bkRender();");await get('#bk-copy').emit('click');assert.equal(f.selectedRange.value.node,get('#bk-text'));assert.ok(get('#copy-status').textContent.includes('清单已选中'));assert.equal(get('#bk-copy').disabled,false);
  f.context.navigator.clipboard={writeText:async text=>{f.copied=text;}};await get('#bk-copy').emit('click');assert.ok(f.copied.includes('Saved - Artist'));
  console.log('PASS: random refinement regressions');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
