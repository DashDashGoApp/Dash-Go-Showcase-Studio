(function(){
  const query=new URLSearchParams(window.location.search);
  if(query.get("showcaseStudio")!=="1")return;
  const hubURL=query.get("showcaseHub")||"",token=query.get("showcaseToken")||"";
  if(!hubURL||!token)return;
  const presets=[
    ["presentation","fit","Presentation Fit","Use this display · high-DPI"],
    ["landscape","wall-landscape","Wall Display Preview","1920 × 1080 CSS"],
    ["landscape","laptop","Laptop Preview","1366 × 768 CSS"],
    ["landscape","wide-tablet","16:10 Preview","1280 × 800 CSS"],
    ["portrait","portrait-wall","Portrait Wall Preview","1080 × 1920 CSS"],
    ["portrait","portrait-tablet","Portrait Tablet Preview","800 × 1280 CSS"],
    ["portrait","portrait-four-three","4:3 Portrait Preview","768 × 1024 CSS"],
  ];
  const root=document.createElement("aside");root.id="showcase-view";
  root.innerHTML="<button class='showcase-view-toggle' aria-expanded='false'>Presentation <span>▾</span></button><section class='showcase-view-panel' hidden><div class='showcase-view-head'><strong>Presentation &amp; Preview</strong><button data-clean>Clean View</button></div><p class='showcase-view-copy'>Presentation Fit uses the current display. Device previews preserve the selected CSS aspect ratio and scale only when the display is smaller.</p><div data-groups></div><p class='showcase-view-status' role='status' aria-live='polite'>Startup window · Native high-DPI presentation</p></section>";
  document.body.appendChild(root);
  const panel=root.querySelector(".showcase-view-panel"),toggle=root.querySelector(".showcase-view-toggle"),groups=root.querySelector("[data-groups]"),status=root.querySelector(".showcase-view-status");
  const restore=document.createElement("button");restore.id="showcase-view-restore";restore.textContent="View ▸";restore.hidden=true;document.body.appendChild(restore);
  const buttons=new Map();let busy=false;
  function group(name){const box=document.createElement("section");box.className="showcase-view-group";box.innerHTML="<p>"+name+"</p><div class='showcase-view-grid'></div>";groups.appendChild(box);return box.querySelector(".showcase-view-grid");}
  const presentation=group("Presentation"),landscape=group("Device previews"),portrait=group("Portrait previews");
  function setBusy(value){busy=value;buttons.forEach(button=>{button.disabled=value;});}
  function setActive(id){buttons.forEach((button,key)=>{button.setAttribute("aria-pressed",String(key===id));button.classList.toggle("is-active",key===id);});}
  function previewStatus(result){
    if(result.fit)return "Presentation Fit · "+result.presentation;
    const host=result.hostWidth&&result.hostHeight?" · window "+result.hostWidth+" × "+result.hostHeight:"";
    const scale=result.scalePercent&&result.scalePercent<100?" · "+result.scalePercent+"% scale":" · 100% scale";
    return result.width+" × "+result.height+" CSS · "+result.orientation+host+scale;
  }
  async function pick(id,label){
    if(busy)return;
    setBusy(true);status.textContent="Switching to "+label+"…";
    try{
      const response=await fetch(hubURL+"/api/viewport?token="+encodeURIComponent(token),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({preset:id})});
      const result=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(result.error||"Presentation could not change.");
      setActive(id);status.textContent=previewStatus(result);panel.hidden=true;toggle.setAttribute("aria-expanded","false");
    }finally{setBusy(false);}
  }
  presets.forEach(([groupName,id,label,size])=>{const button=document.createElement("button");button.type="button";button.setAttribute("aria-pressed","false");button.innerHTML="<b>"+label+"</b><small>"+size+"</small>";button.onclick=()=>pick(id,label).catch(error=>{status.textContent=error.message;});buttons.set(id,button);({presentation,landscape,portrait}[groupName]).appendChild(button);});
  toggle.onclick=()=>{const open=panel.hidden;panel.hidden=!open;toggle.setAttribute("aria-expanded",String(open));};
  root.querySelector("[data-clean]").onclick=()=>{root.hidden=true;restore.hidden=false;document.documentElement.classList.add("showcase-clean-view");};
  restore.onclick=()=>{root.hidden=false;restore.hidden=true;document.documentElement.classList.remove("showcase-clean-view");};
})();
