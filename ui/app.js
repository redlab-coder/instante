'use strict';
const $=id=>document.getElementById(id);
const token=document.querySelector('meta[name="polaroid-editor-token"]').content;
const defaults=()=>({cx:.5,cy:.5,zoom:1,rotation:270,mode:'contain',brightness:1,contrast:1,saturation:1,sharpness:1});
const sliders=['zoom','brightness','contrast','saturation','sharpness'];
const labels={zoom:'Recorte',brightness:'Brilho',contrast:'Contraste',saturation:'Saturação',sharpness:'Nitidez'};
const sessionKey='polaroid-editor-session';
let photos=[],selected=null,filterReview=false,importing=false,exporting=false,clearing=false,restoring=false,closed=false;
let liveSourceCache=null,displayedPhoto=null;
let revision=0,sheetRevision=0,editorTimer,sheetTimer,toastTimer,liveFrame,drag,openedSheet;
let editingAllowed=false,releaseOwnership=null,acquiring=false,passiveAfterYield=false,sessionRevision=0,pendingRestore=null,syncTimer;
const sources=new Map(),urls=new Map(),sheetCache=new Map();
const tabId=crypto.randomUUID(),channel=typeof BroadcastChannel!=='undefined'?new BroadcastChannel('polaroid-editor:'+token):null;
const current=()=>photos.find(p=>p.id===selected);
const canEdit=()=>editingAllowed&&!closed&&!restoring&&!importing&&!exporting&&!clearing;
const item=p=>({id:p.id,edits:{...p.edits},reviewed:!!p.reviewed,manual:!!p.manual});
const visiblePhotos=()=>filterReview?photos.filter(p=>!p.reviewed):photos;
async function api(path,data={},raw=false,name=''){
  const response=await fetch('/api/'+path,{method:'POST',headers:{'X-PolaroidEditor-Token':token,'Content-Type':raw?'application/octet-stream':'application/json',...(name?{'X-Filename':encodeURIComponent(name)}:{})},body:raw?data:JSON.stringify(data)});
  if(!response.ok){let error;try{error=(await response.json()).error;}catch{}throw new Error(error||'Não foi possível concluir.');}return response;
}
function toast(message){clearTimeout(toastTimer);$('toast').textContent=message;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,6000);}
function activity(message=''){$('activity').textContent=message;}
function setUrl(key,blob){const old=urls.get(key),url=URL.createObjectURL(blob);urls.set(key,url);if(old)URL.revokeObjectURL(old);return url;}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
function saveSession(){
  if(!editingAllowed||restoring||closed)return;
  try{const latest=JSON.parse(localStorage.getItem(sessionKey));if(latest?.token===token&&(latest.sessionRevision||0)>sessionRevision){queueRestore(latest);return;}
    localStorage.setItem(sessionKey,JSON.stringify({token,sessionRevision:++sessionRevision,selected,filterReview,photos:photos.map(({thumb,previewError,...p})=>p)}));
  }catch{toast('Mantenha esta aba aberta e salve o lote para preservar seus ajustes.');}
}
function status(p){return p.reviewed?'Conferida':p.suggested?'Sugestão · conferir':'Conferir orientação';}
function refreshControls(){
  const p=current(),disabled=!p||!canEdit();
  $('empty-editor').hidden=!!p;$('tile-frame').hidden=!p;
  $('selected-name').textContent=p?.name||'Escolha uma foto';
  $('orientation-status').hidden=!p;$('orientation-status').textContent=p?status(p):'';
  $('orientation-status').title=p?.suggested?'Orientação sugerida por rostos. Confira antes de imprimir.':'Confira se a foto está em pé na prévia.';
  for(const id of ['center','rotate','invert','reset'])$(id).disabled=disabled;
  $('review-photo').disabled=disabled||!!drag||displayedPhoto!==p?.id;
  $('retry-preview').hidden=!p?.previewError;
  $('review-photo').setAttribute('aria-pressed',String(!!p?.reviewed));
  $('review-photo').title=p?.reviewed?'Marcar como a conferir (F)':filterReview?'Conferir e ir à próxima pendente (F)':'Marcar como conferida (F)';
  for(const button of document.querySelectorAll('[data-fit]')){button.disabled=disabled;button.setAttribute('aria-pressed',String(button.dataset.fit===(p?.edits.mode||'contain')));}
  $('fit-hint').textContent=p?.edits.mode==='cover'?'Preenche o quadrado, com recorte.':'Imagem inteira, com branco nas sobras.';
  for(const key of sliders){const off=disabled||(key==='zoom'&&p?.edits.mode!=='cover'),value=p?.edits[key]??1;
    $(key).disabled=off;$(key).value=value;$(key+'-number').disabled=off;$(key+'-zero').disabled=off;
    if(document.activeElement!==$(key+'-number'))$(key+'-number').value=key==='zoom'?value.toFixed(2):Math.round((value-1)*100);
    $(key+'-value').textContent=key==='zoom'?value.toFixed(2)+'×':Math.round((value-1)*100);
  }
  $('resolution').hidden=true;
  if(p){const effective=(p.edits.mode==='contain'?Math.max(p.width,p.height):Math.min(p.width,p.height)/p.edits.zoom)/945*300;
    if(effective<299){$('resolution').hidden=false;$('resolution').textContent=`Ampliação necessária · aproximadamente ${Math.round(effective)} DPI de detalhe original.`;$('resolution').title='A saída é gravada a 300 DPI; ampliar não recupera detalhes ausentes.';}}
  for(const id of ['add','drop','empty-add','open-project'])$(id).disabled=!canEdit();
  $('clear-all').hidden=!photos.length;$('clear-all').disabled=!photos.length||!canEdit();
  $('save-project').disabled=!photos.length||!canEdit();$('export').disabled=!photos.length||exporting||importing||restoring||clearing;
  $('review-batch').disabled=!photos.length||importing||restoring||clearing;
  $('download-sheet').disabled=exporting||importing||clearing;
  $('clear-confirm').disabled=clearing;$('clear-cancel').disabled=clearing;
  if(!exporting)$('export-label').textContent=photos.length?`Exportar ${photos.length} foto${photos.length===1?'':'s'}`:'Exportar JPG';
  $('export').title=$('export-label').textContent;$('export').setAttribute('aria-label',$('export-label').textContent);
}
function renderLibrary(){
  const focused=document.activeElement?.classList.contains('photo-select');
  $('count').textContent=photos.length;
  const pending=photos.filter(p=>!p.reviewed).length;$('filter-review').hidden=!pending&&!filterReview;
  $('filter-review').textContent=filterReview?'Mostrar todas':`${pending} a conferir`;$('filter-review').setAttribute('aria-pressed',String(filterReview));
  $('photo-list').replaceChildren();
  for(const p of visiblePhotos()){
    const index=photos.indexOf(p),row=document.createElement('div');row.className='photo-row'+(p.id===selected?' active':'')+(!p.reviewed?' to-review':'');row.dataset.id=p.id;
    const selectButton=document.createElement('button');selectButton.className='photo-select';selectButton.setAttribute('aria-label','Editar '+p.name);selectButton.onclick=()=>select(p.id);
    const img=p.thumb?document.createElement('img'):document.createElement('span');if(p.thumb){img.src=p.thumb;img.alt='';}else{img.className='photo-placeholder';img.innerHTML=PolaroidEditorIcons.svg('portrait');}
    const detail=document.createElement('div');detail.className='photo-detail';const name=document.createElement('strong');name.textContent=p.name;name.title=p.name;
    const sub=document.createElement('small');sub.textContent=p.previewError?'Tentar prévia':status(p);sub.title=`${p.width} × ${p.height} pixels`;
    detail.append(name,sub);selectButton.append(img,detail);
    const actions=document.createElement('div');actions.className='row-actions';
    for(const [icon,label,fn,off] of [['up','Mover para cima',()=>move(index,-1),index===0],['down','Mover para baixo',()=>move(index,1),index===photos.length-1],['remove','Remover foto',()=>remove(p.id),false]]){
      const b=document.createElement('button');b.innerHTML=PolaroidEditorIcons.svg(icon);b.title=label;b.setAttribute('aria-label',label+' '+p.name);b.disabled=off||!canEdit();b.onclick=fn;actions.append(b);}
    row.append(selectButton,actions);$('photo-list').append(row);
  }
  if(filterReview&&!pending){const message=document.createElement('p');message.className='review-empty';message.textContent='Todas as fotos foram conferidas.';message.setAttribute('role','status');$('photo-list').append(message);}
  $('sheet-summary').textContent=photos.length?`${photos.length} foto${photos.length===1?'':'s'}`:'';
  refreshControls();if(focused)focusSelectedPhoto();
}
function focusSelectedPhoto(focus=true){const row=[...$('photo-list').children].find(r=>r.dataset.id===selected);if(!row)return;if(focus)row.querySelector('.photo-select').focus({preventScroll:true});const a=$('photo-list').getBoundingClientRect(),b=row.getBoundingClientRect();if(b.top<a.top)$('photo-list').scrollTop+=b.top-a.top;if(b.bottom>a.bottom)$('photo-list').scrollTop+=b.bottom-a.bottom;if(b.left<a.left)$('photo-list').scrollLeft+=b.left-a.left;if(b.right>a.right)$('photo-list').scrollLeft+=b.right-a.right;}
function select(id){if(selected!==id){drag=null;$('tile-frame').classList.remove('dragging');displayedPhoto=null;$('tile-image').getContext('2d').clearRect(0,0,$('tile-image').width,$('tile-image').height);$('tile-frame').setAttribute('aria-busy','true');}selected=id;revision++;renderLibrary();drawLive();renderEditor();saveSession();}
async function sourceFor(p){
  if(!sources.has(p.id))sources.set(p.id,(async()=>createImageBitmap(await(await api('source',{id:p.id})).blob()))());
  try{const bitmap=await sources.get(p.id);for(const [id,promise]of sources){if(sources.size<=3)break;if(id!==p.id){sources.delete(id);promise.then(b=>b.close()).catch(()=>{});}}return bitmap;}
  catch(e){sources.delete(p.id);throw e;}
}
function paintComposition(bitmap,id){
  const c=$('tile-image'),ctx=c.getContext('2d');c.width=1063;c.height=1500;
  ctx.save();ctx.translate(1063,0);ctx.rotate(Math.PI/2);ctx.drawImage(bitmap,0,0,1500,1063);ctx.restore();displayedPhoto=id;$('tile-frame').removeAttribute('aria-busy');$('review-photo').disabled=!canEdit()||!!drag;sizeFrame();
}
function sizeFrame(){const area=$('canvas-area').getBoundingClientRect(),ratio=1063/1500;const h=Math.max(40,Math.min(area.height-36,(area.width-36)/ratio));$('tile-frame').style.setProperty('--frame-height',h+'px');$('tile-frame').style.setProperty('--frame-width',h*ratio+'px');}
function cropGeometry(p,w,h){const e=p.edits,side=Math.min(w,h)/e.zoom;const cx=Math.max(side/2,Math.min(w-side/2,e.cx*w)),cy=Math.max(side/2,Math.min(h-side/2,e.cy*h));return{x:cx-side/2,y:cy-side/2,side};}
function drawLive(){
  if(liveFrame||closed)return;liveFrame=requestAnimationFrame(async()=>{liveFrame=null;const p=current(),request=revision;if(!p)return;
    try{const source=await sourceFor(p);if(request!==revision||current()?.id!==p.id||closed)return;
      const e=p.edits,key=JSON.stringify([p.id,e.rotation,e.brightness,e.contrast,e.saturation,p.content_box]);
      if(liveSourceCache?.key!==key){
        const turn=e.rotation%180!==0,oriented=document.createElement('canvas');oriented.width=turn?source.height:source.width;oriented.height=turn?source.width:source.height;
        const oc=oriented.getContext('2d');oc.translate(oriented.width/2,oriented.height/2);oc.rotate(e.rotation*Math.PI/180);oc.drawImage(source,-source.width/2,-source.height/2);
        const filtered=document.createElement('canvas');filtered.width=oriented.width;filtered.height=oriented.height;const fc=filtered.getContext('2d');fc.fillStyle='white';fc.fillRect(0,0,filtered.width,filtered.height);
        let [left,top,right,bottom]=p.content_box||[0,0,1,1];for(let r=0;r<e.rotation;r+=90)[left,top,right,bottom]=[1-bottom,left,1-top,right];
        const x=Math.round(left*filtered.width),y=Math.round(top*filtered.height),endX=Math.round(right*filtered.width),endY=Math.round(bottom*filtered.height);
        fc.save();fc.beginPath();fc.rect(x,y,Math.max(0,endX-x),Math.max(0,endY-y));fc.clip();fc.filter=`brightness(${e.brightness}) contrast(${e.contrast}) saturate(${e.saturation})`;fc.drawImage(oriented,0,0);fc.restore();liveSourceCache={key,id:p.id,canvas:filtered};
      }
      const oriented=liveSourceCache.canvas;
      const page=document.createElement('canvas');page.width=1500;page.height=1063;const ctx=page.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,1500,1063);ctx.fillStyle='red';ctx.fillRect(1295,0,205,1063);
      ctx.save();ctx.imageSmoothingQuality='high';
      if(e.mode==='contain'){const scale=945/Math.max(oriented.width,oriented.height),w=Math.round(oriented.width*scale),h=Math.round(oriented.height*scale);ctx.drawImage(oriented,70+Math.round((945-w)*e.cx),59+Math.round((945-h)*e.cy),w,h);}
      else{const g=cropGeometry(p,oriented.width,oriented.height);ctx.drawImage(oriented,g.x,g.y,g.side,g.side,70,59,945,945);}
      ctx.restore();paintComposition(page,p.id);
    }catch{if(request===revision){$('retry-preview').hidden=false;}}
  });
}
async function renderEditor(){const p=current(),request=++revision;refreshControls();if(!p)return;
  try{const blob=await(await api('preview',item(p))).blob();if(request!==revision||current()?.id!==p.id||drag||closed)return;
    const bitmap=await createImageBitmap(blob);if(request!==revision||current()?.id!==p.id||drag||closed){bitmap.close();return;}paintComposition(bitmap,p.id);bitmap.close();p.previewError=false;$('retry-preview').hidden=true;
  }catch{if(request===revision){p.previewError=true;$('retry-preview').hidden=false;toast('A foto foi preservada. Tente carregar a prévia novamente.');}}
}
async function updateThumbnail(p){try{const fingerprint=JSON.stringify(p.edits),blob=await(await api('thumbnail',item(p))).blob();if(!photos.includes(p)||fingerprint!==JSON.stringify(p.edits))return;p.thumb=setUrl('thumb-'+p.id,blob);const img=[...$('photo-list').children].find(r=>r.dataset.id===p.id)?.querySelector('img');if(img)img.src=p.thumb;return blob;}catch{p.previewError=true;}}
function changed({manual=false}={}){const p=current();if(!p||!canEdit())return;if(manual){p.manual=true;p.suggested=false;}p.reviewed=false;revision++;refreshControls();drawLive();saveSession();
  clearTimeout(editorTimer);editorTimer=setTimeout(()=>{if(!drag){renderEditor();updateThumbnail(p).then(()=>renderLibrary());}},180);
  clearTimeout(sheetTimer);sheetTimer=setTimeout(()=>{if(!drag)renderSheets();},450);
}
async function uprightPreview(blob){
  const bitmap=await createImageBitmap(blob);
  try{const canvas=document.createElement('canvas');canvas.width=bitmap.height;canvas.height=bitmap.width;const context=canvas.getContext('2d');context.translate(canvas.width,0);context.rotate(Math.PI/2);context.drawImage(bitmap,0,0);
    return await new Promise((resolve,reject)=>canvas.toBlob(result=>result?resolve(result):reject(new Error('Não foi possível criar a prévia.')),'image/png'));
  }finally{bitmap.close();}
}
async function renderSheets(){
  const request=++sheetRevision,snapshot=photos.map(item);$('sheets').replaceChildren();
  if(!snapshot.length){$('sheets').innerHTML='<div class="empty-sheet">Suas montagens aparecerão aqui.</div>';sheetCache.clear();for(const [key,url] of urls)if(key.startsWith('sheet-')){URL.revokeObjectURL(url);urls.delete(key);}return;}
  const cards=[];
  snapshot.forEach((s,i)=>{const card=document.createElement('div');card.className='sheet-card';const button=document.createElement('button');button.className='sheet-open';button.setAttribute('aria-label','Ampliar montagem '+(i+1));button.disabled=true;button.onclick=()=>openSheet(s.id);const img=document.createElement('img');img.alt='Montagem '+(i+1);button.append(img);const label=document.createElement('div');label.className='sheet-label';const name=document.createElement('span');name.textContent=photos[i].name;name.title=photos[i].name;label.append(name);card.append(button,label);$('sheets').append(card);cards.push({button,img});});
  for(let i=0;i<snapshot.length;i++){
    if(request!==sheetRevision)return;const s=snapshot[i],fingerprint=JSON.stringify(s.edits);let cached=sheetCache.get(s.id);
    try{if(!cached||cached.fingerprint!==fingerprint){const blob=await uprightPreview(await(await api('preview',s)).blob());if(request!==sheetRevision)return;cached={blob,fingerprint,snapshot:s,name:photos.find(p=>p.id===s.id)?.name};sheetCache.set(s.id,cached);}
      cards[i].img.src=setUrl('sheet-'+s.id,cached.blob);cards[i].button.disabled=false;
    }catch{cards[i].img.alt='Prévia indisponível';}
  }
  const keep=new Set(snapshot.map(s=>s.id));for(const key of sheetCache.keys())if(!keep.has(key)){sheetCache.delete(key);const old=urls.get('sheet-'+key);if(old)URL.revokeObjectURL(old);urls.delete('sheet-'+key);}
}
async function importFiles(files){
  files=files.filter(file=>!['thumbs.db','.ds_store','desktop.ini'].includes(file.name.toLowerCase()));
  if(!canEdit()||!files.length)return;importing=true;renderLibrary();const errors=[];let first;
  try{for(let i=0;i<files.length;i++){const f=files[i];activity(`Importando ${i+1} de ${files.length}`);
    try{const p=await(await api('upload',f,true,f.name)).json();p.edits=defaults();p.reviewed=false;p.manual=false;photos.push(p);first??=p.id;
      try{const result=await(await api('orientation',{id:p.id})).json();p.edits.rotation=result.rotation;p.initialRotation=result.rotation;p.suggested=result.suggested;}catch{p.initialRotation=270;p.suggested=false;}
      await updateThumbnail(p);if(!selected)selected=p.id;renderLibrary();saveSession();
    }catch(e){errors.push(f.name+': '+e.message);}}
  }finally{importing=false;$('files').value='';activity();}
  selected??=first||null;renderLibrary();renderEditor();renderSheets();saveSession();toast(errors.length?errors.join(' • '):'Fotos adicionadas. Confira as orientações antes de imprimir.');
}
function move(index,delta){if(!canEdit())return;const other=index+delta;if(other<0||other>=photos.length)return;[photos[index],photos[other]]=[photos[other],photos[index]];renderLibrary();renderSheets();saveSession();}
async function remove(id){if(!canEdit())return;try{await api('delete',{id});photos=photos.filter(p=>p.id!==id);releasePhoto(id);if(selected===id)selected=visiblePhotos()[0]?.id||photos[0]?.id||null;renderLibrary();renderEditor();renderSheets();saveSession();}catch(e){toast(e.message);}}
function releasePhoto(id){for(const key of ['thumb-'+id,'sheet-'+id]){const url=urls.get(key);if(url)URL.revokeObjectURL(url);urls.delete(key);}sources.get(id)?.then(b=>b.close()).catch(()=>{});sources.delete(id);sheetCache.delete(id);if(liveSourceCache?.id===id)liveSourceCache=null;if(displayedPhoto===id)displayedPhoto=null;}
async function clearPhotos(){
  if(!canEdit()||!photos.length)return;const ids=photos.map(p=>p.id);clearing=true;revision++;sheetRevision++;clearTimeout(editorTimer);clearTimeout(sheetTimer);cancelAnimationFrame(liveFrame);liveFrame=null;drag=null;$('tile-frame').classList.remove('dragging');renderLibrary();activity('Removendo fotos…');
  try{await api('clear',{ids});photos.forEach(p=>releasePhoto(p.id));photos=[];selected=null;filterReview=false;liveSourceCache=null;displayedPhoto=null;openedSheet=null;$('batch-grid').replaceChildren();$('sheet-dialog-image').removeAttribute('src');const dialogUrl=urls.get('dialog');if(dialogUrl)URL.revokeObjectURL(dialogUrl);urls.delete('dialog');saveSession();$('clear-dialog').close();toast('Fotos removidas da sessão.');}
  catch(e){toast(e.message);}finally{clearing=false;activity();renderLibrary();renderEditor();renderSheets();flushRestore();if(!photos.length)$('empty-add').focus();}
}
async function exportItems(snapshot){
  if(exporting||importing||clearing||!snapshot.length)return;exporting=true;renderLibrary();
  try{const {job}=await(await api('export/start',{items:snapshot})).json();let state;
    do{state=await(await api('export/status',{job})).json();$('export-label').textContent=`${state.done} de ${state.total}`;activity(`Exportando ${state.done} de ${state.total}`);if(state.state==='failed')throw new Error(state.error);if(state.state!=='ready')await new Promise(resolve=>setTimeout(resolve,350));}while(state.state!=='ready');
    const response=await api('export/download',{job});download(await response.blob(),state.filename);toast('Download iniciado · '+(snapshot.length>1?'ZIP com as montagens em JPG.':'JPG a 300 DPI.'));
  }catch(e){toast(e.message);}finally{exporting=false;activity();renderLibrary();flushRestore();}
}
function openSheet(id){const cached=sheetCache.get(id);if(!cached)return;openedSheet={...cached.snapshot,edits:{...cached.snapshot.edits}};$('sheet-dialog-title').textContent=cached.name||'Montagem';$('sheet-dialog-image').src=setUrl('dialog',cached.blob);$('sheet-dialog').showModal();}
async function saveProject(){if(!canEdit()||!photos.length)return;const snapshot=photos.map(item);exporting=true;renderLibrary();activity('Salvando lote…');
  try{const blob=await(await api('project/save',{items:snapshot})).blob();download(blob,'Meu lote.polaroid');toast('Download do lote iniciado. Guarde o arquivo .polaroid para continuar depois.');}
  catch(e){toast(e.message);}finally{exporting=false;activity();renderLibrary();flushRestore();}}
async function openProject(file){if(!file||!canEdit())return;if(photos.length&&!confirm('Abrir este lote substitui a sessão atual. Salve o lote atual antes, se precisar continuar depois.'))return;importing=true;renderLibrary();activity('Abrindo lote…');
  try{const result=await(await api('project/open',file,true)).json();photos.forEach(p=>releasePhoto(p.id));photos=result.photos.map(p=>({...p,initialRotation:p.edits.rotation}));selected=photos[0]?.id||null;filterReview=false;for(const p of photos)await updateThumbnail(p);saveSession();}
  catch(e){toast(e.message);}finally{importing=false;$('project-file').value='';activity();renderLibrary();renderEditor();renderSheets();saveSession();flushRestore();}}

for(const id of ['add','drop','empty-add'])$(id).onclick=()=>$('files').click();
$('files').onchange=e=>importFiles([...e.target.files]);
$('open-project').onclick=()=>$('project-file').click();$('project-file').onchange=e=>openProject(e.target.files[0]);$('save-project').onclick=saveProject;
$('clear-all').onclick=()=>{if(canEdit()&&photos.length){$('clear-message').textContent=`Remover ${photos.length===1?'a foto':`as ${photos.length} fotos`} desta sessão? Salve o lote antes para guardar os ajustes.`;$('clear-dialog').showModal();}};
$('clear-confirm').onclick=clearPhotos;
$('clear-dialog').addEventListener('cancel',e=>{if(clearing)e.preventDefault();});
// Only external files trigger import; pointer gestures still position the photo.
const importArea=$('import-area');let fileDragDepth=0;
const fileDrag=e=>Array.from(e.dataTransfer?.types||[]).includes('Files');
const acceptsDrop=()=>canEdit()&&!document.querySelector('dialog[open]');
function clearFileDrag(){fileDragDepth=0;importArea.classList.remove('file-drop-active');}
importArea.addEventListener('dragenter',e=>{if(!fileDrag(e))return;e.preventDefault();fileDragDepth++;if(acceptsDrop())importArea.classList.add('file-drop-active');});
importArea.addEventListener('dragover',e=>{if(!fileDrag(e))return;e.preventDefault();e.dataTransfer.dropEffect=acceptsDrop()?'copy':'none';if(!acceptsDrop())clearFileDrag();});
importArea.addEventListener('dragleave',e=>{if(!fileDrag(e))return;if(--fileDragDepth<=0)clearFileDrag();});
importArea.addEventListener('drop',e=>{if(!fileDrag(e))return;e.preventDefault();e.stopPropagation();clearFileDrag();if(acceptsDrop())importFiles(Array.from(e.dataTransfer.files));});
// Prevent the browser from navigating to a dropped file outside the import area.
for(const type of ['dragover','drop'])document.addEventListener(type,e=>{if(fileDrag(e)){e.preventDefault();if(type==='drop'||!importArea.contains(e.target)){clearFileDrag();e.dataTransfer.dropEffect='none';}}});
document.addEventListener('dragend',clearFileDrag);window.addEventListener('blur',clearFileDrag);
for(const key of sliders){const output=$(key+'-value'),controls=document.createElement('span');controls.className='precise-control';const numeric=document.createElement('input');numeric.type='number';numeric.id=key+'-number';numeric.min=key==='zoom'?'1':'-100';numeric.max=key==='zoom'?'5':key==='sharpness'?'200':'100';numeric.step=key==='zoom'?'0.01':'1';numeric.setAttribute('aria-label',labels[key]+' exato');const zero=document.createElement('button');zero.id=key+'-zero';zero.innerHTML=PolaroidEditorIcons.svg('reset');zero.title='Restaurar '+labels[key].toLowerCase();zero.setAttribute('aria-label',zero.title);controls.append(numeric,zero);output.classList.add('sr-only');output.after(controls);
  function apply(value){const p=current();if(!p||!canEdit()||(key==='zoom'&&p.edits.mode!=='cover'))return;p.edits[key]=Math.max(Number($(key).min),Math.min(Number($(key).max),Math.round(value*100)/100));changed();}
  $(key).oninput=()=>apply(Number($(key).value));numeric.oninput=()=>{if(numeric.value&&numeric.validity.valid)apply(key==='zoom'?Number(numeric.value):1+Number(numeric.value)/100);};numeric.onchange=()=>refreshControls();numeric.onkeydown=e=>{if(e.key==='Enter')numeric.blur();};zero.onclick=()=>apply(1);
}
document.querySelectorAll('[data-fit]').forEach(b=>b.onclick=()=>{const p=current();if(!p||!canEdit())return;p.edits.mode=b.dataset.fit;p.edits.zoom=1;p.edits.cx=p.edits.cy=.5;changed();});
function rotate(degrees){const p=current();if(!p||!canEdit())return;for(let i=0;i<degrees;i+=90){const {cx,cy}=p.edits;p.edits.rotation=(p.edits.rotation+90)%360;p.edits.cx=1-cy;p.edits.cy=cx;}changed({manual:true});}
$('rotate').onclick=()=>rotate(90);$('invert').onclick=()=>rotate(180);
$('center').onclick=()=>{const p=current();if(!p||!canEdit())return;p.edits.cx=p.edits.cy=.5;changed();};
$('reset').onclick=()=>{const p=current();if(!p||!canEdit())return;p.edits={...defaults(),rotation:p.initialRotation??270};p.manual=false;p.reviewed=false;changed();renderLibrary();};
function toggleReviewed(){
  const p=current();if(!p||!canEdit()||drag||displayedPhoto!==p.id)return;const index=photos.indexOf(p);p.reviewed=!p.reviewed;
  if(filterReview&&p.reviewed){const next=photos.slice(index+1).find(photo=>!photo.reviewed)||photos.slice(0,index).find(photo=>!photo.reviewed);if(next){select(next.id);focusSelectedPhoto(false);return;}}
  saveSession();renderLibrary();
}
$('review-photo').onclick=toggleReviewed;
$('filter-review').onclick=()=>{filterReview=!filterReview;const visible=visiblePhotos();if(visible.length&&!visible.some(p=>p.id===selected)){select(visible[0].id);return;}renderLibrary();saveSession();};
document.addEventListener('keydown',e=>{if(e.key.toLowerCase()!=='f'||e.repeat||e.isComposing||e.ctrlKey||e.altKey||e.metaKey||document.querySelector('dialog[open]')||e.target.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"])')||!canEdit()||!current())return;e.preventDefault();toggleReviewed();});
$('photo-list').addEventListener('keydown',e=>{if(!['ArrowUp','ArrowDown'].includes(e.key)||e.target.closest('.row-actions')||e.ctrlKey||e.altKey||e.shiftKey||importing)return;const list=visiblePhotos();if(!list.length)return;e.preventDefault();const index=list.findIndex(p=>p.id===selected),next=Math.max(0,Math.min(list.length-1,index+(e.key==='ArrowDown'?1:-1)));select(list[next].id);focusSelectedPhoto();});
$('photo-list').onclick=e=>{if(e.target.closest('.photo-select'))focusSelectedPhoto();else if(!e.target.closest('button'))$('photo-list').focus();};
function moveBy(dx,dy){const p=current();if(!p||!canEdit())return;const e=p.edits;[dx,dy]=[dy,-dx];const turn=e.rotation%180!==0,w=turn?p.height:p.width,h=turn?p.width:p.height;if(e.mode==='cover'){e.cx=Math.max(0,Math.min(1,e.cx-dx/w));e.cy=Math.max(0,Math.min(1,e.cy-dy/h));}else{e.cx=Math.max(0,Math.min(1,e.cx+dx/945));e.cy=Math.max(0,Math.min(1,e.cy+dy/945));}changed();}
$('tile-frame').onpointerdown=e=>{if(!canEdit()||!current())return;e.preventDefault();$('tile-frame').focus({preventScroll:true});drag={x:e.clientX,y:e.clientY,moved:false};$('tile-frame').setPointerCapture(e.pointerId);$('tile-frame').classList.add('dragging');refreshControls();};
$('tile-frame').onpointermove=e=>{if(!drag)return;const unit=1063/$('tile-frame').clientWidth;const dx=(e.clientX-drag.x)*unit,dy=(e.clientY-drag.y)*unit;drag.x=e.clientX;drag.y=e.clientY;if(dx||dy){drag.moved=true;moveBy(dx,dy);}};
for(const type of ['pointerup','pointercancel','lostpointercapture'])$('tile-frame').addEventListener(type,()=>{if(!drag)return;const moved=drag.moved;drag=null;$('tile-frame').classList.remove('dragging');if(moved)changed();else refreshControls();});
$('tile-frame').onkeydown=e=>{const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];if(!delta)return;e.preventDefault();moveBy(...delta.map(x=>x*(e.shiftKey?10:1)));};
$('export').onclick=()=>exportItems(photos.map(item));$('download-sheet').onclick=()=>openedSheet&&exportItems([{...openedSheet,edits:{...openedSheet.edits}}]);
$('review-batch').onclick=()=>{const grid=$('batch-grid');grid.replaceChildren();for(const p of photos){const button=document.createElement('button');button.className='batch-card';const img=document.createElement('img');img.alt='Montagem de '+p.name;if(p.thumb)img.src=p.thumb;const name=document.createElement('strong');name.textContent=p.name;const sub=document.createElement('small');sub.textContent=status(p);button.append(img,name,sub);button.onclick=()=>{$('batch-dialog').close();select(p.id);$('tile-frame').focus();};grid.append(button);}$('batch-dialog').showModal();};
$('retry-preview').onclick=()=>{renderEditor();renderSheets();};$('help').onclick=()=>$('help-dialog').showModal();
document.querySelectorAll('[data-close-dialog]').forEach(b=>b.onclick=()=>b.closest('dialog').close());
document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',e=>{if(d.id==='clear-dialog'&&clearing)return;if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}}));
$('sheet-dialog').onclose=()=>{openedSheet=null;};
$('quit').onclick=async()=>{if(importing||exporting||clearing){toast('Aguarde a operação terminar antes de encerrar.');return;}if(photos.length&&!confirm('Salvou o lote ou exportou suas montagens? Encerrar descarta a sessão atual.'))return;try{await api('quit');closed=true;editingAllowed=false;releaseOwnership?.();channel?.close();localStorage.removeItem(sessionKey);clearInterval(heartbeat);document.body.innerHTML='<main style="padding-top:100px;text-align:center"><h1>Até a próxima montagem.</h1><p>O Polaroid Editor foi encerrado. Você pode fechar esta aba.</p></main>';}catch(e){toast(e.message);}};
async function refreshAppStatus(){const state=await(await api('heartbeat')).json();if(closed)return;const update=state.update,show=['available','downloading','ready'].includes(update?.state);$('update-status').hidden=!show;if(show){$('update-label').textContent=update.state==='downloading'?'Baixando atualização':'Atualização disponível';$('update-status').title=`Versão ${update.version}. A atualização é aplicada ao encerrar o Polaroid Editor.`;}}
const heartbeat=setInterval(()=>refreshAppStatus().catch(()=>{clearInterval(heartbeat);toast('A sessão foi encerrada. Abra o Polaroid Editor novamente.');}),20000);refreshAppStatus().catch(()=>{});

async function restoreSession(saved){
  if(!saved||saved.token!==token||!Array.isArray(saved.photos))return;restoring=true;revision++;sheetRevision++;clearTimeout(editorTimer);clearTimeout(sheetTimer);
  try{sessionRevision=saved.sessionRevision||0;const previous=new Map(photos.map(p=>[p.id,p]));const keep=new Set(saved.photos.map(p=>p.id));for(const old of photos)if(!keep.has(old.id))releasePhoto(old.id);
    photos=saved.photos.map(p=>({...p,edits:{...defaults(),...p.edits}}));selected=photos.some(p=>p.id===saved.selected)?saved.selected:photos[0]?.id||null;filterReview=saved.filterReview===true;
    for(const p of photos){const old=previous.get(p.id);if(old?.thumb&&JSON.stringify(old.edits)===JSON.stringify(p.edits))p.thumb=old.thumb;else await updateThumbnail(p);}
  }finally{restoring=false;renderLibrary();renderEditor();renderSheets();}
}
function refreshOwnershipUI(){if(closed)return;$('session-banner').hidden=editingAllowed;renderLibrary();}
function queueRestore(saved){if(!saved||saved.token!==token||(saved.sessionRevision||0)<=sessionRevision)return;pendingRestore=saved;clearTimeout(syncTimer);syncTimer=setTimeout(flushRestore,100);}
function flushRestore(){if(!pendingRestore||drag||importing||exporting||clearing||restoring||closed)return;const saved=pendingRestore;pendingRestore=null;if((saved.sessionRevision||0)>sessionRevision)restoreSession(saved).catch(()=>toast('Não foi possível recuperar a prévia. A sessão foi preservada.'));}
function readSession(){try{return JSON.parse(localStorage.getItem(sessionKey));}catch{return null;}}
function tryAcquireEditor(wait=false){
  if(acquiring||editingAllowed||closed||(!wait&&passiveAfterYield))return;
  if(wait)passiveAfterYield=false;
  if(!navigator.locks){editingAllowed=true;refreshOwnershipUI();return;}
  acquiring=true;
  const controller=wait?new AbortController():null;
  const timeout=controller?setTimeout(()=>controller.abort(),5000):null;
  // Explicit transfer waits for the old holder to release instead of racing a timer.
  navigator.locks.request('polaroid-editor:editing:'+token,controller?{signal:controller.signal}:{ifAvailable:true},async lock=>{
    clearTimeout(timeout);acquiring=false;if(!lock){refreshOwnershipUI();return;}
    editingAllowed=true;const hold=new Promise(resolve=>releaseOwnership=resolve),saved=readSession();
    if(saved?.token===token&&(saved.sessionRevision||0)>sessionRevision)await restoreSession(saved);
    refreshOwnershipUI();await hold;releaseOwnership=null;editingAllowed=false;
  }).catch(error=>{clearTimeout(timeout);acquiring=false;toast(error.name==='AbortError'?'A outra aba está ocupada. Aguarde a operação terminar e tente novamente.':'Não foi possível ativar a edição nesta aba.');});
}
function yieldEditor(){if(!editingAllowed||importing||exporting||clearing||restoring)return false;saveSession();passiveAfterYield=true;editingAllowed=false;drag=null;clearTimeout(editorTimer);clearTimeout(sheetTimer);refreshOwnershipUI();releaseOwnership?.();return true;}
if(channel)channel.onmessage=e=>{if(closed)return;if(e.data.type==='yield'&&editingAllowed){if(yieldEditor())channel.postMessage({type:'released',target:e.data.from});}if(e.data.type==='released'&&e.data.target===tabId){queueRestore(readSession());tryAcquireEditor(true);}};
$('takeover').onclick=()=>{channel?.postMessage({type:'yield',from:tabId});tryAcquireEditor(true);};
window.addEventListener('focus',()=>{if(!editingAllowed)tryAcquireEditor();});
window.addEventListener('storage',e=>{if(e.key===sessionKey&&!closed&&e.newValue){try{queueRestore(JSON.parse(e.newValue));}catch{}}});
window.addEventListener('pagehide',()=>{saveSession();editingAllowed=false;releaseOwnership?.();});
window.addEventListener('pageshow',e=>{if(e.persisted){queueRestore(readSession());tryAcquireEditor();}});
new ResizeObserver(sizeFrame).observe($('canvas-area'));
refreshOwnershipUI();(async()=>{const saved=readSession();if(saved?.token===token)await restoreSession(saved);tryAcquireEditor();})();
