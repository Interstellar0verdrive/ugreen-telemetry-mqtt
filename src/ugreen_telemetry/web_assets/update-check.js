'use strict';
// On-demand update check. This browser asks the GitHub API for the published
// releases; the NAS sends nothing and the setup container opens no connection.
const UPDATE_REPOSITORY = 'Interstellar0verdrive/ugreen-telemetry-mqtt';
const UPDATE_RELEASES_API = `https://api.github.com/repos/${UPDATE_REPOSITORY}/releases?per_page=30`;
const UPDATE_RELEASES_PAGE = `https://github.com/${UPDATE_REPOSITORY}/releases`;
const UPDATE_GUIDE = `https://github.com/${UPDATE_REPOSITORY}/blob/main/docs/release-and-updates.md#updating-in-ugos`;

// Versions follow Python's format: 0.3.0b2 is the second beta of 0.3.0, and
// 0.3.0a1 < 0.3.0b1 < 0.3.0rc1 < 0.3.0. Anything else is not comparable.
function parseVersion(text){
  const value=String(text).trim().replace(/^v/,'');
  const match=/^(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$/.exec(value);
  if(!match) return null;
  const stage=match[4]?{a:0,b:1,rc:2}[match[4]]:3;
  return {text:value,parts:[+match[1],+match[2],+match[3],stage,match[5]?+match[5]:0],stable:!match[4]};
}

function compareVersions(a,b){
  for(let i=0;i<a.parts.length;i++) if(a.parts[i]!==b.parts[i]) return a.parts[i]-b.parts[i];
  return 0;
}

// Pick the release to offer. A beta or release-candidate install follows every
// release; a stable install follows stable releases only.
function chooseUpdate(releases,installedText){
  const installed=parseVersion(installedText);
  const candidates=releases
    .filter(release=>release&&!release.draft)
    .map(release=>({url:release.html_url,version:parseVersion(release.tag_name)}))
    .filter(item=>item.version&&(!installed||!installed.stable||item.version.stable))
    .sort((a,b)=>compareVersions(b.version,a.version));
  const latest=candidates[0];
  if(!latest) return null;
  if(!installed) return {kind:'unknown',installed:null,latest};
  return {kind:compareVersions(latest.version,installed)>0?'available':'current',installed,latest};
}

if(typeof document!=='undefined'&&document.getElementById('update-check')){
  const byId=id=>document.getElementById(id);
  const button=byId('update-check');
  const label=byId('update-check-label');
  const box=byId('update');
  const notes=byId('update-notes');
  const guide=byId('update-guide');
  guide.href=UPDATE_GUIDE;

  const show=(kind,title,detail,link,linkText='Release notes')=>{
    box.className=`update is-${kind}`;
    byId('update-title').textContent=title;
    byId('update-detail').textContent=detail;
    notes.hidden=!link;
    if(link){notes.href=link;notes.textContent=linkText;}
    guide.hidden=kind!=='available';
    box.hidden=false;
  };

  button.addEventListener('click',async()=>{
    const installedText=byId('version').textContent;
    button.disabled=true;button.classList.add('is-checking');label.textContent='Checking…';
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),10000);
    try{
      const response=await fetch(UPDATE_RELEASES_API,{headers:{Accept:'application/vnd.github+json'},cache:'no-store',credentials:'omit',referrerPolicy:'no-referrer',signal:controller.signal});
      if(!response.ok) throw new Error(`GitHub answered ${response.status}`);
      const result=chooseUpdate(await response.json(),installedText);
      if(!result) throw new Error('No published release found');
      const latest=result.latest.version.text;
      if(result.kind==='unknown'){
        show('available',`The latest release is ${latest}`,'This page could not read its own version. Compare it with the image tag in UGOS Docker.',result.latest.url);
      }else if(result.kind==='available'){
        show('available',`Version ${latest} is available`,`You have ${result.installed.text}. Read the release notes, then update the project in UGOS Docker.`,result.latest.url);
      }else{
        show('current','You have the latest version',`${result.installed.text} is the newest ${result.installed.stable?'stable ':''}release.`,null);
      }
    }catch(_error){
      show('error','Update check unavailable','GitHub could not be reached from this browser. Try again later, or open the releases page.',UPDATE_RELEASES_PAGE,'Releases');
    }finally{
      clearTimeout(timer);
      button.disabled=false;button.classList.remove('is-checking');label.textContent='Check for updates';
    }
  });
  byId('update-close').addEventListener('click',()=>{box.hidden=true;button.focus();});
}
