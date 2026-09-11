// Execute the production JS in a deterministic DOM/Audio boundary, without a browser.
'use strict';
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const unhandled = [];
process.on('unhandledRejection', error => unhandled.push(error));

class Events {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, fn) { const listeners = this.listeners.get(type) || []; listeners.push(fn); this.listeners.set(type, listeners); }
  emit(type, properties = {}) {
    const event = {type, target:this, defaultPrevented:false, preventDefault(){this.defaultPrevented=true;}, stopPropagation(){}, ...properties};
    for (const handler of this.listeners.get(type) || []) handler(event);
    return event;
  }
}

function environment({count=3, storage='[]', getFails=false, setFails=false, clipboardRejects=false} = {}) {
  let document;
  class Element extends Events {
    constructor(tag='div', classes='', parent=null) {
      super(); this.tagName=tag.toUpperCase(); this.parentElement=parent; this.children=[];
      this.dataset={}; this.attributes={}; this.style={}; this.hidden=false; this.disabled=false; this.value=''; this._text='';
      this.classes=new Set(classes.split(/\s+/).filter(Boolean));
      this.classList={contains:c=>this.classes.has(c),add:(...cs)=>cs.forEach(c=>this.classes.add(c)),remove:(...cs)=>cs.forEach(c=>this.classes.delete(c)),toggle:(c,force)=>{const on=force===undefined?!this.classes.has(c):Boolean(force);on?this.classes.add(c):this.classes.delete(c);return on;}};
      if(parent)parent.children.push(this);
    }
    set textContent(value) {this._text=String(value);this.children=[];}
    get textContent() {return this._text+this.children.map(c=>c.textContent).join(' ');}
    setAttribute(key,value) {this.attributes[key]=String(value);if(key.startsWith('data-'))this.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(value);}
    getAttribute(key) {if(key.startsWith('data-'))return this.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]??null;return this.attributes[key]??null;}
    removeAttribute(key) {delete this.attributes[key];if(key==='title')delete this.title;}
    hasAttribute(key) {return this.getAttribute(key)!==null;}
    matches(selector) {
      const attrs=[...selector.matchAll(/\[([^=\]]+)(?:=["']?([^\]"']+)["']?)?\]/g)];
      if(attrs.some(m=>!this.hasAttribute(m[1])||(m[2]!==undefined&&this.getAttribute(m[1])!==m[2])))return false;
      const plain=selector.replace(/\[[^\]]+\]/g,'');
      const tag=plain.match(/^[a-z]+/i)?.[0];if(tag&&this.tagName!==tag.toUpperCase())return false;
      return [...plain.matchAll(/\.([\w-]+)/g)].every(m=>this.classes.has(m[1]));
    }
    closest(selector) {for(let node=this;node;node=node.parentElement)if(selector.split(',').some(s=>node.matches(s.trim())))return node;return null;}
    querySelectorAll(selector) {const found=[];const visit=node=>{for(const child of node.children){if(selector.split(',').some(s=>child.matches(s.trim())))found.push(child);visit(child);}};visit(this);return found;}
    querySelector(selector) {return this.querySelectorAll(selector)[0]||null;}
    click() {if(!this.disabled)this.emit('click');}
    focus() {document.activeElement=this;}
    scrollIntoView(options) {this.lastScroll=options;}
  }
  const body=new Element('body'), ids={};
  const element=(id,tag='div',classes='',parent=body)=>{const node=new Element(tag,classes,parent);ids[id]=node;node.id=id;return node;};
  document=new Events();Object.assign(document,{body,activeElement:body,title:'Test issue',getElementById:id=>ids[id]||null,querySelectorAll:selector=>body.querySelectorAll(selector),createRange:()=>({node:null,selectNodeContents(node){this.node=node;}})});
  const selected={node:null}, window=new Events();
  window.getSelection=()=>({removeAllRanges(){selected.node=null;},addRange(range){selected.node=range.node;}});
  const np=element('np');
  for(const id of ['np-cover','np-title','np-artist','np-time'])element(id,id==='np-cover'?'img':'div','',np);
  for(const id of ['np-toggle','np-prev','np-next'])element(id,'button','',np);
  element('np-seek','input','',np).value='0';
  element('boot').dataset.text='Existing issue';
  for(const id of ['fav-n','filter-note','empty-message','fav-text','nc-text'])element(id);
  for(const id of ['fav-only','filter-reset','fav-export','fav-copy','nc-btn','share-btn'])element(id,'button').textContent=id;
  element('track-search','input');element('empty-list');element('fav-box');element('lb');
  const names=['Alpha','Beta','Gamma','Delta','Epsilon','Zeta','Eta','Theta'];
  const cards=[], buttons=[], hearts=[];
  for(let i=0;i<count;i++) {
    const card=new Element('article','mod',body);card.dataset.k=`${names[i]} - Artist ${i+1}`;
    const hd=new Element('div','hd',card);new Element('h2','title',hd).textContent=names[i];
    new Element('span','artist',hd).textContent=`Artist ${i+1}`;new Element('span','genre',hd).textContent=i%2?'folk':'electronic';
    const heart=new Element('button','heart',hd);heart.dataset.k=card.dataset.k;new Element('svg','',heart);
    const button=new Element('button','pbtn',card);Object.assign(button.dataset,{title:names[i],artist:`Artist ${i+1}`,src:`https://audio.example/${i}.m4a`,cover:`https://image.example/${i}.jpg`});
    cards.push(card);buttons.push(button);hearts.push(heart);
  }
  const fill=new Element('article','mod fill',body);
  let raw=storage;const writes=[];
  const localStorage={getItem(){if(getFails)throw new Error('storage denied');return raw;},setItem(key,value){if(setFails)throw new Error('storage quota');raw=value;writes.push({key,value});}};
  const copies=[],timers=new Map();let timerId=0;
  const audios=[];
  class Audio extends Events {
    constructor(){super();this.paused=true;this.ended=false;this.currentTime=0;this.duration=NaN;this.error=null;this.src='';this.requests=[];this.pauseCalls=0;this.loadCalls=0;audios.push(this);}
    play(){this.paused=false;this.ended=false;let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});this.requests.push({resolve,reject,promise});return promise;}
    pause(){this.paused=true;this.pauseCalls++;this.emit('pause');}
    load(){this.loadCalls++;this.error=null;this.currentTime=0;this.duration=NaN;}
    removeAttribute(name){if(name==='src')this.src='';}
    succeed(index=this.requests.length-1,{event=true,resume=true}={}){if(resume)this.paused=false;if(event)this.emit('playing');this.requests[index].resolve();}
    reject(index=this.requests.length-1,name='NotSupportedError'){this.paused=true;this.requests[index].reject(Object.assign(new Error(name),{name}));}
    mediaError(){this.error={code:4};this.paused=true;this.emit('error');}
  }
  const context=vm.createContext({document,window,localStorage,Audio,console,URL,location:{href:'https://example.test/daily.html#detail'},navigator:{clipboard:{async writeText(text){if(clipboardRejects)throw new Error('clipboard denied');copies.push(text);}}},matchMedia:()=>({matches:true}),setTimeout:(fn)=>{const id=++timerId;timers.set(id,fn);return id;},clearTimeout:id=>timers.delete(id)});
  vm.runInContext(input.script,context,{filename:'render_grid.JS',timeout:3000});
  return {ids,cards,buttons,hearts,fill,audios,document,window,body,context,copies,selected,writes,
    store(value){raw=value;},get stored(){return raw;},setStorageFailure(on){setFails=on;},
    key(target,key=' ',code='Space'){return document.emit('keydown',{target,key,code});},
    search(value){ids['track-search'].value=value;ids['track-search'].emit('input');},
    visible(){return cards.filter(c=>!c.classList.contains('hidden'));},
    runTimers(){for(const fn of timers.values())fn();timers.clear();},
  };
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));

const scenarios={
  async old_source_failure_and_events_cannot_touch_b(){
    const e=environment();e.buttons[0].click();const a=e.audios[0];e.buttons[1].click();const b=e.audios[1];
    b.succeed();await flush();a.reject();await flush();a.mediaError();a.paused=false;a.emit('playing');a.emit('waiting');a.emit('ended');await flush();
    assert.equal(e.audios.length,2);assert.equal(e.ids['np-title'].textContent,'Beta');assert.equal(e.ids.np.getAttribute('aria-busy'),'false');
    assert(e.buttons[1].classList.contains('playing'));assert(!e.buttons[1].classList.contains('dead'));assert(!e.buttons[0].classList.contains('playing'));
  },
  async old_source_success_cannot_clear_b_pending_state(){
    const e=environment();e.buttons[0].click();const a=e.audios[0];e.buttons[1].click();a.succeed();await flush();
    assert.equal(e.ids['np-title'].textContent,'Beta');assert.equal(e.ids.np.getAttribute('aria-busy'),'true');assert(!e.buttons[1].classList.contains('playing'));
    e.audios[1].succeed();await flush();assert(e.buttons[1].classList.contains('playing'));
  },
  async an_old_attempt_on_the_same_source_cannot_settle_a_new_attempt(){
    for(const rejected of [false,true]){
      const e=environment();e.buttons[0].click();const a=e.audios[0];e.ids['np-toggle'].click();e.ids['np-toggle'].click();
      assert.equal(a.requests.length,2);assert.equal(e.ids.np.getAttribute('aria-busy'),'true');
      if(rejected)a.requests[0].reject(Object.assign(new Error('old attempt'),{name:'NotSupportedError'}));
      else a.requests[0].resolve();
      await flush();assert.equal(e.audios.length,1);assert.equal(e.ids.np.getAttribute('aria-busy'),'true');assert(!e.buttons[0].classList.contains('dead'));
      a.succeed(1);await flush();assert.equal(e.ids.np.getAttribute('aria-busy'),'false');assert(e.buttons[0].classList.contains('playing'));
    }
  },
  async pause_pending_ignores_late_success_playing_waiting_and_error(){
    const e=environment();e.buttons[0].click();const a=e.audios[0];e.buttons[0].click();
    assert(a.paused);assert.equal(e.ids.np.getAttribute('aria-busy'),'false');a.emit('waiting');
    a.succeed(0,{event:false,resume:false});await flush();assert(!e.ids.np.classList.contains('playing'));
    a.paused=false;a.emit('playing');assert(a.paused);a.emit('waiting');a.mediaError();await flush();
    assert.equal(e.audios.length,1);assert.equal(e.ids.np.getAttribute('aria-busy'),'false');assert(!e.ids.np.classList.contains('playing'));
  },
  async pause_also_cancels_a_queued_ended_event(){
    const e=environment();e.buttons[0].click();const a=e.audios[0];a.succeed();await flush();e.ids['np-toggle'].click();
    assert(a.paused);a.ended=true;a.emit('ended');await flush();assert.equal(e.audios.length,1,'late ended must not restart another track after explicit pause');
  },
  async a_natural_end_still_advances_to_the_next_visible_track(){
    const e=environment();e.buttons[0].click();const a=e.audios[0];a.succeed();await flush();
    a.paused=true;a.ended=true;a.emit('ended');assert.equal(e.audios.length,2);assert.equal(e.ids['np-title'].textContent,'Beta');
    e.audios[1].succeed();await flush();assert(e.buttons[1].classList.contains('playing'));
  },
  async resume_policy_rejection_is_handled_and_retry_works(){
    const e=environment();e.buttons[0].click();const a=e.audios[0];a.succeed();await flush();e.ids['np-toggle'].click();e.ids['np-toggle'].click();
    a.reject(1,'NotAllowedError');await flush();assert.equal(e.audios.length,1);assert(!e.ids.np.classList.contains('playing'));assert.equal(e.ids.np.getAttribute('aria-busy'),'false');
    assert.match(e.ids['np-artist'].textContent,/播放/);e.ids['np-toggle'].click();a.succeed(2);await flush();assert(e.ids.np.classList.contains('playing'));assert(!e.buttons[0].classList.contains('dead'));
  },
  async resume_network_rejection_automatically_moves_to_b(){
    const e=environment();e.buttons[0].click();const a=e.audios[0];a.succeed();await flush();e.ids['np-toggle'].click();e.ids['np-toggle'].click();a.reject(1);await flush();
    assert.equal(e.audios.length,2);assert.equal(e.ids['np-title'].textContent,'Beta');assert(e.buttons[0].classList.contains('dead'));
    e.audios[1].succeed();await flush();assert(e.buttons[1].classList.contains('playing'));
  },
  async broken_sources_have_a_six_attempt_cap_and_manual_retry(){
    const e=environment({count:8});e.buttons[0].click();
    for(let i=0;i<6;i++){assert.equal(e.audios.length,i+1);e.audios[i].reject();await flush();}
    assert.equal(e.audios.length,6);assert.equal(e.ids.np.getAttribute('aria-busy'),'false');assert(!e.ids.np.classList.contains('playing'));assert.match(e.ids['np-artist'].textContent,/重试/);
    e.buttons[5].click();assert.equal(e.audios.length,7);assert.equal(e.audios[6].src,e.buttons[5].dataset.src);e.audios[6].succeed();await flush();
    assert(!e.buttons[5].classList.contains('dead'));assert(e.buttons[5].classList.contains('playing'));
  },
  async duplicate_media_error_and_rejection_only_skip_once(){
    const e=environment();e.buttons[0].click();const a=e.audios[0];a.mediaError();a.mediaError();a.reject();await flush();
    assert.equal(e.audios.length,2);assert.equal(e.ids['np-title'].textContent,'Beta');assert.equal(e.ids.np.getAttribute('aria-busy'),'true');
    e.audios[1].succeed();await flush();assert(e.buttons[1].classList.contains('playing'));
  },
  async automatic_skip_obeys_current_search_and_favorites(){
    const e=environment();e.hearts[2].click();e.buttons[0].click();e.ids['fav-only'].click();e.search('GAMMA');
    assert.equal(e.visible().length,1);e.audios[0].reject();await flush();assert.equal(e.ids['np-title'].textContent,'Gamma');assert.equal(e.audios.length,2);
  },
  async search_favorites_empty_state_and_exports_stay_in_sync(){
    const e=environment({storage:JSON.stringify(['From Past - Elsewhere'])});assert.equal(e.visible().length,3);assert.equal(e.fill.hidden,false);
    e.search('alpha ELECTRONIC');assert.deepEqual(e.visible(),[e.cards[0]]);e.ids['fav-only'].click();assert.equal(e.visible().length,0);assert.equal(e.ids['empty-list'].hidden,false);assert.equal(e.fill.hidden,true);
    e.ids['filter-reset'].click();assert.equal(e.document.activeElement,e.ids['track-search']);e.hearts[0].click();e.ids['fav-only'].click();assert.deepEqual(e.visible(),[e.cards[0]]);
    e.ids['fav-export'].click();assert.equal(e.ids['fav-box'].style.display,'block');assert.match(e.ids['fav-text'].textContent,/From Past/);assert.match(e.ids['fav-text'].textContent,/Alpha/);
    e.hearts[0].click();assert.equal(e.visible().length,0);assert(!e.ids['fav-text'].textContent.includes('Alpha'));assert.match(e.ids['fav-text'].textContent,/From Past/);
    e.store(JSON.stringify(['Beta - Artist 2']));e.window.emit('storage',{key:'md_hearts'});assert.deepEqual(e.visible(),[e.cards[1]]);assert.match(e.ids['fav-text'].textContent,/Beta/);assert(!e.ids['fav-text'].textContent.includes('From Past'));
  },
  async bad_storage_types_do_not_crash_or_pollute_export(){
    for(const raw of ['{}','null','7','"wrong"','[1,null,{},true,"", "   ", "Alpha - Artist 1"]','not JSON']){
      const e=environment({storage:raw});assert.equal(e.visible().length,3);e.ids['fav-export'].click();assert(!e.ids['fav-text'].textContent.includes('[object Object]'));e.hearts[1].click();
      const saved=JSON.parse(e.stored);assert(Array.isArray(saved));assert(saved.every(v=>typeof v==='string'&&v.trim()));assert(saved.includes('Beta - Artist 2'));
    }
  },
  async unavailable_storage_keeps_current_page_favorites_and_copy_fallback(){
    const e=environment({getFails:true,setFails:true,clipboardRejects:true});e.hearts[0].click();e.hearts[1].click();e.search('alpha');e.ids['fav-export'].click();
    assert.match(e.ids['fav-text'].textContent,/Alpha/);assert.match(e.ids['fav-text'].textContent,/Beta/);assert.match(e.ids['filter-note'].textContent,/未能保存/);
    await e.context.copyFav();assert(e.selected.node===e.ids['fav-text'],'copy fallback selects the current export text');assert.match(e.ids['fav-copy'].textContent,/已选中/);
  },
  async keyboard_on_native_controls_never_triggers_global_playback(){
    const e=environment();const nestedSvg=e.hearts[0].children[0];
    for(const target of [e.hearts[0],nestedSvg,e.ids['track-search'],e.ids['fav-export']]){const event=e.key(target);assert.equal(event.defaultPrevented,false);assert.equal(e.audios.length,0);}
    const event=e.key(e.body);assert.equal(event.defaultPrevented,true);assert.equal(e.audios.length,1);
    e.key(e.ids['np-next'],'ArrowRight','ArrowRight');assert.equal(e.audios.length,1);e.ids.lb.classList.add('on');e.key(e.body);assert.equal(e.audios.length,1);
  },
  async copy_exports_exact_current_text_and_restores_button_label(){
    const e=environment();e.hearts[1].click();const original=e.ids['fav-copy'].textContent;await e.context.copyFav();
    assert.equal(e.copies[0],e.ids['fav-text'].textContent);assert.equal(e.ids['fav-copy'].textContent,'已复制 ✓');e.runTimers();assert.equal(e.ids['fav-copy'].textContent,original);
  },
};

(async()=>{
  if(!Object.hasOwn(scenarios,input.scenario))throw new Error('unknown scenario '+input.scenario);
  await scenarios[input.scenario]();await flush();assert.equal(unhandled.length,0,'uncaught async event/play rejection');
  process.stdout.write(JSON.stringify({status:'PASS',scenario:input.scenario})+'\n');
})().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
