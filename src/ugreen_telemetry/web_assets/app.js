'use strict';
const $ = id => document.getElementById(id);
const form = $('setup');
const tabsBar = document.querySelector('.tabs');
const tabsAnchor = document.querySelector('.tabs-anchor');
const tabs = [...document.querySelectorAll('.tab')];
const panels = [...document.querySelectorAll('#setup > .panel')];
const mobileLayout = window.matchMedia('(max-width:660px)');
const defaults = {cpu:1,memory:1,cpu_temperature:15,hdd:15,nvme:15,uptime:15,volume:15,diagnostics:15};
const readings = [
  ['cpu','CPU usage','Current processor load',1],
  ['memory','Memory usage','Current RAM usage',1],
  ['cpu_temperature','CPU temperature','Processor temperature, when exposed',1],
  ['hdd','HDD temperatures','Selected SATA hard drives',5],
  ['nvme','SSD and NVMe temperatures','Detected solid-state storage',5],
  ['uptime','Uptime','Time since the NAS started',1],
  ['volume','Volume space','Used and available space on selected volumes',1],
  ['diagnostics','HDD SMART diagnostics','Optional health counters',5]
];
let token = sessionStorage.getItem('ugreenSetupToken') || '';
let configured = false;
let busy = false;
let savedPassword = '';
function feedback(id, value, kind='error'){
  const node = $(id);
  node.textContent = value;
  node.classList.toggle('is-error',kind==='error');
  node.classList.toggle('is-success',kind==='success');
  node.hidden = !value;
}
async function api(path, options={}){
  let response;
  try{
    response = await fetch(path,{...options,headers:{Authorization:'Bearer '+token,...(options.headers||{})}});
  }catch{
    throw Error('Could not reach the setup service. Check that the setup container is running, then reopen this page using the NAS address.');
  }
  if(response.status===401) throw Error('Setup token not accepted. Copy the current 43-character code from the setup container log, without spaces.');
  let data;
  try{data=await response.json();}catch{throw Error('The setup service returned an invalid response.');}
  if(!response.ok) throw Error(data.error || 'Request failed');
  return data;
}
function syncStickyTabs(){
  if($('workspace').hidden) return;
  tabsBar.classList.toggle('is-stuck',!mobileLayout.matches && tabsAnchor.getBoundingClientRect().bottom <= 0);
}
if('IntersectionObserver' in window) new IntersectionObserver(syncStickyTabs).observe(tabsAnchor);
window.addEventListener('scroll',syncStickyTabs,{passive:true});
function showTab(tab){
  for(const item of tabs) item.setAttribute('aria-selected',String(item===tab));
  tabsBar.dataset.active=String(tabs.indexOf(tab));
  if(!mobileLayout.matches) for(const panel of panels) panel.hidden=panel.id!==tab.getAttribute('aria-controls');
}
for(const tab of tabs) tab.addEventListener('click',()=>showTab(tab));
function syncLayout(){
  syncStickyTabs();
  if(mobileLayout.matches){
    for(const panel of panels){
      panel.hidden=false;
      panel.setAttribute('role','region');
      panel.setAttribute('aria-label',panel.querySelector('h2').textContent);
    }
  }else{
    for(const panel of panels){panel.setAttribute('role','tabpanel');panel.removeAttribute('aria-label');}
    showTab(tabs.find(tab=>tab.getAttribute('aria-selected')==='true')||tabs[0]);
  }
}
mobileLayout.addEventListener('change',syncLayout);
function markDirty(){
  $('saved').textContent='Unsaved changes';
  feedback('message','');
}
function bindSelection(card, numericInput){
  const checkbox=card.querySelector('input[type="checkbox"]');
  const sync=()=>{
    card.classList.toggle('is-off',!checkbox.checked);
    if(numericInput) numericInput.disabled=!checkbox.checked;
  };
  checkbox.addEventListener('change',()=>{sync();markDirty();});
  sync();
}
function makeChoice(value,title,detail,checked,wide=false){
  const label=document.createElement('label');
  label.className='choice'+(wide?' choice-wide':'');
  const input=document.createElement('input');
  input.type='checkbox';input.value=value;input.checked=checked;
  const body=document.createElement('span');
  const strong=document.createElement('strong');strong.textContent=title;
  const small=document.createElement('small');small.textContent=detail;
  body.append(strong,small);label.append(input,body);
  bindSelection(label);
  return label;
}
function renderStorage(data,config){
  const diskBox=$('disks');diskBox.replaceChildren();
  for(const disk of data.disks){
    const name=disk.path.split('/').pop();
    const choice=makeChoice(disk.path,`${disk.type} ${name}`,`${disk.path} · ${disk.type==='HDD'?'SATA hard drive':'SATA solid-state drive'}`,config.disks.includes(disk.path));
    diskBox.append(choice);
  }
  if(!data.disks.length) diskBox.textContent='No SATA disks discovered. Check the /host/sys mount.';
  const count=()=>{$('disk-count').textContent=`${diskBox.querySelectorAll('input:checked').length} selected`;};
  diskBox.addEventListener('change',count);count();
  const volumeBox=$('volumes');volumeBox.replaceChildren();
  for(const volume of data.volumes){
    volumeBox.append(makeChoice(volume.path,`Volume ${volume.label}`,volume.path.replace('/host',''),config.volumes.includes(volume.path),true));
  }
  if(!data.volumes.length) volumeBox.textContent='No mounted data volumes exposed by this project.';
}
function normalizeInterval(input){
  const minimum=Number(input.dataset.min);
  const maximum=Number(input.dataset.max);
  const value=Number(input.value);
  input.value=String(input.value&&Number.isFinite(value)?Math.min(maximum,Math.max(minimum,value)):minimum);
}
function renderReadings(config){
  const box=$('groups');box.replaceChildren();
  for(const [group,title,detail,minimum] of readings){
    const card=document.createElement('div');card.className='reading';card.dataset.group=group;
    const main=document.createElement('div');main.className='reading-main';
    const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.value=group;checkbox.checked=config.sensor_groups.includes(group);
    checkbox.setAttribute('aria-label',`Publish ${title}`);
    const body=document.createElement('span');
    const strong=document.createElement('strong');strong.textContent=title;
    const small=document.createElement('small');small.textContent=detail;
    body.append(strong,small);main.append(checkbox,body);
    const interval=document.createElement('label');interval.className='interval';
    const number=document.createElement('input');number.type='text';number.inputMode='numeric';number.pattern='[0-9]{1,3}';number.maxLength=3;
    number.dataset.min=String(minimum);number.dataset.max='999';number.value=String(config.intervals?.[group]??defaults[group]);
    number.setAttribute('aria-label',`${title} interval in minutes`);
    const suffix=document.createElement('span');suffix.textContent='min';interval.append(number,suffix);
    card.append(main,interval);box.append(card);
    bindSelection(card,number);
    card.addEventListener('click',event=>{
      if(event.target.closest('input, .interval, button, a, select, textarea')) return;
      if(window.getSelection()?.toString()) return;
      checkbox.click();
    });
    number.addEventListener('beforeinput',event=>{if(event.data&&/[^0-9]/.test(event.data)) event.preventDefault();});
    number.addEventListener('input',()=>{number.value=number.value.replace(/[^0-9]/g,'').slice(0,3);markDirty();});
    number.addEventListener('blur',()=>normalizeInterval(number));
  }
}
function setSaved(timestamp){
  const label=timestamp?`Last saved: ${new Date(timestamp*1000).toLocaleString()}`:'Changes on all three tabs are saved together.';
  $('saved').textContent=label;
}
async function unlock(){
  const entered=$('token').value.trim();
  token=entered||token;
  if(!token){feedback('login-message','Enter the setup token.');$('token').focus();return;}
  if(location.protocol==='file:'){
    feedback('login-message','This local file is a preview. Open the setup page using the NAS address to check a token.');
    return;
  }
  $('unlock').disabled=true;
  feedback('login-message','');
  try{
    const data=await api('/api/status');
    const secret=await api('/api/password');
    sessionStorage.setItem('ugreenSetupToken',token);
    configured=!!data.config;
    const config=data.config||{nas_name:'UGREEN NAS',nas_id:'ugreennas',mqtt_port:1883,mqtt_protocol:'5',sensor_groups:Object.keys(defaults).filter(group=>group!=='diagnostics'),disks:[],volumes:[],intervals:defaults};
    for(const name of ['nas_name','nas_id','mqtt_host','mqtt_port','mqtt_user','mqtt_protocol']) form.elements[name].value=config[name]??'';
    savedPassword=secret.password||'';
    form.elements.mqtt_password.value=savedPassword;
    setSecretVisibility(form.elements.mqtt_password,$('password-visibility'),false,'MQTT password');
    form.elements.mqtt_tls.checked=!!config.mqtt_tls;
    const tlsRow=document.querySelector('.tls-row');
    tlsRow.classList.toggle('is-off',!form.elements.mqtt_tls.checked);
    form.elements.mqtt_tls.addEventListener('change',()=>tlsRow.classList.toggle('is-off',!form.elements.mqtt_tls.checked));
    $('password-hint').textContent=savedPassword?'Saved on this NAS. Reveal only on a trusted local network.':'Required for the first save.';
    renderStorage(data,config);renderReadings(config);
    $('login').hidden=true;$('workspace').hidden=false;$('footer').hidden=false;$('verified').hidden=false;
    setSaved(data.saved_at);syncLayout();
    $('token').value='';
  }catch(error){
    feedback('login-message',error.message);
    sessionStorage.removeItem('ugreenSetupToken');token='';
  }finally{$('unlock').disabled=false;}
}
$('login').addEventListener('submit',event=>{event.preventDefault();unlock();});
function setSecretVisibility(input,button,visible,label){
  input.type=visible?'text':'password';
  button.setAttribute('aria-pressed',String(visible));
  button.setAttribute('aria-label',`${visible?'Hide':'Show'} ${label}`);
  button.title=`${visible?'Hide':'Show'} ${label}`;
  button.querySelector('.eye-open').toggleAttribute('hidden',!visible);
  button.querySelector('.eye-closed').toggleAttribute('hidden',visible);
}
for(const [input,button,label] of [[$('token'),$('token-visibility'),'setup token'],[form.elements.mqtt_password,$('password-visibility'),'MQTT password']]){
  button.addEventListener('click',()=>setSecretVisibility(input,button,input.type==='password',label));
}
form.addEventListener('input',markDirty);
form.addEventListener('change',markDirty);
function checkedValues(id){return [...$(id).querySelectorAll('input[type="checkbox"]:checked')].map(input=>input.value);}
function validateFields(){
  if(!savedPassword&&!form.elements.mqtt_password.value){
    form.elements.mqtt_password.setCustomValidity('Enter an MQTT password for the first save.');
  }else form.elements.mqtt_password.setCustomValidity('');
  for(const field of form.querySelectorAll('input,select')){
    if(field.disabled||field.checkValidity()) continue;
    const panel=field.closest('.panel');
    if(panel&&!mobileLayout.matches) showTab(tabs.find(tab=>tab.getAttribute('aria-controls')===panel.id));
    field.focus();field.reportValidity();return false;
  }
  return true;
}
const saveButton = document.querySelector('.save');
    let saveClickPoint = null;
    let pressStartedAt = null;
    let pressPointerId = null;
    let chargeTimer = 0;
    let saveHold = 0;
    saveButton.addEventListener('pointerdown', event => {
      if(!event.isPrimary) return;
      saveHold = 0;
      pressStartedAt = null;
      pressPointerId = null;
      saveButton.classList.remove('is-charged');
      clearTimeout(chargeTimer);
      const mouseOnDesktop = event.pointerType === 'mouse' && window.matchMedia('(min-width:661px) and (hover:hover) and (pointer:fine)').matches;
      if(!mouseOnDesktop) return;
      pressStartedAt = performance.now();
      pressPointerId = event.pointerId;
      chargeTimer = setTimeout(() => {
        if(pressStartedAt !== null) saveButton.classList.add('is-charged');
      },1200);
    });
    window.addEventListener('pointerup', event => {
      if(event.pointerId !== pressPointerId || pressStartedAt === null) return;
      saveHold = Math.min(1,Math.max(0,(performance.now() - pressStartedAt - 250)/950));
      if(saveHold === 1) saveButton.classList.add('is-charged');
      pressStartedAt = null;
      pressPointerId = null;
      clearTimeout(chargeTimer);
    });
    window.addEventListener('pointercancel', event => {
      if(event.pointerId !== pressPointerId) return;
      pressStartedAt = null;
      pressPointerId = null;
      saveHold = 0;
      clearTimeout(chargeTimer);
    });
    saveButton.addEventListener('click', event => {
      saveClickPoint = event.detail > 0 ? {x:event.clientX,y:event.clientY} : null;
      if(event.detail === 0) saveHold = 0;
    });
    let activeConfetti = null;
    function stopConfetti(){
      if(!activeConfetti) return;
      cancelAnimationFrame(activeConfetti.frame);
      activeConfetti.layer.remove();
      activeConfetti = null;
    }
    function celebrateSave(clickPoint, intensity){
      stopConfetti();
      if(document.hidden || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      const bounds = saveButton.getBoundingClientRect();
      const originX = clickPoint?.x ?? bounds.left + bounds.width / 2;
      const originY = clickPoint?.y ?? bounds.top + bounds.height / 2;
      const lowMemory = Number.isFinite(navigator.deviceMemory) && navigator.deviceMemory <= 2;
      const desktop = !lowMemory && window.matchMedia('(min-width:900px) and (pointer:fine)').matches;
      const count = (lowMemory ? 80 : 200) + Math.round((lowMemory ? 60 : desktop ? 180 : 100)*intensity);
      const layer = document.createElement('div');
      layer.className = 'confetti-layer';
      layer.setAttribute('aria-hidden','true');
      const fragment = document.createDocumentFragment();
      const particles = Array.from({length:count}, () => {
        const element = document.createElement('span');
        element.className = 'confetti-piece';
        fragment.appendChild(element);
        return {
          element,x:0,y:0,z:0,wobble:Math.random()*10,
          wobbleSpeed:.1+Math.random()*.1,
          glidePhase:Math.random()*Math.PI*2,
          glideAmplitude:14+Math.random()*12+(desktop ? 12 : 8)*intensity,
          velocity:(17.5+Math.random()*35)*(1+(desktop ? .5 : .35)*intensity),
          angle:(-135-(desktop ? 15 : 10)*intensity+Math.random()*(90+(desktop ? 30 : 20)*intensity))*Math.PI/180,
          angle3D:(Math.random()-.5)*Math.PI/2,
          tilt:Math.random()*Math.PI,
          tiltSpeed:.1+Math.random()*.3
        };
      });
      layer.appendChild(fragment);
      document.body.appendChild(layer);
      activeConfetti = {layer,frame:0};
      let start = 0;
      let previous = 0;
      let slowFrames = 0;
      const duration = 2400+(desktop ? 550 : 400)*intensity;
      function update(time){
        if(activeConfetti?.layer !== layer) return;
        if(!start) start = time;
        if(previous && time - previous < 14){
          activeConfetti.frame = requestAnimationFrame(update);
          return;
        }
        const frameGap = previous ? time - previous : 0;
        const step = Math.min((time - (previous || time))/16.67,2);
        previous = time;
        const elapsed = time - start;
        const fallSpeed = 3 + Math.min(4,Math.max(0,elapsed - 450)/225);
        const glideAmount = Math.min(1,Math.max(0,elapsed - 450)/300);
        const workStarted = performance.now();
        for(let index=0;index<particles.length;index++){
          if(elapsed < index*.2) continue;
          const particle = particles[index];
          particle.x += Math.cos(particle.angle)*particle.velocity*step;
          particle.y += Math.sin(particle.angle)*particle.velocity*step + fallSpeed*step;
          particle.z += Math.sin(particle.angle3D)*particle.velocity*step;
          particle.velocity *= Math.pow(.9,step);
          particle.wobble += particle.wobbleSpeed*step;
          particle.tilt += particle.tiltSpeed*step;
          const glide = glideAmount*particle.glideAmplitude*Math.sin(elapsed/300 + particle.glidePhase);
          const x = originX + particle.x + 10*Math.cos(particle.wobble) + glide;
          const y = originY + particle.y + 10*Math.sin(particle.wobble);
          particle.element.style.transform = `translate3d(${x}px,${y}px,${particle.z}px) rotate3d(1,1,1,${particle.tilt}rad)`;
          particle.element.style.opacity = String(Math.max(0,1-elapsed/duration));
          particle.element.style.visibility = 'visible';
        }
        if(elapsed < 800 && particles.length > 80){
          const slowFrame = frameGap > 30 || performance.now() - workStarted > 11;
          slowFrames = slowFrame ? slowFrames + 1 : Math.max(0,slowFrames - 1);
          if(slowFrames >= 2){
            const nextCount = particles.length > 120 ? Math.max(120,Math.round(particles.length*.7)) : 80;
            for(const particle of particles.splice(nextCount)) particle.element.remove();
            slowFrames = 0;
          }
        }
        if(elapsed < duration && !document.hidden){
          activeConfetti.frame = requestAnimationFrame(update);
        }else{
          stopConfetti();
        }
      }
      activeConfetti.frame = requestAnimationFrame(update);
    }
    document.addEventListener('visibilitychange', () => {if(document.hidden) stopConfetti();});
form.addEventListener('submit',async event=>{
  event.preventDefault();
  if(busy||!validateFields()) return;
  for(const input of $('groups').querySelectorAll('.interval input')) normalizeInterval(input);
  const intervals={};
  for(const card of $('groups').querySelectorAll('.reading')) intervals[card.dataset.group]=Number(card.querySelector('.interval input').value);
  const payload={
    nas_name:form.elements.nas_name.value.trim(),nas_id:form.elements.nas_id.value.trim(),
    mqtt_host:form.elements.mqtt_host.value.trim(),mqtt_port:Number(form.elements.mqtt_port.value),
    mqtt_user:form.elements.mqtt_user.value.trim(),mqtt_protocol:form.elements.mqtt_protocol.value,
    mqtt_tls:form.elements.mqtt_tls.checked,disks:checkedValues('disks'),volumes:checkedValues('volumes'),
    sensor_groups:checkedValues('groups'),intervals
  };
  const enteredPassword=form.elements.mqtt_password.value;
  if(enteredPassword&&enteredPassword!==savedPassword) payload.mqtt_password=enteredPassword;
  busy=true;saveButton.disabled=true;saveButton.textContent='Saving…';feedback('message','');
  try{
    await api('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    configured=true;
    if(enteredPassword) savedPassword=enteredPassword;
    form.elements.mqtt_password.value=savedPassword;
    setSecretVisibility(form.elements.mqtt_password,$('password-visibility'),false,'MQTT password');
    $('password-hint').textContent='Saved on this NAS. Reveal only on a trusted local network.';
    setSaved(Date.now()/1000);
    feedback('message','Settings saved. The telemetry service is starting; check the setup container log for its MQTT connection.','success');
    celebrateSave(saveClickPoint,saveHold);
  }catch(error){
    feedback('message',error.message);
    $('saved').textContent='Not saved';
  }finally{
    busy=false;saveButton.disabled=false;saveButton.textContent='Save and start telemetry';
    saveClickPoint=null;saveHold=0;
  }
});
if(token) unlock();
