class DiscoveryElement extends Element {
  matches(selector){
    if(selector.startsWith('.'))return this.className?.split(/\s+/).includes(selector.slice(1))||this.classList.contains(selector.slice(1));
    if(selector==='[tabindex="-1"]')return this.getAttribute('tabindex')==='-1';
    return this.tagName===selector.toUpperCase();
  }
  closest(selector){if(this.matches(selector))return this;return this.parentNode?.closest(selector)||null;}
  append(...elements){
    for(const element of elements){
      if(element.name==='#fragment'){this.append(...element.children);continue;}
      element.parentNode=this;element.isConnected=true;this.children.push(element);
    }
  }
  replaceChildren(...elements){this.children.forEach(child=>{child.isConnected=false;});this.children=[];this.append(...elements);}
  querySelectorAll(selector){return this.children.flatMap(child=>[...(child.matches(selector)?[child]:[]),...child.querySelectorAll(selector)]);}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
}
function discoverFixture(saved='[]'){
  const nodes=new Map(), windowHandlers={}, notices=[];
  const get=id=>{if(!nodes.has(id))nodes.set(id,new DiscoveryElement('div'));return nodes.get(id);};
  const tracks=Array.from({length:73},(_x,index)=>({id:'d'+index,title:index===0?'Café':'Track '+index,artist:index===0?'Artist A':'Artist '+index,album:'Album '+index,year:index===0?'1998':'2005',genre:index%2===0?'Electronic':'Ambient',cover:'',preview:index===2?'':'https://audio-ssl.itunes.apple.com/'+index+'.m4a',apple:'https://music.apple.com/album/'+index,duration:180000}));
  get('discovery-data').textContent=JSON.stringify(tracks);
  const document=new DiscoveryElement('document');document.body=new DiscoveryElement('body');document.activeElement=document.body;
  document.createElement=tag=>new DiscoveryElement(tag);document.createDocumentFragment=()=>new DiscoveryElement('#fragment');
  document.getElementById=get;document.querySelector=selector=>selector==='.manual-copy'?null:get('discover-list').querySelector(selector);
  document.querySelectorAll=selector=>get('discover-list').querySelectorAll(selector);
  const storage={value:saved,getItem(){return this.value},setItem(_key,value){this.value=value}};
  const context=vm.createContext({console,URL,URLSearchParams,Audio:AudioMock,document,localStorage:storage,navigator:{},Blob,
    HTMLImageElement:class{},setTimeout:()=>1,clearTimeout:()=>{},DISCOVERY_ICONS:{play:'play',pause:'pause',heart:'heart'}});
  context.window=context;context.addEventListener=(type,handler)=>{(windowHandlers[type]??=[]).push(handler);};
  vm.runInContext(__UI_JS__,context);const notify=context.MD.notify;context.MD.notify=message=>{notices.push(message);notify(message);};
  vm.runInContext(__DISCOVER_JS__,context);
  return {context,get,tracks,storage,document,windowHandlers,notices,audio:AudioMock.created.at(-1),cards:()=>get('discover-list').children,play:card=>card.querySelector('.discover-play'),heart:card=>card.querySelector('.heart')};
}
async function discoveryTests(){
  let failures=0;
  async function check(name,fn){try{await fn();console.log('PASS '+name);}catch(error){failures++;console.error('FAIL '+name+'\n'+error.stack);}}
  await check('page boundaries and combined filters reset pagination',()=>{
    const f=discoverFixture();assert.equal(f.cards().length,36);assert.equal(f.get('discover-page').textContent,'1 / 3');
    f.get('discover-next-page').emit('click');assert.equal(f.cards()[0].dataset.id,'d36');assert.equal(f.cards().length,36);
    f.get('discover-next-page').emit('click');assert.equal(f.cards()[0].dataset.id,'d72');assert.equal(f.cards().length,1);assert.equal(f.get('discover-next-page').disabled,true);
    f.get('discover-search').value='cafe artist';f.get('discover-search').emit('input');assert.equal(f.cards().length,1);assert.equal(f.cards()[0].dataset.id,'d0');assert.equal(f.get('discover-page').textContent,'1 / 1');
    f.get('discover-genre').value='Ambient';f.get('discover-genre').emit('change');assert.equal(f.cards().length,0);assert.equal(f.get('discover-empty').hidden,false);
    f.get('discover-reset').emit('click');assert.equal(f.cards().length,36);assert.equal(f.get('discover-search').value,'');
    f.get('discover-genre').value='Electronic';f.get('discover-decade').value='1990';f.get('discover-decade').emit('change');assert.equal(f.cards().length,1);assert.equal(f.cards()[0].dataset.id,'d0');
  });
  await check('unknown favorite records survive across pages; malformed storage is harmless',()=>{
    const f=discoverFixture('[null,17,{},"","Daily favorite - Artist","Café - Artist A","Café - Artist A","Track 72 - Artist 72"]');
    assert.equal(f.heart(f.cards()[0]).getAttribute('aria-pressed'),'true');assert.ok(f.get('discover-export-text').textContent.includes('Daily favorite - Artist'));
    assert.equal(f.get('discover-export-text').textContent.split('\n').length,3);
    f.get('discover-favorites').emit('click');assert.deepEqual(f.cards().map(c=>c.dataset.id),['d0','d72']);
    f.heart(f.cards()[0]).emit('click');assert.deepEqual(f.cards().map(c=>c.dataset.id),['d72']);assert.ok(JSON.parse(f.storage.value).includes('Daily favorite - Artist'));
    f.storage.value='{"malformed":true}';for(const handler of f.windowHandlers.storage)handler({key:'md_hearts'});assert.equal(f.cards().length,0);assert.equal(f.get('discover-copy').disabled,true);
    f.storage.value='["Track 1 - Artist 1"]';for(const handler of f.windowHandlers.storage)handler({key:'md_hearts'});assert.deepEqual(f.cards().map(c=>c.dataset.id),['d1']);
  });
  await check('no-preview label stays accurate and no untrusted text enters innerHTML',()=>{
    const f=discoverFixture();const unavailable=f.play(f.cards()[2]);assert.equal(unavailable.disabled,true);assert.equal(unavailable.querySelector('span').textContent,'暂无试听');
    const title=f.cards()[0].querySelector('h2');assert.equal(title.textContent,'Café');
  });
  await check('late play rejection leaves the newly selected song intact',async()=>{
    const f=discoverFixture();let reject;
    f.audio.nextPlay=new Promise((_resolve,no)=>{reject=no});f.play(f.cards()[0]).emit('click');
    f.audio.nextPlay=Promise.resolve();f.play(f.cards()[1]).emit('click');reject(new Error('late failure'));await Promise.resolve();await Promise.resolve();
    assert.equal(f.get('np-title').textContent,'Track 1');assert.equal(f.get('np-artist').textContent,'Artist 1');
  });
  await check('media failure retry reloads and recovers displayed metadata',async()=>{
    const f=discoverFixture();f.play(f.cards()[0]).emit('click');f.audio.error={code:2};f.audio.paused=true;f.audio.emit('error');
    const before=f.audio.loadCount;f.get('np-toggle').emit('click');assert.ok(f.audio.loadCount>before,'failed media must reload before retry');
    f.audio.error=null;f.audio.emit('playing');assert.equal(f.get('np-artist').textContent,'Artist A','successful retry clears stale error text');
  });
  await check('native keyboard controls retain Space; closing player unloads media',()=>{
    const f=discoverFixture();f.play(f.cards()[0]).emit('click');const source=f.audio.src;
    f.document.emit('keydown',{code:'Space',target:{closest:()=>true},preventDefault(){throw new Error('native control swallowed')}});assert.equal(f.audio.src,source);
    f.get('np-close').emit('click');assert.equal(f.audio.src,'');assert.equal(f.get('np').classList.contains('on'),false);assert.equal(f.audio.paused,true);
  });
  await check('preview stops at 30 seconds and restarts from zero',()=>{
    const f=discoverFixture();f.play(f.cards()[0]).emit('click');f.audio.duration=90;f.audio.currentTime=31;f.audio.emit('timeupdate');
    assert.equal(f.audio.paused,true);assert.equal(f.get('np-time').textContent,'0:30 / 0:30');assert.equal(f.get('np-bar').getAttribute('aria-valuenow'),'100');
    f.get('np-toggle').emit('click');assert.equal(f.audio.currentTime,0,'restart must seek back before playing');
    f.get('np-bar').emit('click',{clientX:200});assert.equal(f.audio.currentTime,30,'click seek clamps to the 30-second preview');
    f.get('np-bar').emit('keydown',{key:'Home',preventDefault(){},stopPropagation(){}});assert.equal(f.audio.currentTime,0);
    f.get('np-bar').emit('keydown',{key:'End',preventDefault(){},stopPropagation(){}});assert.equal(f.audio.currentTime,30);
  });
  if(failures)throw new Error(failures+' discovery UI regressions failed');console.log('discovery UI regressions: PASS');
}
discoveryTests().catch(error=>{console.error(error);process.exitCode=1;});
