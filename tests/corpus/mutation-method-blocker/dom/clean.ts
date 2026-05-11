// DOM and Web API allowance fixture for mutation-method-blocker.
//
// Every line is a canonical DOM mutation that legitimate UI code performs.
// The hook must process the file and return exit code 0 with no detector
// hits. Coverage spans:
//
//   - document property writes (not window: globalThis-style writes are
//     a separate detector and remain in scope by design)
//   - element / node / target property writes (innerHTML, textContent, ...)
//   - .style.* writes (CSS property assignments)
//   - .dataset.* writes (data-* attribute assignments)
//   - scrollTop / scrollLeft compound assignment
//   - typed-suffix receivers (myButton, submitBtn, inputRef, canvasEl)
//   - event.target / event.currentTarget chains

declare const document: any;

const root = document.getElementById('app');
root.innerHTML = '<p>hi</p>';
root.outerHTML = '<section/>';
root.textContent = 'plain text';
root.className = 'card active';
root.id = 'main';
root.title = 'Tooltip';
root.lang = 'en';
root.dir = 'ltr';
root.tabIndex = 0;
root.hidden = false;
root.draggable = true;
root.contentEditable = 'true';
root.spellcheck = false;
root.translate = true;
root.role = 'main';
root.slot = 'header';
root.part = 'shell';

const body = document.body;
body.scrollTop = 0;
body.scrollLeft += 10;
body.scrollTop -= 5;

document.title = 'New Page Title';
document.body.style.color = 'red';
document.body.style.backgroundColor = '#fff';
document.body.style['font-size'] = '14px';
document.documentElement.dataset.theme = 'dark';

const el = document.querySelector('.box');
el.innerHTML = '<span/>';
el.className = 'visible';
el.id = 'box-1';
el.dataset.value = '42';
el.dataset.userId = 'u-99';
el.style.display = 'block';
el.style.width = '100px';
el.style.opacity = '0.5';

const node = document.createElement('div');
node.textContent = 'hello';
node.className = 'note';

const target = document.querySelector('button');
target.disabled = true;
target.value = 'submit';
target.checked = true;
target.selected = false;
target.readOnly = false;
target.placeholder = 'Type here';

const submitBtn = document.querySelector('#submit');
submitBtn.disabled = false;
submitBtn.value = 'Send';

const inputRef = document.querySelector('input');
inputRef.value = 'hello';
inputRef.placeholder = 'Enter text';

const canvasEl = document.querySelector('canvas');
canvasEl.width = 800;
canvasEl.height = 600;

const linkEl = document.querySelector('a');
linkEl.href = '/dest';
linkEl.rel = 'noopener';

const imgEl = document.querySelector('img');
imgEl.src = '/static/photo.jpg';
imgEl.alt = 'photo';
imgEl.loading = 'lazy';
imgEl.width = 320;
imgEl.height = 240;

function onClick(event: any): void {
  event.target.value = '';
  event.currentTarget.disabled = true;
  event.target.style.color = 'blue';
  event.target.dataset.clicked = 'true';
}

function onScroll(e: any): void {
  e.target.scrollTop += 100;
  e.currentTarget.scrollLeft -= 50;
}

const host = document.querySelector('my-element');
host.shadowRoot.innerHTML = '<slot/>';

export {};
