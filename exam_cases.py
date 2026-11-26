"""Grounded, labeled synthetic cases; never applied to uploaded documents."""
CASES=(
    ("老化多久","DEMO-100 老化要做幾小時"),
    ("告警門檻","DEMO-100 E-402 告警條件"),
    ("告警後怎麼辦","DEMO-100 E-402 告警後怎麼處理"),
    ("文件沒寫","DEMO-100 保固幾年"),
    ("版本互相衝突","DEMO-100 交接時限"),
    ("設備不存在","SOP-999"),
    ("PDF 頁碼","PDF-200 ALARM-931"),
    ("Word 範例","WORD-210 EVT-221"),
)

def intent(q):
    if "DEMO-100" not in q.upper():return None
    if any(x in q for x in ("保固","價格","定價")):return "missing",()
    if "交接" in q and any(x in q for x in ("時限","多久","分鐘")):
        return "conflict",(("HANDOFF-DAY.md","15 分鐘"),("HANDOFF-NIGHT.md","30 分鐘"))
    if "老化" in q and any(x in q for x in ("多久","小時","時間","時長","幾小時")):
        return "answer",(("DEVICE-DEMO.md","連續 4 小時"),)
    if "E-402" in q.upper():
        if any(x in q for x in ("後","怎麼做","處理","通知","動作","下一步")):
            return "answer",(("DEVICE-DEMO.md","停止出貨"),)
        return "answer",(("DEVICE-DEMO.md","超過 30 mV"),)
    return None

def excerpts(route,hits,corpus):
    status,wanted=route
    if not wanted:return status,[]
    rank={x["chunk_id"]:x for x in hits}
    result=[]
    for file,marker in wanted:
        for x in corpus:
            if x["source"]!=file:continue
            line=next((t for t in x["text"].splitlines() if marker in t),None)
            if line is not None:
                row={k:v for k,v in x.items() if k!="text"}
                row["quote"]=line
                row["channels"]=rank.get(x["chunk_id"],{}).get("channels",["合成題線索定位"])
                result.append(row)
                break
    return (status,result) if len(result)==len(wanted) else ("missing",[])
