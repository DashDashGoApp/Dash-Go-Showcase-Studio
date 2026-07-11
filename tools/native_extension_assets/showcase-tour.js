(function(){
  const query=new URLSearchParams(window.location.search);
  if(query.get("showcaseStudio")!=="1")return;
  const hubURL=query.get("showcaseHub")||"",token=query.get("showcaseToken")||"";
  const city=query.get("showcaseCity")||"your selected city",locationID=query.get("showcaseLocation")||"chicago";
  const alertEvent=query.get("showcaseAlertEvent")||"Weather Advisory",alertSeverity=query.get("showcaseAlertSeverity")||"moderate";
  const isTour=()=>query.get("showcaseTour")==="1";
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  let index=0,card=null,alertItem=null,listsPreview=false,active=isTour();
  const surfaceSelectors=["#ctrl.show","#scrim.show","#applauncher.show","#chorewheel.show","#familyboard.show","#maintenance.show","#routines.show","#listsapp.show"];
  const call=(name,...args)=>typeof window[name]==="function"?window[name](...args):undefined;
  function primaryVisible(){return surfaceSelectors.filter(selector=>document.querySelector(selector));}
  async function clearPrimarySurface(){
    call("closeOverlaysForIdle");
    call("closeAppLauncher");call("closeChoreWheel");call("closeFamilyBoard");call("closeMaintenance");call("closeRoutines");call("closeListsApp");call("closeCtrl");call("closeScrim");
    for(let attempt=0;attempt<18&&primaryVisible().length;attempt++)await wait(35);
  }
  async function showListsPreview(){
    if(listsPreview)return;
    for(let attempt=0;attempt<20;attempt++){
      if(typeof window.dashboardListsDockEnable==="function"){await window.dashboardListsDockEnable();listsPreview=true;return;}
      await wait(75);
    }
  }
  function hideListsPreview(){
    if(typeof window.dashboardListsDockDisable==="function")window.dashboardListsDockDisable();
    listsPreview=false;
  }
  function addAlertPreview(){
    if(alertItem)return;
    // ALERTS is a lexical global in the compiled Dash-Go bundle, not a window
    // property. Keep this Studio-only preview inside the real alert renderer.
    if(typeof ALERTS==="undefined"||!Array.isArray(ALERTS))return;
    alertItem={_test:true,_showcase:true,event:alertEvent,severity:alertSeverity,headline:"Sample Weather Alert — Studio Preview",description:"This is fictional, offline showcase data for "+city+". Dash-Go can surface important weather conditions without making the dashboard feel noisy.",instruction:"No action is needed. This sample clears when the Studio tour ends.",ends:new Date(Date.now()+90*60000)};
    ALERTS.unshift(alertItem);
    if(typeof renderAlerts==="function")renderAlerts();
    if(typeof showAlertPopup==="function")showAlertPopup(alertItem);
  }
  function removeAlertPreview(){
    if(!alertItem)return;
    if(typeof ALERTS!=="undefined"&&Array.isArray(ALERTS))ALERTS=ALERTS.filter(item=>item!==alertItem&&!item._showcase);
    alertItem=null;
    if(typeof renderAlerts==="function")renderAlerts();
    const title=document.getElementById("poptitle");
    if(title&&String(title.textContent||"").includes("Sample Weather Alert"))call("closeScrim");
  }
  function removeCard(){if(card){card.remove();card=null;}}
  async function cleanTourPresentation(closeSurface){
    removeCard();removeAlertPreview();hideListsPreview();
    if(closeSurface)await clearPrimarySurface();
  }
  async function hubPost(path,body){
    if(!hubURL||!token)throw new Error("Studio Home is unavailable.");
    const response=await fetch(hubURL+path+"?token="+encodeURIComponent(token),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body||{})});
    if(!response.ok)throw new Error(await response.text()||"Studio action could not finish.");
    return response.json();
  }
  async function returnHome(){
    await cleanTourPresentation(true);
    const result=await hubPost("/api/return-home",{});
    window.location.assign(result.hubURL);
  }
  async function restart(){
    await cleanTourPresentation(true);
    const result=await hubPost("/api/restart-tour",{location:locationID});
    window.location.assign(result.dashboardURL);
  }
  async function finish(){
    active=false;await cleanTourPresentation(true);
    const next=new URL(window.location.href);next.searchParams.delete("showcaseTour");
    window.history.replaceState({},document.title,next.pathname+(next.search||"")+next.hash);
  }
  function locationModal(){
    const prior=document.getElementById("showcase-location-lock");if(prior)prior.remove();
    const modal=document.createElement("section");modal.id="showcase-location-lock";modal.setAttribute("role","dialog");modal.setAttribute("aria-modal","true");
    modal.innerHTML="<div class='showcase-lock-card'><p class='showcase-kicker'>SHOWCASE STUDIO</p><h2>Ah ah ah, you didn’t say the magic word.</h2><p>This Studio session stays in <strong>"+escapeHTML(city)+"</strong> so its calendar, weather, maps, and sample household data remain consistent.</p><div class='showcase-actions'><button data-keep>Keep Exploring</button><button data-city>Choose Another City</button></div></div>";
    document.body.appendChild(modal);
    modal.querySelector("[data-keep]").onclick=()=>modal.remove();
    modal.querySelector("[data-city]").onclick=()=>returnHome().catch(error=>console.warn(error));
    modal.querySelector("[data-keep]").focus();
  }
  function escapeHTML(value){const box=document.createElement("div");box.textContent=String(value||"");return box.innerHTML;}
  window.showcaseStudioLocationLocked=locationModal;
  async function openOnly(open,target){
    await clearPrimarySurface();
    await Promise.resolve(open());
    for(let attempt=0;attempt<20;attempt++){
      if(document.querySelector(target))return;
      await wait(45);
    }
    console.warn("Showcase tour target did not become visible",target);
  }
  const steps=[
    {title:"Welcome to Dash-Go",text:"This is the real Dash-Go dashboard with safe, disposable data for "+city+".",open:async()=>{await clearPrimarySurface();await showListsPreview();}},
    {title:"Lists dock",text:"This scrolling strip keeps grocery and household tasks visible at a glance. It is off by default and can be enabled in Dashboard Control.",open:async()=>{await clearPrimarySurface();await showListsPreview();}},
    {title:"Weather awareness",text:"Dash-Go can surface important weather conditions. This is a clearly labeled sample alert, not live weather data.",open:async()=>{await clearPrimarySurface();await showListsPreview();addAlertPreview();}},
    {title:"Apps for the household",text:"Dash-Go keeps focused household tools one tap away.",open:()=>openOnly(()=>call("openAppLauncher"),"#applauncher.show")},
    {title:"Grocery",text:"This is the real local Grocery list, seeded for this Studio session.",open:()=>openOnly(()=>call("openListsApp","grocery"),"#listsapp.show")},
    {title:"Chore Wheel",text:"Try a fair rotation built around the fictional household.",open:()=>openOnly(()=>call("openChoreWheel"),"#chorewheel.show")},
    {title:"Routines",text:"Routines coordinate recurring household moments without leaving the dashboard.",open:()=>openOnly(()=>call("openRoutines"),"#routines.show")},
    {title:"Family Message Board",text:"Household notes and private inboxes stay together.",open:()=>openOnly(()=>call("openFamilyBoard"),"#familyboard.show")},
    {title:"Dashboard Control",text:"Explore themes and display choices. You can search locations, but Studio keeps this demo city locked so the scenario stays consistent.",open:()=>openOnly(()=>call("openDashboardControl"),"#ctrl.show")},
    {title:"Explore freely",text:"The tour is complete. The Lists preview and sample alert disappear now; any remaining changes last only for this Studio session.",open:async()=>{removeAlertPreview();hideListsPreview();await clearPrimarySurface();}}
  ];
  function render(){
    if(!active)return;removeCard();
    const step=steps[index];
    Promise.resolve(step.open()).catch(error=>console.warn("Showcase tour target could not open",error)).finally(()=>{
      if(!active)return;
      card=document.createElement("aside");card.id="showcase-tour";card.setAttribute("role","dialog");card.setAttribute("aria-live","polite");
      card.innerHTML="<button class='showcase-dismiss' data-dismiss aria-label='Close tour'>×</button><p class='showcase-kicker'>SHOWCASE TOUR "+(index+1)+" / "+steps.length+"</p><h2>"+escapeHTML(step.title)+"</h2><p>"+escapeHTML(step.text)+"</p><div class='showcase-actions'><button data-back>Back</button><button data-next>"+(index===steps.length-1?"Explore Freely":"Next")+"</button><button data-restart>Restart Tour</button><button data-skip>Skip Tour</button></div>";
      document.body.appendChild(card);
      card.querySelector("[data-back]").disabled=index===0;
      card.querySelector("[data-back]").onclick=()=>{index=Math.max(0,index-1);render();};
      card.querySelector("[data-next]").onclick=()=>{if(index===steps.length-1){finish().catch(error=>console.warn(error));return;}index++;render();};
      card.querySelector("[data-restart]").onclick=()=>restart().catch(error=>console.warn(error));
      card.querySelector("[data-skip]").onclick=()=>finish().catch(error=>console.warn(error));
      card.querySelector("[data-dismiss]").onclick=()=>finish().catch(error=>console.warn(error));
    });
  }
  window.addEventListener("pagehide",()=>{if(active){removeAlertPreview();hideListsPreview();}});
  document.addEventListener("keydown",event=>{if(event.key==="Escape"&&active&&card){event.preventDefault();finish().catch(error=>console.warn(error));}});
  if(active)window.setTimeout(render,650);
})();