"""原版入口与共用浮层的交互回归；不读取或重写正式曲库。"""
from html.parser import HTMLParser
from pathlib import Path
import json
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import lightbox
import render_landing


class Markup(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class LandingMarkupTests(unittest.TestCase):
    def test_entry_and_browse_links_work_without_javascript(self):
        doc = Markup(render_landing.build_html(42, 2169, "2026-09-07"))
        start = [(tag, attrs) for tag, attrs in doc.tags if attrs.get("id") == "pw"]
        self.assertEqual(len(start), 1)
        self.assertEqual(start[0][0], "a")
        self.assertEqual(start[0][1]["href"], "daily.html")
        destinations = {attrs["href"] for tag, attrs in doc.tags if tag == "a"}
        self.assertTrue({"daily.html", "random.html", "archive/index.html"} <= destinations)
        self.assertTrue(any(tag == "main" for tag, _ in doc.tags))
        self.assertTrue(any("deckbox" in attrs.get("class", "") for _, attrs in doc.tags))

    def test_date_is_plain_text_in_vinyl_and_metadata(self):
        doc = Markup(render_landing.build_html(42, 2169, '\"><img src=x onerror=alert(1)>'))
        self.assertFalse(any(tag == "img" for tag, _ in doc.tags))
        self.assertFalse(any(key.startswith("on") for _, attrs in doc.tags for key in attrs))

    def test_closed_dialog_is_hidden_from_assistive_technology(self):
        doc = Markup(lightbox.LIGHTBOX_HTML)
        attrs = next(attrs for _, attrs in doc.tags if attrs.get("id") == "lb")
        self.assertEqual(attrs["role"], "dialog")
        self.assertEqual(attrs["aria-hidden"], "true")
        self.assertTrue(any(tag == "button" and attrs.get("aria-label") == "关闭"
                            for tag, attrs in doc.tags))


# Small DOM boundary for executing the emitted JavaScript. It tracks browser-owned
# focus and event cancellation, while leaving navigation and native button clicks
# to the test. No browser or third-party Python/Node dependency is required.
DOM = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const handlers = {};
let doc;
class Element {
  constructor(tag='div', cls='', parent=null) {
    this.tagName=tag.toUpperCase(); this.parentElement=parent;
    this.classes=new Set(cls.split(/\s+/).filter(Boolean)); this.attrs={};
    this.classList={add:x=>this.classes.add(x),remove:x=>this.classes.delete(x),contains:x=>this.classes.has(x)};
    this.style={overflow:''}; this.dataset={}; this.children=[]; this.isConnected=true;
    this.scrollTop=80; this._html=''; this._text='';
    if(parent) parent.children.push(this);
  }
  set textContent(v) {this._text=String(v);this._html=String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  get textContent() {return this._text;}
  set innerHTML(v) {this._html=v;}
  get innerHTML() {return this._html;}
  setAttribute(k,v) {this.attrs[k]=v;}
  removeAttribute(k) {delete this.attrs[k];}
  hasAttribute(k) {return Object.hasOwn(this.attrs,k);}
  focus() {doc.activeElement=this;}
  getClientRects() {return this.style.display==='none'?[]:[{}];}
  insertAdjacentHTML(_,v) {this._html+=v;}
  contains(el) {for(;el;el=el.parentElement) if(el===this)return true;return false;}
  closest(selector) {
    for(let el=this;el;el=el.parentElement) {
      if(selector.split(',').some(s=>{
        s=s.trim();
        if(s.startsWith('.'))return el.classes.has(s.slice(1));
        if(s==='[data-close]')return el.hasAttribute('data-close');
        if(s==='[contenteditable="true"]')return el.attrs.contenteditable==='true';
        return el.tagName===s.toUpperCase();
      }))return el;
    }
    return null;
  }
}
const body=new Element('body'); body.style.overflow='clip';
const background=new Element('main','',body);
const alreadyInert=new Element('aside','',body); alreadyInert.setAttribute('inert','');
const dialog=new Element('div','',body);
const closeButton=new Element('button','x',dialog); closeButton.setAttribute('data-close','');
const info=new Element('div','info',dialog);
const link=new Element('a','',info); link.setAttribute('href','https://example.test');
const veil=new Element('div','veil',dialog); veil.setAttribute('data-close','');
const ids={lb:dialog};
for(const id of ['lb-big','lb-artist','lb-sub','lb-tags','lb-inpool','lb-inpool-w','lb-trkname',
  'lb-bio','lb-bio-w','lb-one','lb-one-w','lb-why','lb-scene','lb-trk-w','lb-links']) ids[id]=new Element('div','',info);
dialog.querySelector=s=>s==='.x'?closeButton:s==='.info'?info:null;
dialog.querySelectorAll=()=>[closeButton,link];
doc={body,activeElement:body,getElementById:id=>ids[id]||null,createElement:tag=>new Element(tag),
  addEventListener:(name,fn,capture)=>{(handlers[name]||=[]).push({fn,capture});}};
const context={document:doc,URL,Array,console,addEventListener:doc.addEventListener};
vm.runInNewContext(SCRIPT,context);
function event(type,target,extra={}) {
  const e={target,defaultPrevented:false,stopped:false,
    preventDefault(){this.defaultPrevented=true},stopPropagation(){this.stopped=true},...extra};
  for(const handler of handlers[type]||[])handler.fn(e);
  return e;
}
function trigger(tag='div') {
  const el=new Element(tag,'cover-zoom',background);
  el.dataset={title:'Song',artist:'Artist',album:'Album',year:'2000',why:'Notes',apple:'https://music.apple.com/track'};
  return el;
}
"""


@unittest.skipUnless(shutil.which("node"), "JavaScript interaction checks need Node.js")
class BrowserBehaviorTests(unittest.TestCase):
    def run_js(self, assertions, source=None, harness=DOM):
        script = source if source is not None else lightbox.lightbox_js(".cover-zoom")
        program = "const SCRIPT=" + json.dumps(script) + ";\n" + harness + assertions
        result = subprocess.run([shutil.which("node"), "-"], input=program, text=True,
                                encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_landing_does_not_register_global_keys_or_navigation_timer(self):
        self.run_js("", source=render_landing.LANDING_JS, harness=r"""
          const vm=require('node:vm');
          vm.runInNewContext(SCRIPT,{
            document:{getElementById:()=>null},
            addEventListener(){throw Error('must not capture unrelated keys')},
            setTimeout(){throw Error('navigation must not wait for a timer')},
            location:{set href(_){throw Error('native link owns navigation')}}
          });
        """)

    def test_native_cover_keyboard_and_nested_playback_are_not_intercepted(self):
        self.run_js(r"""
          const native=trigger('button');
          for(const key of ['Enter',' ']) {
            const e=event('keydown',native,{key});
            assert.equal(e.defaultPrevented,false);
            assert.equal(dialog.classList.contains('on'),false);
          }
          const old=trigger(), play=new Element('button','pbtn',old);
          for(const key of ['Enter',' '])assert.equal(event('keydown',play,{key}).defaultPrevented,false);
          event('click',play); assert.equal(dialog.classList.contains('on'),false);
          event('click',native); assert.equal(dialog.classList.contains('on'),true);
          assert.equal(doc.activeElement,closeButton);
        """)

    def test_legacy_cover_keyboard_and_close_restore_focus_and_existing_state(self):
        self.run_js(r"""
          const cover=trigger(); cover.focus();
          const opened=event('keydown',cover,{key:' '});
          assert.equal(opened.defaultPrevented,true); assert.equal(opened.stopped,true);
          assert.equal(dialog.classList.contains('on'),true);
          assert.equal(dialog.attrs['aria-hidden'],'false');
          assert.equal(background.hasAttribute('inert'),true);
          assert.equal(body.style.overflow,'hidden'); assert.equal(info.scrollTop,0);
          const escaped=event('keydown',closeButton,{key:'Escape'});
          assert.equal(escaped.defaultPrevented,true); assert.equal(escaped.stopped,true);
          assert.equal(dialog.classList.contains('on'),false);
          assert.equal(dialog.attrs['aria-hidden'],'true');
          assert.equal(doc.activeElement,cover); assert.equal(body.style.overflow,'clip');
          assert.equal(background.hasAttribute('inert'),false);
          assert.equal(alreadyInert.hasAttribute('inert'),true);
        """)

    def test_tab_cycles_current_controls_and_modal_keys_do_not_reach_player(self):
        self.run_js(r"""
          event('click',trigger()); link.focus();
          assert.equal(event('keydown',link,{key:'Tab'}).defaultPrevented,true);
          assert.equal(doc.activeElement,closeButton);
          event('keydown',closeButton,{key:'Tab',shiftKey:true}); assert.equal(doc.activeElement,link);
          background.focus(); event('keydown',background,{key:'Tab'}); assert.equal(doc.activeElement,closeButton);
          const space=event('keydown',closeButton,{key:' '});
          assert.equal(space.defaultPrevented,false); assert.equal(space.stopped,true);
          event('click',closeButton); assert.equal(dialog.classList.contains('on'),false);
        """)

    def test_backdrop_closes_but_unrelated_close_marker_does_not(self):
        self.run_js(r"""
          const other=new Element('button','',background); other.setAttribute('data-close','');
          event('click',other); assert.equal(body.style.overflow,'clip');
          const cover=trigger(); event('click',cover); event('click',veil);
          assert.equal(dialog.classList.contains('on'),false); assert.equal(doc.activeElement,cover);
        """)

    def test_untrusted_metadata_cannot_create_script_links_or_attributes(self):
        self.run_js(r"""
          const cover=trigger();
          cover.dataset={title:'Song',artist:'<img src=x onerror=alert(1)>',
            cover:'javascript:alert(1)',apple:'javascript:alert(2)',spotify:'https://open.spotify.com/track/ok'};
          event('click',cover);
          assert.equal(ids['lb-artist'].textContent,cover.dataset.artist);
          assert.equal(ids['lb-big'].innerHTML.includes('<img'),false);
          assert.equal(ids['lb-links'].innerHTML.includes('javascript:'),false);
          assert.equal(ids['lb-links'].innerHTML.includes('https://open.spotify.com/track/ok'),true);
        """)

    def test_related_track_links_reach_random_from_archive_and_identify_artist(self):
        self.run_js(r"""
          const cover=trigger();
          cover.dataset={title:'One',artist:'A & B',inpool:'One|Same Title'};
          event('click',cover);
          assert.equal(ids['lb-inpool'].innerHTML.includes('../random.html?t=Same%20Title&amp;artist=A%20%26%20B'),true);
          assert.equal(ids['lb-inpool'].innerHTML.includes('href="?t='),false);
        """, source=lightbox.lightbox_js(".cover-zoom", "../random.html"))

    def test_late_artist_context_updates_open_dialog_without_resetting_focus_or_scroll(self):
        self.run_js(r"""
          const cover=trigger(); event('click',cover);
          info.scrollTop=96; link.focus();
          cover.dataset.bio='Arrived later'; cover.dataset.years='1990–2020'; cover.dataset.inpool='Song|Second';
          event('musicdaily:artist-context',cover);
          assert.equal(ids['lb-bio'].textContent,'Arrived later');
          assert.equal(ids['lb-sub'].textContent,'1990–2020');
          assert.equal(ids['lb-inpool'].innerHTML.includes('Second'),true);
          assert.equal(info.scrollTop,96); assert.equal(doc.activeElement,link);
          const other=trigger(); other.dataset.bio='Wrong artist';
          event('musicdaily:artist-context',other);
          assert.equal(ids['lb-bio'].textContent,'Arrived later');
        """)


if __name__ == "__main__":
    unittest.main()
