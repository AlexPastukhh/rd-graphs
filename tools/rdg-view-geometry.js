/* Common camera and target-label geometry for R graphs and graph sets. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.RDGViewGeometry=api;})(globalThis,function(){
  'use strict';
  const clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
  function wheelView(view,event,point,size){
    const factor=event.deltaMode===1?16:event.deltaMode===2?size.height:1;
    const dx=(Number(event.deltaX)||0)*(event.deltaMode===2?size.width:factor),dy=(Number(event.deltaY)||0)*factor;
    if(event.ctrlKey){
      const delta=dy||dx;if(!delta)return {...view};
      const scale=clamp(view.scale*Math.exp(-clamp(delta,-600,600)*.0015),.07,3);
      return {x:point.x-(point.x-view.x)*scale/view.scale,y:point.y-(point.y-view.y)*scale/view.scale,scale};
    }
    return {...view,x:view.x-(event.shiftKey?(dx||dy):dx),y:view.y-(event.shiftKey?0:dy)};
  }
  const hit=(a,b,pad=6)=>a.x<b.x+b.w+pad&&a.x+a.w+pad>b.x&&a.y<b.y+b.h+pad&&a.y+a.h+pad>b.y;
  function placeTargetLabel({target,endpoint,width,height,nodeBoxes,labels,otherRoutes=[]}){
    const center={x:target.x+target.w/2,y:target.y+target.h/2};
    const distance=box=>Math.hypot(Math.max(box.x-endpoint.x,endpoint.x-box.x-box.w,0),Math.max(box.y-endpoint.y,endpoint.y-box.y-box.h,0));
    const crosses=box=>otherRoutes.reduce((n,ps)=>n+ps.slice(1).filter((p,i)=>{
      const a=ps[i];return a[0]===p[0]?a[0]>box.x&&a[0]<box.x+box.w&&Math.max(a[1],p[1])>box.y&&Math.min(a[1],p[1])<box.y+box.h:
        a[1]>box.y&&a[1]<box.y+box.h&&Math.max(a[0],p[0])>box.x&&Math.min(a[0],p[0])<box.x+box.w;
    }).length,0);
    const nearby=[];
    for(let ring=0;ring<=14;ring++){
      const candidates=[],step=height+8;
      for(const shift of ring?[ring*step,-ring*step]:[0]){
        candidates.push({x:target.x-width-12,y:endpoint.y-height/2+shift,w:width,h:height},
          {x:target.x+target.w+12,y:endpoint.y-height/2+shift,w:width,h:height},
          {x:center.x-width/2+shift,y:target.y-height-12,w:width,h:height},
          {x:center.x-width/2+shift,y:target.y+target.h+12,w:width,h:height});
      }
      const valid=candidates.filter(b=>!nodeBoxes.some(n=>hit(b,n))&&!labels.some(l=>hit(b,l)));
      for(const b of valid)nearby.push({...b,crowded:ring>5,score:distance(b)+crosses(b)*90+ring*2});
      if(ring>=5&&nearby.length){nearby.sort((a,b)=>a.score-b.score);return nearby[0];}
    }
    // Only physically packed/overlapping user layouts reach this local fallback.
    // Expand around the target, never use a shared gutter at the source.
    for(let ring=1;;ring++){
      const step=height+8;
      for(let i=-ring;i<=ring;i++)for(const [x,y] of [[i,-ring],[i,ring],[-ring,i],[ring,i]]){
        const b={x:center.x+x*(width+12)-width/2,y:center.y+y*step-height/2,w:width,h:height};
        if(!nodeBoxes.some(n=>hit(b,n))&&!labels.some(l=>hit(b,l)))return {...b,crowded:true};
      }
    }
  }
  return Object.freeze({wheelView,placeTargetLabel});
});
