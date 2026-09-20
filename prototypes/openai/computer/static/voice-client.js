'use strict';
// Session-scoped room token remains in memory. No credentials in URLs or storage.
let computerRoom=null;
window.addEventListener('DOMContentLoaded',()=>{
 const action=(id,fn)=>document.getElementById(id).addEventListener('click',async()=>{try{await fn();}catch(error){document.getElementById('notice').textContent='Audio: '+error.message;}});
 async function request(path){const r=await fetch('/api/voice/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!r.ok)throw Error('Audio nicht verfügbar. Lokale Modelle und LiveKit-Konfiguration prüfen.');return r.json();}
 action('voice-connect',async()=>{
  if(computerRoom)return;
  const connection=await request('connect');
  const room=new LivekitClient.Room();computerRoom=room;
  room.on(LivekitClient.RoomEvent.TrackSubscribed,track=>{if(track.kind==='audio'){const audio=track.attach();audio.dataset.computerAudio='true';document.body.append(audio);}});
  room.on(LivekitClient.RoomEvent.TrackUnsubscribed,track=>track.detach().forEach(el=>el.remove()));
  try{await room.connect(connection.url,connection.token);await room.localParticipant.setMicrophoneEnabled(true,{echoCancellation:true,noiseSuppression:true,autoGainControl:true});}
  catch(error){await room.disconnect();computerRoom=null;await request('disconnect');throw error;}
 });
 action('voice-wake',()=>request('wake'));
 action('voice-disconnect',async()=>{if(computerRoom)await computerRoom.disconnect();computerRoom=null;document.querySelectorAll('[data-computer-audio]').forEach(el=>el.remove());await request('disconnect');});
 document.getElementById('stop').addEventListener('click',()=>{document.querySelectorAll('[data-computer-audio]').forEach(el=>{el.pause();el.srcObject=null;});if(computerRoom){computerRoom.disconnect();computerRoom=null;}request('disconnect').catch(()=>{});});
});
