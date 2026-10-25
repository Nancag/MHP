/* Self-contained function injected only after a user click. No cookies, fetch or credentials. */
function mhpExtractProduct() {
  const here=new URL(location.href),host=here.hostname;
  const taobao=host==='item.taobao.com'||host==='detail.tmall.com';
  const pdd=host==='mobile.yangkeduo.com'||host==='mobile.pinduoduo.com';
  const id=here.searchParams.get(taobao?'id':'goods_id');
  if(!(taobao||pdd)||!id||!/^\d+$/.test(id))throw new Error('请打开淘宝/天猫商品详情页或含 goods_id 的拼多多商品详情页；暂不支持短链接和其它页面。');
  const source=new URL(here.origin+here.pathname);source.searchParams.set(taobao?'id':'goods_id',id);
  const fields={},images=[];
  const scalar=v=>{
    if(v&&typeof v==='object'&&!Array.isArray(v)&&['string','number'].includes(typeof v.value))return scalar(`${v.value} ${v.unitText||v.unitCode||''}`);
    return typeof v==='string'||typeof v==='number'?String(v).replace(/\s+/g,' ').trim().slice(0,2000):'';
  };
  const put=(key,value,evidence)=>{value=scalar(value);if(value&&!fields[key])fields[key]={value,evidence,source_url:source.href}};
  const visible=node=>node&&node.getClientRects().length>0;
  const meta=name=>document.querySelector(`meta[property="${name}"],meta[name="${name}"]`)?.content||'';
  const addImage=value=>{
    if(typeof value!=='string')return;
    try{const u=new URL(value,here);if(u.protocol!=='https:')return;
      if(!/(^|\.)(alicdn\.com|taobaocdn\.com|pddpic\.com|yangkeduo\.com)$/.test(u.hostname))return;
      u.hash='';if(!images.includes(u.href)&&images.length<100)images.push(u.href);
    }catch{}
  };
  let product=null;
  function find(v,depth=0){if(depth>15||!v||typeof v!=='object')return;
    if([v['@type']].flat().some(type=>typeof type==='string'&&type.split('/').pop()==='Product')){product=product||v;return}
    for(const child of Object.values(v))if(child&&typeof child==='object')find(child,depth+1);
  }
  for(const node of document.querySelectorAll('script[type="application/ld+json"]')){
    if(node.textContent.length>500000)continue;try{find(JSON.parse(node.textContent))}catch{}
  }
  // A visible variant price takes priority over a generic structured offer.
  const visiblePrice=document.querySelector('[class*="Price--priceText"],[class*="priceText"],[class*="goods-price"]');
  if(visible(visiblePrice))put('price',visiblePrice.innerText,'当前页面显示价格（需核对规格和优惠）');
  const aliases={'材质':'material','材料':'material','商品尺寸':'size','产品尺寸':'size','包装尺寸':'package_size','包裹尺寸':'package_size',
    'material':'material','product dimensions':'size','item dimensions':'size','package dimensions':'package_size','packaging dimensions':'package_size'};
  if(product){
    for(const key of ['name','description','material','size','width','height','depth','weight'])put(key,product[key],'商品页 JSON-LD Product');
    const offer=[product.offers].flat().find(v=>v&&typeof v==='object')||{};
    put('price',offer.price??offer.lowPrice,'JSON-LD 报价（需核对所选规格）');put('currency',offer.priceCurrency,'JSON-LD 币种');
    put('price_max',offer.highPrice,'JSON-LD 最高报价（需核对所选规格）');
    for(const prop of [product.additionalProperty].flat()){
      if(!prop||typeof prop!=='object')continue;
      const key=aliases[scalar(prop.name).toLowerCase()];
      if(key)put(key,prop.value,'JSON-LD 商品参数：'+scalar(prop.name));
    }
    for(const image of [product.image].flat())addImage(typeof image==='object'?image?.url||image?.contentUrl:image);
  }
  put('name',meta('og:title'),'商品页 og:title');put('price',meta('product:price:amount'),'商品页价格 meta');put('currency',meta('product:price:currency'),'商品页币种 meta');addImage(meta('og:image'));
  const title=document.querySelector('h1,[class*="mainTitle"],[class*="MainTitle"],[class*="goodsName"],[class*="goods-name"]');
  if(visible(title))put('name',title.innerText,'页面商品标题（需核对）');
  if(!/登录|验证|访问受限/.test(document.title))put('name',document.title.replace(/[-_｜|]\s*(淘宝网?|天猫|拼多多).*$/,''),'浏览器标题（需核对）');
  for(const node of [...document.querySelectorAll('tr,dl,[class*="attribute"],[class*="Attribute"],[class*="propItem"],[class*="param-item"]')].slice(0,500)){
    if(!visible(node))continue;
    const text=(node.innerText||'').trim();if(text.length>250)continue;
    for(const [label,key] of Object.entries(aliases)){
      const match=text.match(new RegExp('^'+label+'\\s*[:：|\\n]\\s*([\\s\\S]{1,180})$','i'));
      if(match)put(key,match[1],'页面参数：'+text.replace(/\s+/g,' '));
    }
  }
  for(const node of document.images){
    if(!visible(node)||Math.max(node.naturalWidth,node.width)<150||Math.max(node.naturalHeight,node.height)<150)continue;
    addImage(node.currentSrc||node.src||node.getAttribute('data-src'));
  }
  if(!fields.name||/^(淘宝网?|天猫|拼多多)$/.test(fields.name.value))throw new Error('未识别到可确认的商品标题，请完成登录或验证，等待商品加载后再采集。');
  return {version:1,source_url:source.href,fields,image_urls:images,warnings:['浏览器候选结果需要人工核对；图片可能包含推荐商品或促销素材。','未显示的商品尺寸、包裹尺寸和材质不会推测；价格需核对规格与优惠。']};
}
if(typeof module!=='undefined')module.exports={mhpExtractProduct};
