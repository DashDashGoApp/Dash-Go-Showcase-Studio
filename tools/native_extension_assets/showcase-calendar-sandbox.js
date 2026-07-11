(function(){
  if(!window.DASHGO_SHOWCASE)return;
  function sourceFor(ev){return String(ev&&ev.cal&&ev.cal.url||ev&&ev.calUrl||"");}
  function nameFor(status,source){const found=(Array.isArray(status&&status.calendars)?status.calendars:[]).find(item=>item&&String(item.source||"")===source);return String(found&&found.name||"Studio calendar");}
  function sessionNote(){return el("p","calendar-writeback-note","Studio session only. Every edit resets when Studio closes.");}
  window.showcaseMoveCalendarEvent=function(ev,status){
    const source=sourceFor(ev),targets=calendarWritebackActiveCalendars(status).filter(item=>String(item&&item.source||"")!==source);
    popupOpenTransaction({mode:"showcasemove",title:"Move event",when:"Studio session calendar",loading:"Preparing calendar move…"},()=>{
      const root=el("section","calendar-writeback-recurring");root.append(sessionNote(),el("p","",`Move “${ev&&ev.title||"this event"}” from ${nameFor(status,source)} to:`));
      const actions=el("div","calendar-writeback-action-row");
      targets.forEach(target=>{const button=calendarWritebackButton("Move to "+String(target.name||"Studio calendar"),"primary",async node=>{node.disabled=true;try{const result=await calendarWritebackRequest("/api/calendar/event/move",{calUrl:source,targetCalUrl:String(target.source||""),uid:ev.uid});if(result.warning)calendarWritebackShowError(root,result.warning);await calendarWritebackRefresh();closeScrim();}catch(error){node.disabled=false;calendarWritebackShowError(root,error.message);}});actions.appendChild(button);});
      root.appendChild(actions);const back=el("div","calendar-writeback-form-actions");back.appendChild(calendarWritebackButton("Back to event","",()=>showEventPopup(ev)));root.appendChild(back);return root;
    });
  };
  window.showcaseDeleteCalendarSeries=function(ev){
    popupOpenTransaction({mode:"showcaseseriesdelete",title:"Delete entire series?",when:"Studio session calendar",loading:"Preparing series deletion…"},()=>{
      const root=el("section","calendar-writeback-recurring");root.append(sessionNote(),el("p","",`Delete every occurrence of “${ev&&ev.title||"this series"}” from this Studio session?`));
      const actions=el("div","calendar-writeback-action-row");actions.append(calendarWritebackButton("Keep series","",()=>showEventPopup(ev)),calendarWritebackButton("Delete entire series","danger",async node=>{node.disabled=true;try{const result=await calendarWritebackRequest("/api/calendar/event/series/delete",{calUrl:sourceFor(ev),uid:ev.uid});if(result.warning)calendarWritebackShowError(root,result.warning);await calendarWritebackRefresh();closeScrim();}catch(error){node.disabled=false;calendarWritebackShowError(root,error.message);}}));root.appendChild(actions);return root;
    });
  };
})();