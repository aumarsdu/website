import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove inline style and add css/style.css, open graph, json-ld
head_replacement = """  <meta name="keywords" content="河狸陪,Heilipei,升学规划,背景提升,科研项目,国际竞赛,实习项目,留学规划">
  
  <!-- Open Graph -->
  <meta property="og:title" content="河狸陪 | 怕选错就找河狸陪 — 独立第三方升学规划平台">
  <meta property="og:description" content="河狸陪是独立第三方升学背景提升平台，不绑定任何机构，只站在你的立场。提供科研项目、国际竞赛、实习项目、升学规划等一站式服务，帮你从全市场筛选最匹配的方案。">
  <meta property="og:image" content="https://www.heilipei.com/assets/heilipei-logo.jpeg">
  <meta property="og:url" content="https://www.heilipei.com/">
  <meta property="og:type" content="website">

  <!-- JSON-LD -->
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "EducationalOrganization",
    "name": "河狸陪",
    "description": "独立第三方升学背景提升平台，不绑定任何机构，只站在你的立场。",
    "url": "https://www.heilipei.com",
    "logo": "https://www.heilipei.com/assets/heilipei-logo.jpeg"
  }
  </script>

  <link rel="manifest" href="manifest.json">
  <link rel="stylesheet" href="css/minimal.css">
  <link rel="stylesheet" href="css/style.css">
</head>"""

content = re.sub(r'  <meta name="keywords" content="[^"]*">.*?</style>\n</head>', head_replacement, content, flags=re.DOTALL)

# 2. Add links to the 5 workshops in the top navigation bar and width/height to logo
header_old = """  <header class="site-nav" id="top">
    <div class="shell nav-shell">
      <a class="brand-link" href="#top" aria-label="返回页面顶部">
        <img class="brand-mark" src="assets/heilipei-logo.jpeg" alt="河狸陪 Logo">
      </a>
      <a class="nav-cta" href="#cta-section" data-open-wechat-modal data-modal-size="large">免费咨询 →</a>
    </div>
  </header>"""

header_new = """  <header class="site-nav" id="top">
    <div class="shell nav-shell">
      <a class="brand-link" href="#top" aria-label="返回页面顶部">
        <img class="brand-mark" src="assets/heilipei-logo.jpeg" alt="河狸陪 Logo" width="160" height="52">
      </a>
      <nav class="nav-menu" aria-label="主导航">
        <a class="nav-item" href="/workshops.html#research">科研项目</a>
        <a class="nav-item" href="/workshops.html#competition">国际竞赛</a>
        <a class="nav-item" href="/workshops.html#internship">实习项目</a>
        <a class="nav-item" href="/workshops.html#planning">升学规划</a>
        <a class="nav-item" href="/workshops.html#summer-school">夏校申请</a>
      </nav>
      <a class="nav-cta" href="#cta-section" data-open-wechat-modal data-modal-size="large">免费咨询 →</a>
    </div>
  </header>"""

content = content.replace(header_old, header_new)

# 3. Add width/height to all other <img> tags (qr code)
content = content.replace('<img class="qr-image" src="assets/wechat-qr.jpeg" alt="河狸陪教育规划师微信二维码">', '<img class="qr-image" src="assets/wechat-qr.jpeg" alt="河狸陪教育规划师微信二维码" width="200" height="200">')

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)

