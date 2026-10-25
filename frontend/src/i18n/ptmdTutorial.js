export const ptmdTutorial = {
  zh: {
    entry: '新手教程',
    title: '让商品图出道',
    subtitle: '5 站上手 · 从一张照片到电商成品',
    later: '稍后再看',
    previous: '上一步',
    next: '下一步',
    finish: '完成',
    progress: '教程进度',
    step: '第 {current} / {total} 步',
    steps: [
      {
        icon: '📸', location: '左侧 · 商品素材', title: '请主角登场',
        description: '准备一张清晰的商品照片，第一张作品就从这里开始。',
        items: [
          ['上传照片', '点击「上传主图」，选择 JPG / PNG 图片，也可以直接拖入上传区。'],
          ['选中商品', '点击上传后的缩略图。做详情页时，可以再传几张真实特写。'],
        ],
        tip: '手机上先点素材按钮展开左侧面板。照片越清楚，后面越省心。',
      },
      {
        icon: '🎨', location: '右侧 · 制作方式', title: '今天怎么拍？',
        description: '按你的目标，选一种制作方式。',
        items: [
          ['素材排版', '适合第一次练手。用现有照片排版，配色、裁切与文案在右侧调整；原图背景和文字会保留。'],
          ['GPT Image 2', '按要求生成新画面，需选择生成质量；可在左侧选最多 2 张风格参考图。选项不可用时，可先用素材排版。'],
        ],
        tip: '手机上点参数按钮展开右侧面板。参考图用于提供风格，商品信息以真实素材为准。',
      },
      {
        icon: '✍️', location: '右侧 · 商品与逐页文案', title: '先让一张图出道',
        description: '先做 1 张，满意之后再挑战整套。',
        items: [
          ['填写商品', '输入商品名称，张数先选 1。支持制作 1–9 张独立图片。'],
          ['写上文案', '选择俄语或英语，再自行填入对应语言的图片标题、卖点文案；主图卖点最多两条。'],
          ['按需调整', '只展示商品可勾选「无附加文字与装饰」；裁切在「调整素材与版式」，尺寸和配色在「更多设置」。'],
        ],
        tip: '原图已有文字会保留。商品卖点要真实，别让马克杯突然学会煮咖啡。',
      },
      {
        icon: '⚡', location: '底部 · 画面要求与生成', title: '准备好，开工！',
        description: '检查素材、文案与张数，点击「生成1张电商图」。',
        items: [
          ['使用 AI 时', '可以填写风格、背景等画面要求；需要显示在图上的文字，请填在每页文案里。'],
          ['看清额度', '每张消耗 1 个 MHP 额度，重做再次消耗；AI 模式另有上游费用，提交前查看确认提示。'],
        ],
        example: '浅色桌面，柔和自然光，画面简洁，保留商品真实颜色与结构，不添加配件。',
        tip: '素材排版中的画面要求只作备注，效果需通过素材、裁切、配色和文案设置落实。',
      },
      {
        icon: '🎉', location: '中间 · 成品与核对区', title: '你是最后的质检官',
        description: '成品出炉！检查一下，就可以带走了。',
        items: [
          ['逐页核对', '点击成品，检查并勾选商品一致、文案无误、没有多余配件、版式符合要求，再点「确认本页符合要求」。'],
          ['下载作品', '全部页面确认后，选择 1200 / 2000 px，点击「下载已核对套图」。'],
          ['继续创作', '单页不满意可点「重新生成本页」。准备好后，把张数增加到 2–9 张，逐页安排主图、卖点和细节。'],
        ],
        tip: '点击「完成」就能开始制作。想复习时，随时打开顶部「新手教程」。',
      },
    ],
  },
  en: {
    entry: 'Quick tutorial',
    title: 'Give your product its debut',
    subtitle: '5 steps · From a photo to ecommerce images',
    later: 'Maybe later',
    previous: 'Previous',
    next: 'Next',
    finish: 'Done',
    progress: 'Tutorial progress',
    step: 'Step {current} of {total}',
    steps: [
      {
        icon: '📸', location: 'Left · Product images', title: 'Meet the star',
        description: 'Start your first image with a clear photo of your product.',
        items: [
          ['Upload a photo', 'Click “Upload main images” and choose a JPG / PNG, or drag it into the upload area.'],
          ['Select your product', 'Click its thumbnail. Upload real close-ups for detail pages, too.'],
        ],
        tip: 'On mobile, use the materials button to open the left panel. Clear photos make everything easier.',
      },
      {
        icon: '🎨', location: 'Right · Create with', title: 'Choose your approach',
        description: 'Pick the creation method that fits your goal.',
        items: [
          ['Photo layout', 'A good first try. Arrange existing photos and adjust colors, crops and copy on the right. Original backgrounds and lettering remain.'],
          ['GPT Image 2', 'Generate new visuals from your instructions. Choose AI quality and optionally select up to 2 style references on the left. If unavailable, try photo layout.'],
        ],
        tip: 'On mobile, use the parameters button to open the right panel. References guide style; your actual product photos define the product.',
      },
      {
        icon: '✍️', location: 'Right · Product and page copy', title: 'Start with one image',
        description: 'Get your first image right, then try a whole set.',
        items: [
          ['Name the product', 'Enter its name and start with 1 image. You can create 1–9 independent images.'],
          ['Add your copy', 'Choose Russian or English, then enter the actual headline and selling points in that language. Use at most two selling points on the main image.'],
          ['Make adjustments', 'Choose “No added text or decoration” for a product-only layout. Find crops in “Adjust source & layout”, and size and colors in “More settings”.'],
        ],
        tip: 'Original lettering remains. Keep claims accurate: your mug should not suddenly learn to make coffee.',
      },
      {
        icon: '⚡', location: 'Bottom · Creative brief and generation', title: 'Ready, set, create!',
        description: 'Check your photos, copy and image count, then click “Generate 1 images”.',
        items: [
          ['For AI generation', 'Describe the desired style and background in the creative brief. Put exact image text in each page’s copy fields.'],
          ['Check your credits', 'Each image uses 1 MHP credit, including regenerations. AI generation also incurs provider fees; read the confirmation before submitting.'],
        ],
        example: 'A light tabletop, soft natural light and a simple composition. Preserve the product’s real color and structure; add no accessories.',
        tip: 'In photo layout, the brief is a note. Apply changes using source photos, crops, colors and copy settings.',
      },
      {
        icon: '🎉', location: 'Center · Results and review', title: 'You are the final inspector',
        description: 'Your images are ready. Review them before taking them home.',
        items: [
          ['Review every page', 'Select an image and check product accuracy, correct copy, no extra accessories and the layout. Then click “Confirm this page”.'],
          ['Download your work', 'Once all pages are confirmed, choose 1200 / 2000 px and click “Download reviewed set”.'],
          ['Keep creating', 'Use “Regenerate this page” to redo one page. When ready, try 2–9 images with a main image, selling points and details.'],
        ],
        tip: 'Click “Done” to start creating. Open “Quick tutorial” at the top whenever you want a refresher.',
      },
    ],
  },
}
