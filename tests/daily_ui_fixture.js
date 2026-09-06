function dailyFixture(saved='[]'){
  const elements=new Map(), windowHandlers={}, notices=[], selection={removeAllRanges(){},addRange(range){this.range=range;}};
  const get=id=>{if(!elements.has(id))elements.set(id,new Element(id));return elements.get(id);};
  const cards=[
    {id:'a',k:'Track A - Artist A',search:'Track A Artist A Café Dream Pop 1998',genre:'Dream Pop'},
    {id:'b',k:'Track B - Artist B',search:'Track B Artist B Ambient 2005',genre:'Ambient'},
    {id:'c',k:'Track C - Artist C',search:'Track C Artist C Ambient 2010',genre:'Ambient'}
  ].map(data=>{const card=new Element('article');card.dataset=data;return card;});
  const buttons=cards.map((card,index)=>{const button=card.querySelector('.pbtn');button.dataset={title:'Track '+index,artist:'Artist '+index,src:index<2?'https://example.org/'+index+'.m4a':'',cover:''};button.closest=()=>card;return button;});
  const document=new Element('document');document.body=new Element('body');document.activeElement=document.body;document.title='MUSIC DAILY';
  document.createElement=tag=>{const element=new Element(tag);element.select=()=>{element.selected=true;};return element;};
  document.getElementById=get;
  document.querySelectorAll=selector=>selector==='article.mod'?cards:selector==='.pbtn'?buttons:[];
  document.querySelector=selector=>selector==='.manual-copy'?document.body.children.find(x=>x.className==='manual-copy'&&x.isConnected)||null:null;
  document.createRange=()=>({selectNodeContents(element){this.element=element;}});
  const storage={value:saved,getItem(){return this.value},setItem(_key,value){this.value=value}};
  const context=vm.createContext({console,URLSearchParams,Audio:AudioMock,document,localStorage:storage,navigator:{},
    HTMLImageElement:class{},location:{href:'https://example.org/music-daily/daily.html',search:''},setTimeout:()=>1,clearTimeout:()=>{}});
  context.window=context;context.getSelection=()=>selection;context.addEventListener=(type,handler)=>{(windowHandlers[type]??=[]).push(handler);};
  vm.runInContext(__UI_JS__,context);const realNotify=context.MD.notify;context.MD.notify=message=>{notices.push(message);realNotify(message);};
  vm.runInContext(__DAILY_JS__,context);
  return {context,get,cards,buttons,document,storage,selection,notices,windowHandlers,audio:AudioMock.created.at(-1)};
}
async function dailyTests(){
  let failures=0;
  async function check(name,fn){try{await fn();console.log('PASS '+name);}catch(error){failures++;console.error('FAIL '+name+'\n'+error.stack);}}
  await check('malformed favorites are harmless and deduplicated',()=>{
    const f=dailyFixture('[null,{},17,false,"Track A - Artist A","Track A - Artist A",""]');
    assert.equal(f.get('fav-n').textContent,1);assert.ok(f.get('fav-text').textContent.includes('共 1 首'),'empty/corrupted values must not inflate export count');
    assert.equal(f.cards[0].querySelector('.heart').getAttribute('aria-pressed'),'true');
    f.storage.value='{"invalid":true}';for(const handler of f.windowHandlers.storage)handler({key:'md_hearts'});
    assert.equal(f.get('fav-n').textContent,0);assert.equal(f.get('fav-copy').disabled,true);
  });
  await check('combined search genre favorites and reset',()=>{
    const f=dailyFixture('["Track A - Artist A"]');
    f.get('track-search').value='cafe artist';f.get('track-search').emit('input');
    assert.deepEqual(f.cards.map(c=>c.hidden),[false,true,true],'search is accent insensitive and all terms match');
    f.get('track-genre').value='Ambient';f.get('track-genre').emit('change');assert.ok(f.cards.every(c=>c.hidden));assert.equal(f.get('no-tracks').hidden,false);
    f.get('filter-reset').emit('click');assert.ok(f.cards.every(c=>!c.hidden));assert.equal(f.get('track-search').value,'');assert.equal(f.get('track-genre').value,'');
    f.get('fav-only').emit('click');assert.deepEqual(f.cards.map(c=>c.hidden),[false,true,true]);
    f.cards[0].querySelector('.heart').emit('click');assert.ok(f.cards.every(c=>c.hidden));
  });
  await check('native controls keep Space and modal blocks playback shortcuts',()=>{
    const f=dailyFixture();const source=f.audio.src;
    f.document.emit('keydown',{code:'Space',target:{closest:()=>true},preventDefault(){throw new Error('native keyboard intercepted')}});
    assert.equal(f.audio.src,source);
    f.get('lb').classList.add('on');f.document.emit('keydown',{code:'Space',target:{closest:()=>false},preventDefault(){throw new Error('modal shortcut escaped')}});assert.equal(f.audio.src,source);
  });
  await check('missing preview clears old source and never replays it',async()=>{
    const f=dailyFixture();f.buttons[0].emit('click');await Promise.resolve();assert.ok(f.audio.src);
    f.buttons[2].emit('click');assert.equal(f.audio.src,'','switching to no-preview must clear previous src');
    assert.equal(f.audio.paused,true);assert.equal(f.get('np').classList.contains('on'),false,'no-preview hides stale player controls');
  });
  await check('stale play rejection does not fail the later track',async()=>{
    const f=dailyFixture();let reject;
    f.audio.nextPlay=new Promise((_resolve,no)=>reject=no);f.buttons[0].emit('click');
    f.audio.nextPlay=Promise.resolve();f.buttons[1].emit('click');reject(new Error('old source failed'));await Promise.resolve();await Promise.resolve();
    assert.equal(f.buttons[1].classList.contains('dead'),false);assert.equal(f.get('np-artist').textContent,'Artist 1');
  });
  await check('player retry reloads failed media',async()=>{
    const f=dailyFixture();f.buttons[0].emit('click');f.audio.paused=true;f.audio.error={code:2};f.audio.emit('error');
    const before=f.audio.loadCount;f.get('np-toggle').emit('click');assert.ok(f.audio.loadCount>before,'retry must reset a failed media resource');
    f.audio.error=null;f.audio.emit('playing');assert.equal(f.get('np-artist').textContent,'Artist 0','successful retry restores artist metadata');
  });
  await check('long API previews advance at the promised 30 seconds',()=>{
    const f=dailyFixture();f.buttons[0].emit('click');f.audio.duration=90;f.audio.currentTime=30;f.audio.emit('timeupdate');
    assert.equal(f.audio.src,'https://example.org/1.m4a');
  });
  await check('clipboard fallback selects available export and offers manual copy for links',async()=>{
    const f=dailyFixture();const exported=f.get('fav-text'), button=f.get('fav-copy');
    exported.textContent='Track A - Artist A';assert.equal(await f.context.MD.copyText(exported.textContent,button,exported),false);
    assert.equal(f.selection.range.element,exported);
    assert.equal(await f.context.MD.copyText('https://example.org/daily.html',button),false);
    const panel=f.document.querySelector('.manual-copy');assert.ok(panel);const area=panel.children.find(x=>x.tagName==='TEXTAREA');
    assert.equal(area.value,'https://example.org/daily.html');assert.equal(area.selected,true);
    panel.children.find(x=>x.tagName==='BUTTON').emit('click');assert.equal(panel.isConnected,false);assert.equal(button.focused,true);
    f.context.navigator.clipboard={writeText:async text=>{f.copied=text;}};
    assert.equal(await f.context.MD.copyText('Done',button),true);assert.equal(f.copied,'Done');
  });
  if(failures)throw new Error(failures+' daily UI regressions failed');
  console.log('daily UI state regressions: PASS');
}
dailyTests().catch(error=>{console.error(error);process.exitCode=1;});
