const $ = id => document.getElementById(id);
let session, current = 0, dirty = false, saving = false, toastTimer;
const names = {'gpt-4o-mini':'GPT-4o mini','gpt-5.4-mini':'GPT-5.4 mini','gpt-6-luna':'GPT-6 Luna','gpt-6-sol':'GPT-6 Sol','claude-sonnet-5-5':'Claude Sonnet 5.5','claude-opus-5-5':'Claude Opus 5.5'};
function node(tag, text, cls) { const e=document.createElement(tag); if(text!==undefined)e.textContent=text; if(cls)e.className=cls; return e; }
function highlight(element, text) {
  element.replaceChildren();
  for(const part of (text || '').split(/(TARGETCIT|OTHERCIT)/g)) element.append(part==='TARGETCIT'?node('mark',part):part==='OTHERCIT'?node('span',part,'other-citation'):document.createTextNode(part));
}
function toast(text) { $('toast').textContent=text; $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').hidden=true,3500); }
function refreshNavigation() {
  const saved=Object.keys(session.decisions).filter(id=>session.cases.some(c=>c.context_id===id)).length;
  $('progress-label').textContent=`${saved} / ${session.cases.length}`;
  $('progress').max=session.cases.length || 1; $('progress').value=saved;
  $('remaining').textContent=`${session.cases.length-saved} citas por revisar`;
  $('completed-banner').hidden=saved!==session.cases.length;
  $('case-list').replaceChildren();
  session.cases.forEach((c,i)=>{
    const b=node('button',String(i+1).padStart(2,'0'),'case-button');b.type='button';
    b.title=`${c.context_id} · ${session.decisions[c.context_id]?'Guardada':'Pendiente'}`;
    b.setAttribute('aria-label',`Cita ${i+1}, ${session.decisions[c.context_id]?'guardada':'pendiente'}`);
    if(session.decisions[c.context_id])b.classList.add('done');
    if(i===current){b.classList.add('current');b.setAttribute('aria-current','step');}
    b.onclick=()=>navigate(i);$('case-list').append(b);
  });
}
function toggleFunction() {
  const available=$('evaluability').value==='Evaluable';
  $('function-field').hidden=!available;
  document.querySelectorAll('input[name="function"]').forEach(r=>{r.required=available;r.disabled=!available;});
}
function render() {
  const c=session.cases[current];
  if(!c){$('startup').hidden=false;$('startup').textContent='No hay citas pendientes en este consolidado.';$('workspace').hidden=true;return;}
  $('case-title').textContent=`Cita ${String(current+1).padStart(2,'0')} de ${session.cases.length}`;
  $('case-id').textContent=c.context_id;
  highlight($('context'),c.contexto_original);
  $('paper-title').textContent=c.titulo_citado || 'Sin título disponible';
  $('abstract').textContent=c.resumen_citado || 'Sin resumen disponible';
  const votes=JSON.parse(c.votos_por_funcion || '{}');
  $('vote-summary').textContent=Object.entries(votes).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`${k} · ${v}`).join(' / ');
  $('models').replaceChildren();
  for(const [model,name] of Object.entries(names)) {
    const card=node('article',undefined,'model'),top=node('div',undefined,'model-top');
    top.append(node('span',name,'model-name'),node('span',c[model+'__evaluabilidad']==='Evaluable'?c[model+'__funcion']:c[model+'__evaluabilidad'] || 'Sin respuesta','pill'));
    card.append(top,node('p',c[model+'__justificacion'] || 'Sin justificación disponible.'));
    if(c[model+'__evidencia'])card.append(node('blockquote',c[model+'__evidencia']));
    card.append(node('span',`Confianza: ${c[model+'__confianza'] || 'Sin declarar'}`,'hint'));$('models').append(card);
  }
  const d=session.decisions[c.context_id];
  $('evaluability').value=d?.evaluabilidad || 'Evaluable';
  $('confidence').value=d?.confianza || 'Media';
  $('justification').value=d?.justificacion || '';
  document.querySelectorAll('input[name="function"]').forEach(r=>r.checked=r.value===d?.funcion);
  toggleFunction();
  $('save-state').className='save-state';
  $('save-state').textContent=d?`Decisión guardada · ${new Date(d.fecha).toLocaleString('es')}`:'Sin decisión guardada';
  $('save').textContent=d?'Actualizar y continuar →':'Guardar y continuar →';
  $('previous').disabled=current===0;$('next').disabled=current===session.cases.length-1;
  $('models-panel').open=false;
  dirty=false;refreshNavigation();
}
function navigate(index) {
  if(saving || index<0 || index>=session.cases.length)return;
  if(dirty && !confirm('Hay cambios sin guardar. ¿Quieres descartarlos y cambiar de cita?'))return;
  current=index;render();window.scrollTo({top:0,behavior:'instant'});
}
async function save(event) {
  event?.preventDefault();if(saving || !$('decision-form').reportValidity())return;
  const c=session.cases[current],ev=$('evaluability').value;
  const body={evaluabilidad:ev,funcion:ev==='Evaluable'?(document.querySelector('input[name="function"]:checked')?.value || ''):'',
    confianza:$('confidence').value,justificacion:$('justification').value,
    version:session.decisions[c.context_id]?.version || 0};
  saving=true;$('save').disabled=true;$('save-state').textContent='Guardando en este equipo…';
  try {
    const res=await fetch('/api/decisions/'+encodeURIComponent(c.context_id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!res.ok){const error=await res.json();throw Error(typeof error.detail==='string'?error.detail:'Revisa los campos de tu decisión e inténtalo otra vez.');}
    session.decisions[c.context_id]=await res.json();dirty=false;
    const next=session.cases.findIndex((r,i)=>i>current && !session.decisions[r.context_id]);
    const first=session.cases.findIndex(r=>!session.decisions[r.context_id]);
    current=next>=0?next:first>=0?first:current;render();toast('Decisión guardada en este equipo.');
  } catch(error){$('save-state').className='save-state error';$('save-state').textContent=error.message;}
  finally{saving=false;$('save').disabled=false;}
}
async function start() {
  try {
    const res=await fetch('/api/session');if(!res.ok)throw Error('No se pudo leer la cola de revisión.');session=await res.json();
    for(const [i,c] of session.classes.entries()){
      const label=node('label',undefined,'function-option'),input=node('input');input.type='radio';input.name='function';input.value=c.name;input.id='function-'+i;
      const text=node('span',c.name);text.append(node('small',c.definition));label.append(input,text);$('functions').append(label);
    }
    $('source').textContent='Versión del consolidado: '+session.source;
    document.querySelector('footer').firstChild.textContent=`Las ${session.accepted_automatically} decisiones por consenso se conservan. Aquí solo se revisan las citas pendientes. `;
    current=Math.max(0,session.cases.findIndex(c=>!session.decisions[c.context_id]));
    $('startup').hidden=true;$('workspace').hidden=false;render();
  }catch(error){$('startup').textContent=error.message+' Recarga la página para intentarlo de nuevo.';}
}
$('decision-form').addEventListener('submit',save);
$('decision-form').addEventListener('input',()=>{dirty=true;$('save-state').textContent='Cambios sin guardar';$('save-state').className='save-state';});
$('evaluability').addEventListener('change',toggleFunction);
$('previous').onclick=()=>navigate(current-1);$('next').onclick=()=>navigate(current+1);
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();save();}});
start();
