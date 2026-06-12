#!/usr/bin/env python3
"""
OA 支付款项数据抓取。通过 playwright-cli 驱动浏览器。
用法: uv run python3 oa_scraper.py [output.json]
"""

import subprocess, json, sys, re, time, os, base64

def run_js(code, timeout=120):
    r = subprocess.run(["playwright-cli", "run-code", code],
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr

def run_cli(args, timeout=60):
    r = subprocess.run(["playwright-cli"] + args,
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr

def extract_json(text):
    """从 playwright-cli 输出提取 JSON（处理多层序列化）。"""
    m = re.search(r'### Result\s*\n(.+?)(?:\n###|\Z)', text, re.DOTALL)
    if m:
        s = re.sub(r'^```.*?\n?|\n?```$', '', m.group(1).strip())
        try:
            v = json.loads(s)
            return json.loads(v) if isinstance(v, str) else v
        except json.JSONDecodeError: pass
    for pat in [r'"(\[.*?\])"', r'"(\{.*?\})"']:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try: return json.loads(m.group(1))
            except json.JSONDecodeError: pass
    return None

def load_env():
    # 优先从项目根目录 info.md 读取凭据
    info_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "info.md"))
    for p in [info_path,
              os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", ".env")),
              os.path.join(os.getcwd(), ".env")]:
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
            return

def solve_captcha():
    """截取验证码并用 ddddocr 识别。"""
    out = run_js("""async p => {
        const img = p.locator('form[name="LoginForm"] img');
        const buf = await img.screenshot({type:'png'});
        return buf.toString('base64');
    }""")
    m = re.search(r'"([A-Za-z0-9+/=]{50,})"', out)
    if not m: return ""
    try:
        import ddddocr
        with open("/tmp/_oa_cap.png", "wb") as f: f.write(base64.b64decode(m.group(1)))
        ocr = ddddocr.DdddOcr(show_ad=False)
        with open("/tmp/_oa_cap.png", "rb") as f: code = ocr.classification(f.read())
        return re.sub(r'\D', '', code)
    except Exception as e:
        print(f"验证码 OCR 失败: {e}", file=sys.stderr)
        return ""

def scrape_detail_bx(item_id):
    """获取报销申请详情。"""
    out = run_js(f"""async page => {{
        const frame = page.frames().find(f => f.url().includes('ListToDo'));
        if (!frame) return {{error:'no frame'}};
        let np;
        try {{
            const [p] = await Promise.all([
                page.context().waitForEvent('page',{{timeout:10000}}),
                frame.evaluate(id => HandleBiz(id,'../../Apps/H_JkBx/BxSq/handle1.jsp?ToDoWorkItem='), '{item_id}')
            ]);
            np = p; await np.waitForLoadState('networkidle',{{timeout:15000}});
        }} catch(e) {{ return {{error:e.message}}; }}
        const data = await np.evaluate(() => {{
            const cells = document.querySelectorAll('table.tableClass td');
            const gv = label => {{
                for(let i=0;i<cells.length;i++){{
                    if(cells[i].textContent.trim().replace(/：$/,'')===label && cells[i+1]){{
                        let t=''; for(const n of cells[i+1].childNodes) if(n.nodeType===3) t+=n.textContent;
                        return t.trim() || cells[i+1].textContent.trim();
                    }}
                }} return '';
            }};
            return {{bxr:gv('报销人'), bxamt:gv('报销金额')}};
        }});
        await np.close().catch(()=>{{}});
        return data;
    }}""", timeout=30)
    r = extract_json(out)
    return r if isinstance(r, dict) else {}

def scrape_detail_zj(item_id):
    """获取资金支付详情。"""
    out = run_js(f"""async page => {{
        const frame = page.frames().find(f => f.url().includes('ListToDo'));
        if (!frame) return {{error:'no frame'}};
        let np;
        try {{
            const [p] = await Promise.all([
                page.context().waitForEvent('page',{{timeout:10000}}),
                frame.evaluate(id => HandleBiz(id,'../../Apps/C_CgFk/ZjZf/handle.jsp?ToDoWorkItem='), '{item_id}')
            ]);
            np = p; await np.waitForLoadState('networkidle',{{timeout:15000}});
        }} catch(e) {{ return {{error:e.message}}; }}
        const data = await np.evaluate(() => {{
            const gv = n => (document.querySelector('input[name="'+n+'"]')||{{}}).value||'';
            return {{gysmc:gv('GysMc'), sqzdamt:gv('SqZfAmt'), fkbt:gv('FkBt')}};
        }});
        await np.close().catch(()=>{{}});
        return data;
    }}""", timeout=30)
    r = extract_json(out)
    return r if isinstance(r, dict) else {}

def main():
    load_env()
    user = os.environ.get("FINANCE_OA_USERNAME", "")
    pwd  = os.environ.get("FINANCE_OA_PASSWORD", "")
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/payment_data.json"

    if not user or not pwd:
        print("错误: 缺少 FINANCE_OA_USERNAME / FINANCE_OA_PASSWORD", file=sys.stderr)
        sys.exit(1)

    # 1. 打开浏览器 & 登录
    run_cli(["open", "--browser=chrome", "--persistent"])
    time.sleep(1)

    for attempt in range(3):
        print(f"登录 OA（第 {attempt+1} 次）...", file=sys.stderr)
        run_js(f"async p=>{{await p.goto('https://oa.nmdev.cn/coakast/login.jsp');return 1;}}")
        time.sleep(1)
        run_js(f"""async p=>{{
            await p.locator('#UsrLoginName').fill('{user}');
            await p.locator('#PassWord').fill('{pwd}');
            return 1;
        }}""")
        cap = solve_captcha()
        if not cap: continue
        print(f"  验证码: {cap}", file=sys.stderr)
        res = run_js(f"""async p=>{{
            await p.locator('input[name="PassWord2"]').fill('{cap}');
            await p.getByRole('button',{{name:'登录'}}).click();
            await p.waitForTimeout(2000);
            return p.url();
        }}""")
        if "main.jsp" in res:
            print("登录成功", file=sys.stderr); break
        print(f"  失败: {res[:60]}", file=sys.stderr)
    else:
        print("登录失败，退出", file=sys.stderr)
        run_cli(["close"]); sys.exit(1)

    # 2. 导航到待办列表
    print("导航到待办列表...", file=sys.stderr)
    run_js("""async p=>{
        const f=p.frame('rls'); if(!f)return'no frame';
        for(const a of await f.locator('a').all()){
            if((await a.textContent()).trim().includes('待办已办')){await a.click();return'ok';}
        } return'not found';
    }""")
    time.sleep(3)

    # 3. 提取列表（含处理环节过滤）
    print("提取列表...", file=sys.stderr)
    out = run_js("""async p=>{
        const f=p.frames().find(f=>f.url().includes('ListToDo'));
        if(!f)return[];
        return await f.evaluate(()=>{
            const rows=document.querySelectorAll('table.vwTable tr[onmouseout]');
            const r=[];
            for(const row of rows){
                const c=row.querySelectorAll('td');
                if(c.length<3)continue;
                const bt=c[1]?.textContent?.trim(), t=c[2]?.textContent?.trim();
                // 提取所有列文本，用于匹配处理环节
                const allText=Array.from(c).map(x=>x.textContent?.trim()||'');
                const oc=c[1]?.getAttribute('onclick')||c[2]?.getAttribute('onclick')||'';
                const m=oc.match(/HandleBiz\('(\d+)'/), m2=oc.match(/HandleBiz\('\d+','([^']+)'/);
                if(m&&(bt==='报销申请'||bt==='资金支付'))
                    r.push({id:m[1],bizType:bt,title:t,handleUrl:m2?m2[1]:'',allCols:allText});
            }
            return r;
        });
    }""")

    raw_items = extract_json(out) or []
    # 过滤：报销申请只取处理环节为"报销结清"的，资金支付只取处理节点为"支付记录"的
    items = []
    for it in raw_items:
        cols = it.get("allCols", [])
        col_text = "|".join(cols)
        if it["bizType"] == "报销申请":
            if "报销结清" not in col_text:
                continue
        elif it["bizType"] == "资金支付":
            if "支付记录" not in col_text:
                continue
        items.append(it)

    bx = sum(1 for i in items if i.get("bizType")=="报销申请")
    zj = sum(1 for i in items if i.get("bizType")=="资金支付")
    raw_bx = sum(1 for i in raw_items if i.get("bizType")=="报销申请")
    raw_zj = sum(1 for i in raw_items if i.get("bizType")=="资金支付")
    print(f"  原始: {raw_bx} 条报销申请，{raw_zj} 条资金支付", file=sys.stderr)
    print(f"  过滤后: {bx} 条报销申请(报销结清)，{zj} 条资金支付(支付记录)", file=sys.stderr)

    # 4. 逐条获取详情
    results = []
    for idx, item in enumerate(items):
        print(f"  [{idx+1}/{len(items)}] {item.get('title','')[:35]}...", file=sys.stderr)
        if item["bizType"] == "报销申请":
            d = scrape_detail_bx(item["id"])
            results.append({"type":"报销","project":d.get("bxr",""),"amount":d.get("bxamt",""),"remark":"报销"})
        else:
            d = scrape_detail_zj(item["id"])
            results.append({"type":"资金支付","project":d.get("gysmc",""),"amount":d.get("sqzdamt",""),"remark":d.get("fkbt","")})

    # 5. 输出
    run_cli(["close"])
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"data":results,"count":len(results)}, f, ensure_ascii=False, indent=2)
    print(f"\n共 {len(results)} 条 → {out_path}", file=sys.stderr)

if __name__ == "__main__":
    main()

