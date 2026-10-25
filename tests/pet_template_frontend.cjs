// Actual Vue setup/watch behavior with isolated API doubles. No real providers.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const {pathToFileURL} = require('node:url')
const root = path.resolve(__dirname, '..')
const Vue = require(path.join(root, 'frontend/node_modules/vue'))
const {parse, compileScript} = require(path.join(root, 'frontend/node_modules/@vue/compiler-sfc'))
const renderer = Vue.createRenderer({createElement:()=>({}),createText:()=>({}),createComment:()=>({}),
  insert(){},remove(){},setText(){},setElementText(){},patchProp(){},parentNode:()=>null,nextSibling:()=>null})
function component(file, dependencies={}) {
  const {descriptor} = parse(fs.readFileSync(path.join(root,'frontend/src',file),'utf8'))
  let code = compileScript(descriptor,{id:file}).content
  code = code.replace(/^import\s+([\s\S]*?)\s+from\s+['"]([^'"]+)['"];?\s*$/gm,(_,bindings,source)=>{
    dependencies[source] ||= source==='vue'? Vue : {default:{render:()=>null}}
    const value=`__deps[${JSON.stringify(source)}]`
    return bindings.trim().startsWith('{') ? `const ${bindings.replace(/\bas\b/g,':')} = ${value};` : `const ${bindings.trim()} = ${value}.default;`
  })
  const result=new Function('__deps',code.replace('export default','return'))(dependencies)
  result.render=()=>null
  return result
}
function mount(type,props={}) {
  const reactiveProps=Vue.reactive(props)
  let vm
  const wrapper={setup:()=>()=>Vue.h(type,{...reactiveProps,ref:value=>{if(value)vm=value}})}
  const app=renderer.createApp(wrapper)
  app.mount({})
  return {s:vm.$.setupState,props:reactiveProps,unmount:()=>app.unmount()}
}
async function settle(){for(let i=0;i<32;i++)await Promise.resolve();await Vue.nextTick()}
const clone=o=>JSON.parse(JSON.stringify(o))
const aid='a'.repeat(32), preset_id='mhp-pet-heating-pad-ru-v1'
const preset={preset_id,name:'MHP 官方 · 宠物加热垫（俄语）',counts:[7,8,9],language:'ru',
  rules:['尺寸只在主图','不添加配件'],checklist:['八档调温？','防水阻燃？'],wishes:'宠物加热垫；主图少字大品名；尺寸只在主图；真实细节与场景；不添加配件。'}
const job={plan_id:'c'.repeat(32),status:'completed',created_at:'2026-10-25',
  request:{image_ids:[aid],language:'ru',count:7,preset_id,wishes:'温暖高级'},
  content:{product_name_zh:'宠物加热垫',brief_zh:'温暖高级，真实商品',notes_zh:['安全功能待核实'],
    pages:Array.from({length:7},(_,i)=>({asset_id:aid,kind:i?'feature':'main',
      title:{target:'КОВРИК ДЛЯ ПИТОМЦЕВ',zh:'宠物加热垫'},copy_lines:[],direction_zh:'真实外观',fact_keys:['seller_facts']}))}}
async function main(){
  global.crypto=require('node:crypto').webcrypto
  global.window={crypto,confirm:()=>true,addEventListener(){},removeEventListener(){},location:{origin:'https://offline.invalid'}}
  global.document={hidden:false,addEventListener(){},removeEventListener(){}}
  global.localStorage={getItem:()=> 'seen'}
  const calls=[],events=[]
  const request=async(url,method='GET',payload)=>{
    calls.push({url,method,payload:payload&&clone(payload)})
    if(url.endsWith('/capabilities'))return {configured:true,models:['chosen-model'],presets:[clone(preset)]}
    if(url.startsWith('/assets'))return {items:[{asset_id:aid,filename:'pad.png'}],total:1}
    if(url.startsWith('/mkhp')||(url==='/product-plans'&&method==='GET'))return {items:[]}
    if(method==='PUT')return {...clone(job),content:clone(payload.content)}
    return clone(job)
  }
  const a=mount(component('components/ptmd/ProductPlanAssistant.vue',{'../../api/client':{workspaceRequest:request,assetPreviewUrl:id=>id}}),
    {preset:{preset_id},count:1,language:'ru',onApply:v=>events.push(v)})
  await settle()
  assert.ok(calls.length>0&&calls.every(c=>c.method==='GET'),'Applying only reads; never submits a paid request')
  assert.equal(a.s.count,null,'7/8/9 must be chosen explicitly')
  assert.deepEqual(a.s.counts,[7,8,9])
  assert.equal(a.s.model,'');assert.equal(a.s.facts,'');assert.equal(a.s.importId,'')
  assert.equal(a.s.confirmed,false);assert.deepEqual(a.s.imageIds,[])
  assert.equal(a.s.wishes,preset.wishes)
  a.s.model='chosen-model';a.s.facts='宠物加热垫，30×35cm';a.s.selectImage(aid);a.s.confirmed=true
  a.s.count=6;await a.s.generate();assert.equal(calls.filter(c=>c.method==='POST').length,0)
  a.s.count=7;window.confirm=()=>false;await a.s.generate();assert.equal(calls.filter(c=>c.method==='POST').length,0)
  window.confirm=()=>true;await a.s.generate()
  const submitted=calls.find(c=>c.method==='POST')
  assert.equal(submitted.payload.preset_id,preset_id)
  assert.equal(submitted.payload.count,7)
  assert.ok(!JSON.stringify(submitted.payload).includes('八档'),'Unchecked claims must stay out of paid payload')
  assert.equal(a.s.checked,false);await a.s.apply();assert.equal(events.length,0)
  a.s.checked=true;await a.s.apply();assert.equal(events[0].request.preset_id,preset_id)
  assert.equal(calls.filter(c=>c.url.startsWith('/product-sets')).length,0)
  // Reapplying a template resets old product facts/consent, without another paid call.
  a.props.preset={preset_id};await settle()
  assert.equal(a.s.facts,'');assert.equal(a.s.confirmed,false);assert.equal(a.s.count,null)
  assert.equal(calls.filter(c=>c.method==='POST').length,1)
  a.unmount()

  const {createSetDraft}=await import(pathToFileURL(path.join(root,'frontend/src/ptmdDraft.js')))
  const {messages}=await import(pathToFileURL(path.join(root,'frontend/src/i18n/index.js')))
  const context={creditsChanged(){},locale:'zh',user:{user_id:'alice'}}
  let creates=0
  const client={workspaceRequest:async()=>({preferences:{resolution:'1200'}}),fetchAccount:async()=>({available:30}),
    fetchAssets:async()=>({items:[],total:0}),fetchGenerations:async()=>({items:[],total:0}),
    fetchSetCapabilities:async()=>({reference_editing:true}),fetchProductSets:async()=>({items:[]}),
    createProductSet:async()=>{creates++;throw Error('Unexpected paid request')},assetPreviewUrl:id=>id}
  const wb=mount(component('views/PTMDWorkbench.vue',{'../api/client':client,'../ptmdDraft':{createSetDraft},
    '../composables/useAppContext':{useAppContext:()=>context},'../i18n/membership':{membershipMessages:{zh:{},en:{}}},'../parameters':{parameterLabel:()=>''}}),{t:messages.zh})
  await settle()
  await wb.s.applyTemplate({workflow:'set',planner:{preset_id},spec:null,params:{language:'ru'}})
  assert.equal(wb.s.paramsOpen,true)
  assert.equal(wb.s.plannerPreset.preset_id,preset_id)
  assert.equal(wb.s.templateDraft.spec,null,'An empty official storyboard must not be saved as a one-page local preset')
  assert.equal(wb.s.templateDraft.planner.preset_id,preset_id)
  await wb.s.generateSet();assert.equal(creates,0)
  wb.s.applyAiPlan(clone(job))
  assert.equal(wb.s.setSpec.preset_id,preset_id);assert.equal(wb.s.setSpec.count,7)
  assert.equal(wb.s.setSpec.engine,'');assert.equal(wb.s.setSpec.text_rendering,null);assert.equal(wb.s.setSpec.image_quality,null)
  assert.equal(wb.s.setSpec.pages[0].title_zh,'宠物加热垫')
  await wb.s.generateSet();assert.equal(creates,0,'Production method requires selection')
  wb.s.setSpec.engine='reference';await wb.s.generateSet();assert.equal(creates,0,'Typography requires selection')
  wb.s.setSpec.text_rendering='model';await wb.s.generateSet();assert.equal(creates,0,'Quality requires selection')
  wb.s.setSpec.image_quality='low';window.confirm=()=>false;await wb.s.generateSet();assert.equal(creates,0,'Fee consent remains separate')
  assert.equal(wb.s.templateDraft.spec.preset_id,preset_id)
  assert.equal(createSetDraft(wb.s.templateDraft.spec).preset_id,preset_id,'Saved drafts retain canonical rule identity')
  wb.unmount()

  const panel=mount(component('components/ptmd/ProductSetPanel.vue',{'../../api/client':{assetPreviewUrl:id=>id}}),
    {modelValue:createSetDraft(),preset:{preset_id}})
  assert.equal(panel.s.needsPlan,true)
  panel.props.modelValue={...createSetDraft(),preset_id}
  await settle();assert.equal(panel.s.needsPlan,false);assert.deepEqual(panel.s.counts,[7,8,9])
  panel.unmount()
  console.log(JSON.stringify({official_template_scenarios:5,real_network_calls:0,rendered_browser:false}))
}
main().catch(error=>{console.error(error);process.exitCode=1})
