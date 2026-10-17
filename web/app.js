(() => {
  'use strict';
  const BUILD = '1.0.0';
  function init() {
  const iconPaths = {
    merge: '<path d="M8 3h8l4 4v13a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"/><path d="M16 3v5h4M4 7v13M11 13h6m-3-3v6"/>',
    split: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M12 4v16M7 11h2m6 0h2"/>',
    extract: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6m-6 4h6m-3 3v5"/>',
    remove: '<path d="M6 3h9l4 4v14H6zM15 3v5h4"/><path d="M9 15h7"/>',
    rotate: '<path d="M3 11a9 9 0 0 1 15-6l2 2M20 3v4h-4"/><path d="M21 13a9 9 0 0 1-15 6l-2-2m0 4v-4h4"/>',
    compress: '<path d="M8 3H5v3M16 3h3v3M8 21H5v-3m11 3h3v-3M9 9l3 3 3-3M12 12v5"/>',
    word: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8l2 8 2-5 2 5 2-8"/>',
    office: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M9 8h6m-6 4h6m-6 4h4"/>',
    pdfimage: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8" cy="9" r="1.5"/><path d="m4 18 6-6 4 4 3-3 4 4"/>',
    imagepdf: '<rect x="5" y="4" width="14" height="16" rx="2"/><path d="m6 17 4-4 3 3 3-3 3 4"/><circle cx="10" cy="9" r="1.5"/>',
    excel: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M4 9h16M10 9v12M4 15h16"/>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m4 19 6-6 4 4 3-3 4 4"/>',
  };
  const svgIcon = key => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[key]}</svg>`;
  const formats = {
    pdf: { accept: '.pdf', exts: ['pdf'], hint: '支持 PDF 文件' },
    image: { accept: '.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff,.gif', exts: ['png','jpg','jpeg','webp','bmp','tif','tiff','gif'], hint: 'JPG、PNG、WebP、BMP、TIFF、GIF' },
    excel: { accept: '.xls,.xlsx,.csv', exts: ['xls','xlsx','csv'], hint: 'XLS、XLSX、CSV' },
    office: { accept: '.doc,.docx,.odt,.rtf,.ods,.ppt,.pptx,.odp', exts: ['doc','docx','odt','rtf','ods','ppt','pptx','odp'], hint: 'Word、PPT、ODT 等' },
  };
  const tasks = [
    { id:'pdf_merge', name:'PDF 合并', group:'pdf', icon:'merge', kind:'pdf', multi:true, min:2,
      desc:'将多个 PDF 按顺序合并为一份完整文件。', tip:'合并前调整文件顺序，输出的 PDF 就会按这个顺序排列。', action:'合并 PDF' },
    { id:'pdf_split', name:'PDF 拆分', group:'pdf', icon:'split', kind:'pdf', multi:false,
      desc:'将一份 PDF 按页面拆分成多个独立文件。', tip:'拆分后的页面将自动打包成 ZIP，方便一次保存。', action:'拆分 PDF' },
    { id:'pdf_extract', name:'提取页面', group:'pdf', icon:'extract', kind:'pdf', multi:false,
      desc:'按需要提取指定页码，生成一份新的 PDF。', tip:'例如输入 1-3,5,8，表示提取第 1、2、3、5、8 页。', action:'提取页面', fields:[
        { key:'pages', type:'text', label:'提取页码', placeholder:'例如：1-3,5,8', help:'使用逗号分隔，短横线代表连续页码。' }] },
    { id:'pdf_remove', name:'删除页面', group:'pdf', icon:'remove', kind:'pdf', multi:false,
      desc:'从 PDF 中移除不需要的页面，保留其他内容。', tip:'原文件始终不会被改写，系统只会生成一个新的 PDF。', action:'删除页面', fields:[
        { key:'pages', type:'text', label:'要删除的页码', placeholder:'例如：2,4-6', help:'最多不能删除所有页面。' }] },
    { id:'pdf_rotate', name:'旋转页面', group:'pdf', icon:'rotate', kind:'pdf', multi:false,
      desc:'顺时针旋转整份 PDF 或其中某些页面。', tip:'页码留空表示旋转所有页面；旋转后会生成新文件。', action:'旋转 PDF', fields:[
        { key:'angle', type:'select', label:'顺时针旋转', choices:[['90','90°'],['180','180°'],['270','270°']] },
        { key:'pages', type:'text', label:'指定页码（可留空）', placeholder:'默认：所有页面', help:'例如 1-2,5；留空则旋转全部页面。' }] },
    { id:'pdf_compress', name:'PDF 优化压缩', group:'pdf', icon:'compress', kind:'pdf', multi:false,
      desc:'精简 PDF 体积；提供无损优化和更小文件两种方式。', tip:'无损优化不一定能显著缩小文件；高压缩可能降低图片画质。', action:'压缩 PDF', fields:[
        { key:'mode', type:'select', label:'压缩模式', choices:[['lossless','无损优化（推荐）'],['smaller','更小文件（需 Ghostscript）']], help:'如果压缩结果反而变大，将返回原文件内容。' }] },
    { id:'pdf_to_word', name:'PDF 转 Word', group:'convert', icon:'word', kind:'pdf', multi:false,
      desc:'智能识别表格并重建可编辑 Word。', tip:'PDF 是固定版式，部分复杂表格可能需要人工调整；扫描件暂不支持 OCR。', action:'转换为 Word', fields:[
        { key:'mode', type:'select', label:'转换方式', choices:[['structured','智能表格（推荐，可编辑）'],['text','纯文本（仅保留文字）'],['visual','按页面图片（不可编辑）']], help:'有表格优先选智能表格；扫描件可使用图片模式。' }] },
    { id:'excel_to_word', name:'表格 → 可编辑 Word', group:'convert', icon:'excel', kind:'excel', multi:true,
      desc:'直接读取 Excel 单元格，生成排版清晰、可编辑的 Word 表格。', tip:'智能重排，不是原始 Excel 外观的逐像素复制；所有非空字段保留在主表或来源附录。', action:'生成可编辑 Word' },
    { id:'excel_smart_pdf', name:'表格 → 智能排版 PDF', group:'convert', icon:'excel', kind:'excel', multi:true,
      desc:'使用与 Word 相同的清晰版式输出 PDF，中文与表格结构更适合阅读。', tip:'直接从 Excel 生成。旧版 .xls 需要 LibreOffice 读取。', action:'生成清晰 PDF' },
    { id:'table_to_csv', name:'导出 CSV', group:'convert', icon:'excel', kind:'excel', multi:true,
      desc:'导出 UTF-8 CSV，保留原始行号与数据列。', tip:'含多张工作表时将生成多个 CSV 并自动打包。', action:'导出 CSV' },
    { id:'office_to_pdf', name:'Office 转 PDF', group:'convert', icon:'office', kind:'office', multi:true,
      desc:'Word 优先生成中文清晰、可搜索的 PDF。', tip:'清晰排版适合表格和中文；如需精确保留复杂原版式可选兼容模式。', action:'转换为 PDF', fields:[{ key:'mode', type:'select', label:'Word 转换方式', choices:[['readable','清晰排版（推荐）'],['original','尽量保留原版式（LibreOffice）']], help:'清晰排版会调整部分间距和分页；Excel、PPT 仍由 LibreOffice 处理。' }]  },
    { id:'pdf_to_images', name:'PDF 转图片', group:'convert', icon:'pdfimage', kind:'pdf', multi:false,
      desc:'将 PDF 的每一页导出为清晰的 PNG 或 JPG 图片。', tip:'如果是公众号插图或展示素材，150 DPI 通常足够。', action:'导出图片', fields:[
        { key:'format', type:'select', label:'图片格式', choices:[['png','PNG · 清晰无损'],['jpg','JPG · 体积更小']] },
        { key:'dpi', type:'select', label:'导出分辨率', choices:[['96','96 DPI · 较小'],['150','150 DPI · 标准'],['200','200 DPI · 高清']], default:'150' }] },
    { id:'images_to_pdf', name:'图片合成 PDF', group:'convert', icon:'imagepdf', kind:'image', multi:true,
      desc:'将一张或多张图片按顺序整理到同一份 PDF。', tip:'透明图片会在白色背景上合成，避免导出时出现黑底。', action:'合成 PDF' },
    { id:'image_convert', name:'图片格式转换', group:'image', icon:'image', kind:'image', multi:true,
      desc:'批量转换 JPG、PNG、WebP，并可顺便调整尺寸与质量。', tip:'JPG 不支持透明背景；透明部分会自动转为白色。GIF 仅处理首帧。', action:'转换图片', fields:[
        { key:'format', type:'select', label:'目标格式', choices:[['png','PNG'],['jpg','JPG'],['webp','WebP']] },
        { key:'quality', type:'select', label:'输出质量（JPG / WebP）', choices:[['100','100 · 最高质量'],['90','90 · 高清'],['85','85 · 均衡'],['70','70 · 更小文件'],['50','50 · 高压缩']], default:'85' },
        { key:'max_side', type:'select', label:'限制最长边', choices:[['0','保持原始尺寸'],['1280','1280 px'],['1920','1920 px'],['2560','2560 px']] }] },
  ];
  const groupMeta = {
    pdf: { title:'PDF', singular:'PDF', icon:'merge' },
    image: { title:'图片', singular:'图片', icon:'image' },
    excel: { title:'表格文件', singular:'Excel / CSV', icon:'excel' },
    office: { title:'Office', singular:'Office 文件', icon:'office' },
  };
  // A stale HTML page can be paired with a newly cached script. Make that failure
  // visible instead of letting one missing node disable the whole application.
  function incompatiblePage(reason) {
    console.error('[FileDesk] 页面资源不匹配：' + reason);
    const notice = document.createElement('div');
    notice.id = 'filedesk-startup-error';
    notice.setAttribute('role', 'alert');
    Object.assign(notice.style, {position:'fixed', zIndex:'99999', inset:'0', display:'flex',
      alignItems:'center', justifyContent:'center', padding:'24px', background:'#f8faf8',
      color:'#26392d', fontFamily:'-apple-system,BlinkMacSystemFont,sans-serif'});
    const card = document.createElement('div');
    Object.assign(card.style, {maxWidth:'540px',padding:'32px',border:'1px solid #e1e9e3',
      borderRadius:'16px',background:'white'});
    const title = document.createElement('h2');
    title.textContent = '页面资源未正确加载';
    title.style.margin = '0 0 12px';
    const description = document.createElement('p');
    description.textContent = '文序的网页和脚本版本不一致，或有部分页面元素缺失。请刷新网页；如果仍出现此提示，退出旧版服务并重新运行新版 start-mac.command。';
    description.style.lineHeight = '1.8';
    const detail = document.createElement('small');
    detail.textContent = '诊断：' + reason;
    detail.style.color = '#65756b';
    const reload = document.createElement('button');
    reload.textContent = '重新加载页面';
    Object.assign(reload.style,{display:'block',marginTop:'20px',padding:'10px 18px',background:'#305b44',
      color:'white',border:'0',borderRadius:'8px',cursor:'pointer'});
    reload.addEventListener('click', () => window.location.reload());
    card.append(title, description, detail, reload);
    notice.append(card);
    document.body.append(notice);
  }
  const pageBuild = document.querySelector('meta[name="filedesk-build"]')?.content;
  if (pageBuild !== BUILD) {
    incompatiblePage(`页面版本 ${pageBuild || '未知'}，脚本版本 ${BUILD}`);
    return;
  }
  // Only the history backdrop is optional and can be recreated safely.
  // Other missing nodes indicate an incompatible page and require a reload.
  if (!document.getElementById('history-backdrop')) {
    const backdrop = document.createElement('div');
    backdrop.id = 'history-backdrop';
    backdrop.className = 'history-backdrop';
    backdrop.hidden = true;
    document.body.append(backdrop);
  }
  const refs = Object.fromEntries([
    'empty-view','loaded-view','file-input','welcome-drop','add-inline','reset-all',
    'workspace-title','workspace-subtitle','total-count','group-tabs','file-list','file-summary',
    'file-hint','recommend-title','recommend-subtitle','operation-list','chosen-icon','chosen-name',
    'selection-summary','chosen-desc','single-file-pick','option-fields','execution-note',
    'execute','execute-label','cancel-job','inline-error','result-bar','drag-overlay','toast','history-toggle','history-close',
    'history-backdrop','history-panel','history-list','history-clear',
    'preview-backdrop','preview-modal','preview-close','preview-done','preview-title','preview-subtitle','preview-files',
    'preview-stage','preview-pages','preview-prev','preview-next','preview-page-label','preview-thumbs','success-banner','success-filename','redownload','success-dismiss',
  ].map(id => [id,document.getElementById(id)]));
  const missing = Object.entries(refs).filter(([, element]) => !element).map(([id]) => id);
  if (missing.length) {
    incompatiblePage('缺失页面元素：' + missing.join(', '));
    return;
  }
  let files=[];
  let activeKind=null;
  let operation=null;
  let singleFileId=null;
  let busy=false;
  let expanded=false;
  let lastResult=null;
  let recentDownload=null;
  let activeJobId=null;
  let uploadController=null;
  let cancelPending=false;
  let history=[];
  let nextFileId=0;
  let toastTimer;
  let dragDepth=0;
  let previewOpen=false;
  let previewSelected=null;
  let previewPage=0;
  let previewEpoch=0;
  let previewSelectionEpoch=0;
  const previewSessions=new Map();
  let previewBlobUrl=null;
  let previewReturnFocus=null;

  const el = (tag, className, content) => {
    const node=document.createElement(tag);
    if(className)node.className=className;
    if(content!==undefined)node.textContent=content;
    return node;
  };
  const icon = (key) => `<svg viewBox="0 0 24 24" aria-hidden="true">${iconPaths[key]||iconPaths.office}</svg>`;
  function showToast(message, isError=false){
    clearTimeout(toastTimer);
    refs.toast.textContent=message;
    refs.toast.className='toast'+(isError?' error':'');
    refs.toast.hidden=false;
    toastTimer=setTimeout(()=>{refs.toast.hidden=true},5500);
  }
  function bytes(n){if(n<1024)return `${n} B`;if(n<1048576)return `${(n/1024).toFixed(1)} KB`;return `${(n/1048576).toFixed(1)} MB`}
  function typeOf(file){
    const suffix=(file.name.split('.').pop()||'').toLowerCase();
    return Object.keys(formats).find(kind=>formats[kind].exts.includes(suffix))||null;
  }
  function grouped(kind=activeKind){return files.filter(item=>item.kind===kind)}
  function preferredKind(){
    const counts=Object.keys(formats).map(kind=>({kind,n:grouped(kind).length}));
    counts.sort((a,b)=>b.n-a.n || ['pdf','excel','image','office'].indexOf(a.kind)-['pdf','excel','image','office'].indexOf(b.kind));
    return counts.find(item=>item.n>0)?.kind||null;
  }
  function recommended(kind=activeKind){
    const count=grouped(kind).length;
    if(kind==='pdf')return count>1
      ? ['pdf_merge','pdf_to_word','pdf_split','pdf_extract','pdf_compress','pdf_rotate','pdf_remove','pdf_to_images']
      : ['pdf_to_word','pdf_split','pdf_extract','pdf_compress','pdf_to_images','pdf_rotate','pdf_remove'];
    if(kind==='image')return count>1?['images_to_pdf','image_convert']:['image_convert','images_to_pdf'];
    if(kind==='excel')return ['excel_to_word','excel_smart_pdf','table_to_csv'];
    if(kind==='office')return ['office_to_pdf'];
    return [];
  }
  function availableOperations(){return recommended().map(id=>tasks.find(t=>t.id===id)).filter(Boolean)}
  function selectedTask(){return tasks.find(t=>t.id===operation)||null}
  function reconcile(){
    if(!files.length){activeKind=null;operation=null;singleFileId=null;return;}
    if(!activeKind || !grouped(activeKind).length){activeKind=preferredKind();expanded=false;operation=null;}
    const available=recommended();
    if(!available.includes(operation)){operation=available[0]||null;expanded=false;}
    if(!grouped().some(item=>item.id===singleFileId))singleFileId=grouped()[0]?.id??null;
  }
  function addFiles(list){
    if(busy)return;
    if(previewOpen)closePreview();
    refs['inline-error'].hidden=true;
    const added=Array.from(list||[]);
    if(!added.length)return;
    refs['success-banner'].hidden=true;
    const candidates=[];
    let unsupported=0, large=0, duplicates=0;
    const seen=new Set(files.map(item=>item.file.name+'~'+item.file.size+'~'+item.file.lastModified));
    for(const file of added){
      const kind=typeOf(file);
      if(!kind){unsupported++;continue;}
      if(file.size>65*1024*1024||!file.size){large++;continue;}
      const identity=file.name+'~'+file.size+'~'+file.lastModified;
      if(seen.has(identity)){duplicates++;continue;}
      seen.add(identity);
      candidates.push({file,kind,id:++nextFileId});
    }
    if(files.length+candidates.length>35){showToast('每批最多 35 个文件，请先处理当前文件。',true);return;}
    if(files.reduce((n,item)=>n+item.file.size,0)+candidates.reduce((n,item)=>n+item.file.size,0)>200*1024*1024){showToast('当前批次总量不能超过 200 MB。',true);return;}
    const wasEmpty=files.length===0;
    files.push(...candidates);
    if(candidates.length){
      if(wasEmpty){activeKind=preferredKind();operation=null;}
      else if(!candidates.some(item=>item.kind===activeKind)){
        activeKind=candidates[0].kind;operation=null;expanded=false;
      }
      lastResult=null;
      reconcile();render();
    }
    if(unsupported||large||duplicates){
      const reasons=[];
      if(unsupported)reasons.push(`${unsupported} 个格式暂不支持`);
      if(large)reasons.push(`${large} 个文件为空或超过 65 MB`);
      if(duplicates)reasons.push(`${duplicates} 个重复文件已跳过`);
      showToast(reasons.join('；'),unsupported>0||large>0);
    }
  }
  function removeFile(id){
    if(busy)return;
    files=files.filter(item=>item.id!==id);
    lastResult=null;reconcile();render();
  }
  function moveFile(id,direction){
    if(busy)return;
    const current=files.findIndex(item=>item.id===id);
    const peers=files.map((item,i)=>item.kind===activeKind?i:-1).filter(i=>i>=0);
    const idx=peers.indexOf(current);
    const next=peers[idx+direction];
    if(next===undefined)return;
    [files[current],files[next]]=[files[next],files[current]];
    lastResult=null;render();
  }
  function chooseKind(kind){
    if(busy||kind===activeKind)return;
    activeKind=kind;operation=null;singleFileId=null;expanded=false;lastResult=null;
    reconcile();render();
  }
  function chooseOperation(id){
    if(busy)return;
    if(!recommended().includes(id))return;
    operation=id;lastResult=null;refs['inline-error'].hidden=true;render();
  }
  function render(){
    reconcile();
    refs['empty-view'].hidden=files.length>0;
    refs['loaded-view'].hidden=files.length===0;
    refs['add-inline'].disabled=busy;
    refs['reset-all'].disabled=busy;
    if(!files.length)return;
    const activeFiles=grouped();
    const allGroups=Object.keys(groupMeta).filter(kind=>grouped(kind).length);
    const count=activeFiles.length;
    const group=groupMeta[activeKind];
    refs['workspace-title'].textContent=allGroups.length>1?`${files.length} 个文件`:count>1?`${count} 份${group.title}`:(activeKind==='pdf'?'PDF 文件':group.title);
    refs['workspace-subtitle'].textContent='';
    refs['total-count'].textContent=files.length;
    renderGroups(allGroups);
    renderFileList(activeFiles);
    renderRecommendations();
    renderExecution();
  }
  function renderGroups(groups){
    refs['group-tabs'].replaceChildren();
    refs['group-tabs'].hidden=groups.length<=1;
    for(const kind of groups){
      const btn=el('button','group-tab'+(activeKind===kind?' active':''),`${groupMeta[kind].title}  ${grouped(kind).length}`);
      btn.type='button';btn.setAttribute('role','tab');btn.setAttribute('aria-selected',kind===activeKind?'true':'false');
      btn.disabled=busy;btn.addEventListener('click',()=>chooseKind(kind));refs['group-tabs'].append(btn);
    }
  }
  function renderFileList(activeFiles){
    const task=selectedTask();
    const multiple=!!task?.multi;
    refs['file-list'].replaceChildren();
    activeFiles.forEach((item,index)=>{
      const row=el('div','file-row'+(!multiple&&activeFiles.length>1&&item.id===singleFileId?' selected':''));
      const iconBox=el('div','file-icon'+(item.kind==='image'?' image':(item.kind==='office'||item.kind==='excel')?' office':''));
      iconBox.innerHTML=icon(item.kind==='pdf'?'merge':item.kind==='image'?'image':item.kind==='excel'?'excel':'office');
      const info=el('div','file-detail');
      const name=el('div','file-name',item.file.name);name.title=item.file.name;
      const extension=(item.file.name.split('.').pop()||'').toUpperCase();
      info.append(name,el('div','file-meta',`${extension}  ·  ${bytes(item.file.size)}`));
      const controls=el('div','row-actions');
      if(item.kind==='pdf' || (item.kind==='image' && !/\.(tif|tiff)$/i.test(item.file.name))){
        const peek=el('button','preview-open','预览');
        peek.type='button';peek.disabled=busy;peek.setAttribute('aria-label','预览 '+item.file.name);
        peek.addEventListener('click',()=>openPreview(item.id));controls.append(peek);
      }
      if(!multiple&&activeFiles.length>1){
        const select=el('button','select-file',item.id===singleFileId?'当前':'选取');select.disabled=busy;select.type='button';
        select.setAttribute('aria-label','选择处理文件 '+item.file.name);
        select.addEventListener('click',()=>{singleFileId=item.id;lastResult=null;render()});controls.append(select);
      }
      if(multiple&&activeFiles.length>1){
        for(const [direction,title,character] of [[-1,'上移','↑'],[1,'下移','↓']]){
          const control=el('button','row-control',character);control.type='button';control.title=title;
          control.setAttribute('aria-label',item.file.name+' '+title);
          control.disabled=busy||(direction<0?index===0:index===activeFiles.length-1);
          control.addEventListener('click',()=>moveFile(item.id,direction));controls.append(control);
        }
      }
      const remove=el('button','row-control','×');remove.type='button';remove.title='移除文件';
      remove.setAttribute('aria-label','移除 '+item.file.name);remove.disabled=busy;
      remove.addEventListener('click',()=>removeFile(item.id));controls.append(remove);
      row.append(iconBox,info,controls);refs['file-list'].append(row);
    });
    refs['file-summary'].textContent='';
    refs['file-hint'].textContent=files.length>activeFiles.length?`另外 ${files.length-activeFiles.length} 个文件仍保留在工作台`:multiple&&activeFiles.length>1?'可通过箭头调整处理顺序':'';
  }
  function renderRecommendations(){
    const items=availableOperations();
    const n=grouped().length;
    const isStrong=(activeKind==='pdf'&&n>1)||(activeKind==='image'&&n>1)||activeKind==='excel'||activeKind==='office';
    refs['recommend-title'].textContent='处理方式';
    refs['recommend-subtitle'].textContent='';
    refs['operation-list'].replaceChildren();
    const shown=expanded?items:items.slice(0,4);
    for(const task of shown){
      const choice=el('button','operation-item'+(task.id===operation?' active':''));choice.type='button';choice.disabled=busy;
      choice.setAttribute('aria-pressed',task.id===operation?'true':'false');
      const symbol=el('div','operation-icon');symbol.innerHTML=icon(task.icon);
      const text=el('div','operation-text');text.append(el('strong','',task.name),el('small','',task.desc));
      const arrow=el('div','operation-arrow');arrow.innerHTML='<svg viewBox="0 0 24 24"><path d="M9 18l6-6-6-6"/></svg>';
      choice.append(symbol,text,arrow);
      choice.addEventListener('click',()=>chooseOperation(task.id));refs['operation-list'].append(choice);
    }
    if(items.length>4){
      const more=el('button','quiet-button',expanded?'收起其他操作':`查看另外 ${items.length-4} 项操作`);
      more.type='button';more.disabled=busy;more.style.alignSelf='flex-start';
      more.addEventListener('click',()=>{expanded=!expanded;renderRecommendations()});
      refs['operation-list'].append(more);
    }
  }
  function renderExecution(){
    const task=selectedTask();if(!task)return;
    const active=grouped();
    const processed=task.multi?active:[active.find(item=>item.id===singleFileId)||active[0]];
    refs['chosen-icon'].innerHTML=icon(task.icon);
    refs['chosen-name'].textContent=task.name;
    refs['chosen-desc'].textContent=task.desc;
    refs['selection-summary'].textContent=`将处理 ${processed.length} 个文件`;
    // Single-file operations explicitly highlight one item in the existing file list.
    // Do not show a duplicate selector: a single place to make a choice is clearer.
    refs['single-file-pick'].replaceChildren();
    refs['single-file-pick'].hidden=true;
    if(!task.multi && active.length>1){
      const chosenName=processed[0].file.name;
      refs['selection-summary'].textContent=`仅处理：${chosenName}`;
      refs['selection-summary'].title=chosenName;
    }
    refs['option-fields'].replaceChildren();
    for(const field of task.fields||[]){
      const wrapper=el('div','field');
      const label=el('label','',field.label);label.htmlFor='option-'+field.key;
      wrapper.append(label);
      if(field.type==='text'){
        const input=el('input','field-control');input.id=label.htmlFor;input.type='text';input.placeholder=field.placeholder||'';input.autocomplete='off';input.disabled=busy;wrapper.append(input);
      }else{
        const select=el('select','field-control');select.id=label.htmlFor;select.disabled=busy;
        field.choices.forEach(([value,title])=>{const item=el('option','',title);item.value=value;select.append(item)});
        if(field.default)select.value=field.default;wrapper.append(select);
      }
      if(field.help)wrapper.append(el('div','field-help',field.help));
      refs['option-fields'].append(wrapper);
    }
    refs['execution-note'].textContent='';
    refs['execute'].disabled=busy||processed.length<(task.min||1);
    const count=processed.length;
    refs['execute-label'].textContent=busy?'正在本机处理…':task.id==='pdf_merge'?`合并这 ${count} 份 PDF`:
      count>1?`${task.action} · ${count} 个文件`:task.action;
    refs['result-bar'].hidden=!lastResult;
    refs['result-bar'].replaceChildren();
    if(lastResult){
      const check=el('div','','✓');check.setAttribute('aria-hidden','true');
      const resultText=el('span','',lastResult);
      refs['result-bar'].append(check,resultText);
    }
  }
  // V1.0.0 – PDFs render one page at a time on the loopback server.
  // File order is shared with the main workbench; preview never mutates source data.
  function closePreview(){
    if(!previewOpen)return;
    previewOpen=false;previewEpoch++;previewSelectionEpoch++;
    refs['preview-modal'].hidden=true;refs['preview-backdrop'].hidden=true;
    if(previewBlobUrl){URL.revokeObjectURL(previewBlobUrl);previewBlobUrl=null;}
    for(const pending of previewSessions.values()){
      Promise.resolve(pending).then(session=>{
        fetch('/api/preview/'+session.id,{method:'DELETE'}).catch(()=>{});
      }).catch(()=>{});
    }
    previewSessions.clear();
    const focusTarget=previewReturnFocus;
    previewReturnFocus=null;
    if(focusTarget?.isConnected)focusTarget.focus();
  }
  function supportedPreview(item){return item && (item.kind==='pdf' || (item.kind==='image' && !/\.(tif|tiff)$/i.test(item.file.name)));}
  async function ensurePreviewSession(item){
    const existing=previewSessions.get(item.id);
    if(existing)return existing;
    // Keep no more than eight temporary PDF sessions in a preview dialog;
    // revisiting an evicted file transparently creates a fresh session.
    while(previewSessions.size>=8){
      const oldest=previewSessions.keys().next().value;
      const discarded=previewSessions.get(oldest);previewSessions.delete(oldest);
      Promise.resolve(discarded).then(session=>fetch('/api/preview/'+session.id,{method:'DELETE'}).catch(()=>{})).catch(()=>{});
    }
    const epoch=previewEpoch;
    const data=new FormData();data.append('file',item.file,item.file.name);
    const pending=(async()=>{
      const response=await fetch('/api/preview/pdf',{method:'POST',body:data});
      if(!response.ok){
        let detail='无法预览这份 PDF';
        try{detail=(await response.json()).detail||detail}catch{}
        throw new Error(detail);
      }
      const result=await response.json();
      if(!/^[a-f0-9]{32}$/.test(result.id)||!(result.pages>0))throw new Error('预览服务返回了无效结果');
      if(!previewOpen||epoch!==previewEpoch){
        fetch('/api/preview/'+result.id,{method:'DELETE'}).catch(()=>{});
        throw new Error('预览已关闭');
      }
      return result;
    })();
    previewSessions.set(item.id,pending);
    try{return await pending}catch(error){previewSessions.delete(item.id);throw error;}
  }
  function refreshPreviewSidebar(){
    if(!previewOpen)return;
    const current=files.find(x=>x.id===previewSelected);
    if(!current)return;
    const peers=grouped(current.kind);
    const canReorder=current.kind==='pdf' && selectedTask()?.id==='pdf_merge' && !busy;
    refs['preview-files'].replaceChildren();
    for(let index=0;index<peers.length;index++){
      const item=peers[index];
      const row=el('div','preview-file-entry'+(item.id===previewSelected?' selected':''));
      const select=el('button','preview-file-choice');select.type='button';
      select.setAttribute('aria-label','预览 '+item.file.name);
      const photo=el('div','preview-file-thumb');
      if(item.kind==='pdf'){
        photo.textContent='PDF';
        // Thumbnails load only for a bounded number of files. For a batch of
        // 35 PDFs, loading every source before allowing a preview would stall.
        if(index<8){
          ensurePreviewSession(item).then(session=>{
            if(!previewOpen||!photo.isConnected)return;
            const thumb=el('img');thumb.alt='第 1 页缩略图';thumb.loading='lazy';
            thumb.src=`/api/preview/${session.id}/pages/0?size=thumb`;
            photo.replaceChildren(thumb);
          }).catch(()=>{});
        }
      }else{
        photo.textContent='图片';
      }
      select.append(photo,el('span','preview-file-name',item.file.name));
      select.addEventListener('click',()=>selectPreview(item.id));row.append(select);
      if(canReorder){
        const moves=el('div','preview-order');
        for(const [delta,label,symbol] of [[-1,'上移','↑'],[1,'下移','↓']]){
          const button=el('button','preview-order-button',symbol);button.type='button';
          button.disabled=delta<0?index===0:index===peers.length-1;
          button.title=label;button.setAttribute('aria-label',item.file.name+' '+label);
          button.addEventListener('click',()=>{moveFile(item.id,delta);refreshPreviewSidebar()});moves.append(button);
        }
        row.append(moves);
      }
      refs['preview-files'].append(row);
    }
  }
  function previewMessage(message){
    refs['preview-stage'].replaceChildren(el('div','preview-message',message));
  }
  function setPreviewImage(url, alt){
    const img=el('img','preview-large');img.alt=alt;
    img.addEventListener('error',()=>{if(img.isConnected)previewMessage('页面无法显示，请尝试重新打开预览。')});
    img.src=url;refs['preview-stage'].replaceChildren(img);
  }
  function renderPreviewPages(session){
    refs['preview-pages'].hidden=false;
    refs['preview-prev'].disabled=previewPage<=0;
    refs['preview-next'].disabled=previewPage>=session.pages-1;
    refs['preview-page-label'].textContent=`第 ${previewPage+1} / ${session.pages} 页`;
    setPreviewImage(`/api/preview/${session.id}/pages/${previewPage}`,`第 ${previewPage+1} 页预览`);
    refs['preview-thumbs'].replaceChildren();
    // Show first/last plus a small window around the current page; keep
    // network and raster work bounded regardless of PDF length.
    const visible=new Set([0,session.pages-1]);
    for(let p=Math.max(0,previewPage-2);p<=Math.min(session.pages-1,previewPage+2);p++)visible.add(p);
    for(const p of [...visible].sort((a,b)=>a-b)){
      const button=el('button','preview-thumb'+(p===previewPage?' active':''));button.type='button';
      button.setAttribute('aria-label','查看第 '+(p+1)+' 页');
      const thumb=el('img');thumb.alt='';thumb.loading='lazy';
      thumb.src=`/api/preview/${session.id}/pages/${p}?size=thumb`;
      button.append(thumb,el('span','',String(p+1)));
      button.addEventListener('click',()=>{previewPage=p;renderPreviewPages(session)});
      refs['preview-thumbs'].append(button);
    }
  }
  async function selectPreview(id){
    const item=files.find(x=>x.id===id);
    if(!previewOpen||!supportedPreview(item))return;
    previewSelected=id;previewPage=0;const selection=++previewSelectionEpoch;
    refs['preview-subtitle'].textContent=item.file.name;
    refs['preview-pages'].hidden=true;refs['preview-thumbs'].replaceChildren();
    if(previewBlobUrl){URL.revokeObjectURL(previewBlobUrl);previewBlobUrl=null;}
    previewMessage('正在准备预览…');refreshPreviewSidebar();
    if(item.kind==='image'){
      previewBlobUrl=URL.createObjectURL(item.file);
      setPreviewImage(previewBlobUrl,'图片预览');return;
    }
    try{
      const session=await ensurePreviewSession(item);
      if(!previewOpen||previewSelected!==id||selection!==previewSelectionEpoch)return;
      renderPreviewPages(session);
    }catch(error){
      if(previewOpen&&previewSelected===id&&selection===previewSelectionEpoch)previewMessage(error.message||'PDF 预览失败');
    }
  }
  function openPreview(id){
    if(busy||previewOpen)return;
    const item=files.find(x=>x.id===id);
    if(!supportedPreview(item))return;
    previewOpen=true;previewEpoch++;previewReturnFocus=document.activeElement;
    refs['preview-modal'].hidden=false;refs['preview-backdrop'].hidden=false;
    refs['preview-close'].focus();selectPreview(id);
  }
  function changePreviewPage(delta){
    const selectedId=previewSelected;
    const pending=previewSessions.get(selectedId);
    if(!pending)return;
    Promise.resolve(pending).then(session=>{
      if(!previewOpen||previewSelected!==selectedId)return;
      previewPage=Math.min(session.pages-1,Math.max(0,previewPage+delta));
      renderPreviewPages(session);
    }).catch(()=>{});
  }

  function downloadLastResult(){
    if(!recentDownload||!/^[a-f0-9]{32}$/.test(recentDownload.resultId))return;
    // The browser streams directly from the local history endpoint. Unlike fetch().blob(),
    // this does not duplicate multi-hundred-MB results in JavaScript memory.
    const link=document.createElement('a');
    link.href='/api/history/'+recentDownload.resultId+'/download';
    link.download=recentDownload.filename;
    document.body.append(link);link.click();link.remove();
  }
  async function execute(){
    if(busy||!selectedTask())return;
    const task=selectedTask();const group=grouped();
    const chosen=task.multi?group:[group.find(item=>item.id===singleFileId)||group[0]];
    if(chosen.length<(task.min||1)){showToast('当前文件数量不足，请添加文件。',true);return;}
    const options={};
    for(const field of task.fields||[])options[field.key]=(document.getElementById('option-'+field.key)?.value||'').trim();
    if(['pdf_extract','pdf_remove'].includes(task.id)&&!options.pages){showToast('请先输入要处理的页码。',true);document.getElementById('option-pages')?.focus();return;}
    busy=true;lastResult=null;cancelPending=false;activeJobId=null;
    refs['inline-error'].hidden=true;
    uploadController=new AbortController();renderBusy(true);
    const data=new FormData();data.append('operation',task.id);data.append('options',JSON.stringify(options));
    chosen.forEach(item=>data.append('files',item.file,item.file.name));
    try{
      // Long Excel conversions run as bounded local background jobs. Never
      // leave the UI waiting indefinitely on one open HTTP request.
      const submitted=await fetch('/api/jobs',{method:'POST',body:data,signal:uploadController.signal});
      uploadController=null;
      if(!submitted.ok){let reason='无法创建处理任务';try{reason=(await submitted.json()).detail||reason}catch{}throw new Error(reason)}
      const job=await submitted.json();
      if(!/^[a-f0-9]{32}$/.test(job.id||''))throw new Error('任务编号无效，请刷新后重试。');
      activeJobId=job.id;renderBusy(true);
      let state=job;
      const deadline=Date.now()+12*60*1000+30000;
      let failures=0;
      while(!['completed','failed','cancelled'].includes(state.status)){
        if(Date.now()>deadline)throw new Error('等待超过 12 分钟，请查看终端输出并尝试拆分文件。');
        await new Promise(resolve=>setTimeout(resolve,850));
        let check;
        try{check=await fetch('/api/jobs/'+job.id,{cache:'no-store'});}catch(error){
          if(++failures<4)continue;
          throw new Error('本地服务连接中断，可能是转换进程退出。请检查终端错误信息。');
        }
        if(!check.ok){if(++failures<4)continue;throw new Error('无法获取转换进度，请检查本地服务。')}
        failures=0;state=await check.json();
        const percentage=Number.isFinite(+state.percent)?Math.min(100,Math.max(0,+state.percent)):0;
        refs['execute-label'].textContent=cancelPending?'正在停止…':'正在处理 · '+percentage+'%';
        refs['execution-note'].textContent=state.stage||'';
      }
      if(state.status==='cancelled'){showToast('任务已取消。');return;}
      if(state.status==='failed')throw new Error(state.error||'文件处理失败，请检查源文件。');
      // The server has already stored the result. Let the browser stream it
      // directly to Downloads instead of reading a potentially huge Blob.
      const filename=state.filename||'文序_处理结果.zip';
      if(!/^[a-f0-9]{32}$/.test(state.result_id||''))
        throw new Error('处理已完成，但结果保存失败，请在历史记录中检查。');
      recentDownload={filename,resultId:state.result_id};
      downloadLastResult();
      // A local persistent copy is saved by the server for history re-download.
      const storedId=state.result_id;
      if(storedId){
        history.unshift({id:storedId,action:task.name,name:filename,count:chosen.length,created_at:Date.now()/1000});
      }

      // Start a fresh working context, but keep the result for a manual re-download.
      files=[];activeKind=null;operation=null;singleFileId=null;expanded=false;lastResult=null;
      refs['success-filename'].textContent=filename+((filename.includes('可读重排')||filename.includes('清晰排版'))?'（已采用可读重排，原 Word 的部分版式可能变化）':'');
      refs['success-banner'].hidden=false;
    }catch(error){
      const message=error?.name==='AbortError'?'已取消上传。':(error?.message||'文件处理失败，请重试。');
      if(error?.name==='AbortError')showToast(message);
      else{refs['inline-error'].textContent=message;refs['inline-error'].hidden=false;showToast(message,true);}
    }
    finally{busy=false;activeJobId=null;uploadController=null;cancelPending=false;refs['execution-note'].textContent='';render();renderBusy(false);}
  }
  function renderBusy(value){
    refs['cancel-job'].hidden=!value;
    refs['cancel-job'].disabled=!value||cancelPending;
    refs['cancel-job'].textContent=cancelPending?'正在停止…':(!activeJobId?'取消上传':'取消任务');
    const current=selectedTask();
    const count=grouped().length;
    refs.execute.disabled=value || !current || count<(current.min||1);
    refs['execute-label'].textContent=value?'正在本机处理…':'开始处理';
    refs['add-inline'].disabled=value;
    refs['reset-all'].disabled=value;
    refs['operation-list'].querySelectorAll('button').forEach(btn=>{btn.disabled=value});
    refs['file-list'].querySelectorAll('button').forEach(btn=>{btn.disabled=value});
    refs['option-fields'].querySelectorAll('input,select').forEach(field=>{field.disabled=value});
    refs['single-file-pick'].querySelectorAll('select').forEach(field=>{field.disabled=value});
  }
  async function cancelJob(){
    if(!busy||cancelPending)return;
    if(!activeJobId&&uploadController){uploadController.abort();return;}
    if(!activeJobId)return;
    cancelPending=true;renderBusy(true);
    try{
      const response=await fetch('/api/jobs/'+activeJobId+'/cancel',{method:'POST'});
      if(!response.ok)throw new Error('取消请求失败，请稍后重试。');
      const status=await response.json();
      if(status.status==='completed')showToast('转换已经完成，正在保存结果。');
    }catch(error){cancelPending=false;renderBusy(true);showToast(error.message||'取消失败',true);}
  }
  function reset(){if(busy)return;refs['inline-error'].hidden=true;files=[];activeKind=null;operation=null;singleFileId=null;expanded=false;lastResult=null;refs['success-banner'].hidden=true;render();}
  function historyDownload(record){
    if(!/^[a-f0-9]{32}$/.test(record.id||'')){showToast('该记录无法下载，请重新转换。',true);return;}
    const link=document.createElement('a');
    link.href='/api/history/'+record.id+'/download';
    link.download=record.name;
    document.body.append(link);link.click();link.remove();
  }
  function renderHistory(){
    refs['history-list'].replaceChildren();
    if(!history.length){
      refs['history-list'].append(el('div','history-empty','还没有可下载的历史结果。'));
      return;
    }
    for(const record of history){
      const item=el('div','history-item');
      const desc=el('div','history-details');
      const stamp=new Date(record.created_at*1000).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
      desc.append(el('strong','',(tasks.find(task=>task.id===record.action)?.name || record.action)),el('span','',`${stamp} · ${record.count} 个文件`),el('span','history-filename',record.name));
      const download=el('button','history-download','重新下载');
      download.type='button';download.setAttribute('aria-label','重新下载 '+record.name);
      download.addEventListener('click',()=>historyDownload(record));
      item.append(desc,download);refs['history-list'].append(item);
    }
  }
  async function loadHistory(){
    refs['history-list'].replaceChildren(el('div','history-empty','正在读取本机历史结果…'));
    try{
      const response=await fetch('/api/history',{cache:'no-store'});
      if(!response.ok)throw new Error('读取失败');
      const result=await response.json();
      history=Array.isArray(result.items)?result.items:[];
      renderHistory();
    }catch(error){
      refs['history-list'].replaceChildren(el('div','history-empty','历史记录读取失败，请重试。'));
      showToast(error?.message||'历史记录读取失败',true);
    }
  }
  function toggleHistory(open){
    refs['history-backdrop'].hidden=!open;
    refs['history-panel'].hidden=!open;
    if(!open){refs['history-toggle'].focus();return;}
    refs['history-close'].focus();
    loadHistory();
  }
  async function clearHistory(){
    if(!window.confirm('确定清空本机保存的转换结果吗？清空后将无法从历史记录重新下载。'))return;
    try{
      const response=await fetch('/api/history',{method:'DELETE'});
      if(!response.ok)throw new Error('清理失败');
      history=[];
      renderHistory();
      showToast('历史结果已从本机清理。');
    }catch(error){showToast('清理失败，请稍后重试。',true)}
  }
  function openPicker(){if(!busy)refs['file-input'].click()}
  for(const ref of ['welcome-drop','add-inline'])refs[ref].addEventListener('click',openPicker);
  refs['welcome-drop'].addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();openPicker()}});
  refs['file-input'].addEventListener('change',event=>{addFiles(event.target.files);event.target.value=''});
  refs['reset-all'].addEventListener('click',reset);
  refs['redownload'].addEventListener('click',downloadLastResult);
  refs['success-dismiss'].addEventListener('click',()=>{refs['success-banner'].hidden=true});
  refs.execute.addEventListener('click',execute);
  refs['cancel-job'].addEventListener('click',cancelJob);
  refs['history-toggle'].addEventListener('click',()=>toggleHistory(true));
  refs['history-close'].addEventListener('click',()=>toggleHistory(false));
  refs['history-clear'].addEventListener('click',clearHistory);
  refs['history-backdrop'].addEventListener('click',()=>toggleHistory(false));
  refs['preview-close'].addEventListener('click',closePreview);
  refs['preview-done'].addEventListener('click',closePreview);
  refs['preview-backdrop'].addEventListener('click',closePreview);
  refs['preview-prev'].addEventListener('click',()=>changePreviewPage(-1));
  refs['preview-next'].addEventListener('click',()=>changePreviewPage(1));
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'){if(previewOpen)closePreview();else if(!refs['history-panel'].hidden)toggleHistory(false);return;}
    if(previewOpen){
      if(event.key==='Tab'){
        const focusables=[...refs['preview-modal'].querySelectorAll('button:not([disabled])')];
        const first=focusables[0],last=focusables[focusables.length-1];
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
      }
      if(event.key==='ArrowLeft')changePreviewPage(-1);
      if(event.key==='ArrowRight')changePreviewPage(1);
      return;
    }
    if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='o'){
      event.preventDefault();openPicker();
    }
  });
  // A document-level drop target supports real Finder drag and drop in both empty and loaded states.
  // Dragging UI elements within the document does not trigger file import.
  document.addEventListener('dragenter',event=>{
    if(!Array.from(event.dataTransfer?.types||[]).includes('Files'))return;
    event.preventDefault();dragDepth++;if(!busy)refs['drag-overlay'].hidden=false;
  });
  document.addEventListener('dragover',event=>{
    if(!Array.from(event.dataTransfer?.types||[]).includes('Files'))return;
    event.preventDefault();event.dataTransfer.dropEffect=busy?'none':'copy';
  });
  document.addEventListener('dragleave',event=>{
    if(!Array.from(event.dataTransfer?.types||[]).includes('Files'))return;
    dragDepth=Math.max(0,dragDepth-1);if(dragDepth===0)refs['drag-overlay'].hidden=true;
  });
  document.addEventListener('drop',event=>{
    event.preventDefault();dragDepth=0;refs['drag-overlay'].hidden=true;
    if(event.dataTransfer?.files?.length)addFiles(event.dataTransfer.files);
  });
  window.addEventListener('blur',()=>{dragDepth=0;refs['drag-overlay'].hidden=true});

  render();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once:true});
  } else {
    init();
  }
})();
