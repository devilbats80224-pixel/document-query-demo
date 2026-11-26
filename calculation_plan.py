"""Explicit formula planning and validated spreadsheet arithmetic. Never eval."""
import ast
from collections import defaultdict
from decimal import Decimal, DecimalException, localcontext
from hashlib import sha256
import json
import re

from openpyxl.utils.cell import get_column_letter
from generic_analysis import number,numeric_fields

AGG={"SUM","AVG","COUNT","MIN","MAX"}
PLAN_TERMS=("毛利率","加權平均","比率","占比","成長率","變動率","自訂公式")
FILTER_TERMS=("排除","不含","不包含","只算","僅","只有","不計","篩選")

def needs_plan(question):
    return any(s in question for s in PLAN_TERMS) or (
        any(s in question for s in FILTER_TERMS)
        and any(s in question for s in ("計算","合計","加總","總和","平均","筆數","數量","最大","最小")))
OPS={ast.Add,ast.Sub,ast.Mult,ast.Div}
UNIT_NAMES={"currency","ccy","幣別","貨幣","unit","單位"}

def map_columns(table):
    eligible=set(numeric_fields(table))
    return {get_column_letter(i):k for i,k in enumerate((k for k in table["fields"] if k in eligible),1)}

def pin(table):
    return sha256(json.dumps(table,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def unique_unit(table):
    names=[c for c in table["fields"] if c.casefold() in UNIT_NAMES]
    return names[0] if len(names)==1 else ""

def propose(q,table,cols):
    if any(f in q for f in FILTER_TERMS):return {}, "題目有篩選條件，請先核對要計入哪些資料；這個版本不會自動套用過濾。"
    nmap={k:c for c,k in cols.items()}
    groups=[x for x in table["fields"] if x not in nmap and re.search(r"(?:各|依|按)"+re.escape(x),q)]
    if len(groups)>1:return {},"分組欄不唯一，請選一欄。"
    group=groups[0] if groups else ""
    group_hint=q
    if "加權平均" in q:
        for c in nmap:group_hint=re.sub(r"(?:按照|依照|按|依)"+re.escape(c),"",group_hint)
    if re.search(r"(?:各|依|按|每.*分組)",group_hint) and not group:
        return {},"題目可能要分組，但找不到確切欄名。請選分組欄再確認。"
    base={"group":group,"unit":unique_unit(table),"percent":False}
    if "毛利率" in q:
        rev=[c for c in nmap if any(x in c.casefold() for x in ("收入","營收","銷售額","revenue","sales"))]
        cost=[c for c in nmap if any(x in c.casefold() for x in ("成本","cost"))]
        for label,candidates in (("收入",rev),("成本",cost)):
            mentioned=[c for c in candidates if c in q]
            if mentioned:
                candidates=mentioned
            if len(candidates)!=1:
                return {},f"{label}欄不唯一或未提供，請明確指定。"
            if label=="收入":a=nmap[candidates[0]]
            else:b=nmap[candidates[0]]
        if a==b:return {},"收入與成本不能用同一欄。"
        return {**base,"formula":f"(SUM({a})-SUM({b}))/SUM({a})","percent":True},""
    if "加權平均" in q:
        stated=[c for c in nmap if c in q]
        weights=[c for c in stated if any(w in c.casefold() for w in ("權重","加權","weight"))]
        amounts=[c for c in stated if c not in weights]
        if len(weights)==len(amounts)==1:
            a=nmap[amounts[0]];b=nmap[weights[0]]
            return {**base,"formula":f"SUM({a}*{b})/SUM({b})"},""
        return {},"請指定數值欄和權重欄；可用 SUM(數值代號*權重代號)/SUM(權重代號)。"
    choices=[c for c in nmap if c in q]
    ops=[(word,op) for word,op in (("加總","SUM"),("合計","SUM"),("平均","AVG"),("筆數","COUNT"),("最小","MIN"),("最大","MAX")) if word in q]
    if len(choices)==1 and len(set(op for _,op in ops))==1:
        return {**base,"formula":f"{ops[0][1]}({nmap[choices[0]]})"},""
    return {}, "未能從問題唯一判斷算式。可編輯公式，或選本機模型提出草案。"

def parse_formula(source,cols):
    if not 1<=len(source)<=180 or not re.fullmatch(r"[A-Z0-9 .+*/()\-]+",source):
        raise ValueError("只接受欄位代號、聚合函數和四則運算。")
    try:root=ast.parse(source.strip(),mode="eval").body
    except SyntaxError as e:raise ValueError("算式格式不正確。") from e
    if len(list(ast.walk(root)))>55:raise ValueError("算式太長或太複雜。")
    calls={}
    def visit(n,row=False):
        if type(n) is ast.BinOp and type(n.op) in OPS:
            visit(n.left,row);visit(n.right,row);return
        if type(n) is ast.UnaryOp and type(n.op) in {ast.UAdd,ast.USub}:
            visit(n.operand,row);return
        if type(n) is ast.Constant and type(n.value) in (int,float) and abs(n.value)<=10**12:return
        if row and type(n) is ast.Name and n.id in cols:return
        if not row and type(n) is ast.Call and type(n.func) is ast.Name and n.func.id in AGG and len(n.args)==1 and not n.keywords:
            visit(n.args[0],True)
            if not any(isinstance(item,ast.Name) and item.id in cols for item in ast.walk(n.args[0])):
                raise ValueError("每個聚合都需要至少一個數值欄。")
            calls.setdefault(ast.dump(n),n)
            return
        raise ValueError("不支援這個動作，或欄位代號不存在。")
    visit(root)
    if not calls or len(calls)>8:raise ValueError("需使用一至八個聚合，例如 SUM(A)。")
    return root,calls

def evaluate(root,values,calls=None):
    if isinstance(root,ast.Constant):return Decimal(str(root.value))
    if isinstance(root,ast.Name):return values[root.id]
    if isinstance(root,ast.Call):return calls[ast.dump(root)]
    if isinstance(root,ast.UnaryOp):
        value=evaluate(root.operand,values,calls)
        return -value if isinstance(root.op,ast.USub) else value
    l=evaluate(root.left,values,calls);r=evaluate(root.right,values,calls)
    if isinstance(root.op,ast.Add):return l+r
    if isinstance(root.op,ast.Sub):return l-r
    if isinstance(root.op,ast.Mult):return l*r
    return l/r

def compute(table,cols,formula,group,unit,percent):
    root,calls=parse_formula(formula,cols)
    if any(k and k not in table["fields"] for k in (group,unit)):
        raise ValueError("分組或單位欄不在來源表。")
    if any(len({row[k] for row in table["rows"] if row[k]})>1 and unit!=k and group!=k
           for k in table["fields"] if k.casefold() in UNIT_NAMES):
        raise ValueError("來源有多個幣別或單位，請指定欄位分開計算。")
    aliases={node.id for call in calls.values() for node in ast.walk(call.args[0]) if isinstance(node,ast.Name)}
    groups=defaultdict(list)
    bad=miss_unit=0
    with localcontext() as ctx:
        ctx.prec=50
        for row in table["rows"]:
            values={k:number(row[cols[k]]) for k in aliases}
            if any(v is None for v in values.values()):bad+=1;continue
            if unit and not row[unit]:miss_unit+=1;continue
            try:computed={key:evaluate(n.args[0],values) for key,n in calls.items()}
            except DecimalException:bad+=1;continue
            groups[(row[unit] if unit else "",(row[group] or "未分類") if group else "全部")].append(computed)
        out=[]
        for (u,g),rows in sorted(groups.items()):
            agg={}
            for k,n in calls.items():
                vs=[r[k] for r in rows]; f=n.func.id
                agg[k]={"SUM":lambda:sum(vs,Decimal(0)),"AVG":lambda:sum(vs,Decimal(0))/len(vs),
                        "COUNT":lambda:Decimal(len(vs)),"MIN":lambda:min(vs),"MAX":lambda:max(vs)}[f]()
            try:value=format(evaluate(root,{},agg),"f"); note=""
            except DecimalException:value=None;note="分母為零或無法定義"
            out.append({"group":g,"unit":u,"ratio":value,"count":len(rows),"note":note,
                        "aggregates":{ast.unparse(calls[k]):format(v,"f") for k,v in agg.items()}})
    return {"formula":formula,"columns":{k:cols[k] for k in cols if k in aliases},
            "group":group,"unit":unit,"percent":percent,"results":out,
            "excluded":{"invalid_numeric":bad,"missing_unit":miss_unit,"malformed_rows":table["excluded"]}}


def human_formula(source,cols):
    root,_=parse_formula(source,cols)
    symbols={ast.Add:"＋",ast.Sub:"－",ast.Mult:"×",ast.Div:"÷"}
    names={"SUM":"合計","AVG":"平均","COUNT":"有效筆數","MIN":"最小值","MAX":"最大值"}
    def describe(x):
        if isinstance(x,ast.Constant):return str(x.value)
        if isinstance(x,ast.Name):return cols[x.id]
        if isinstance(x,ast.Call):return f"{names[x.func.id]}（{describe(x.args[0])}）"
        if isinstance(x,ast.UnaryOp):return ("－" if isinstance(x.op,ast.USub) else "＋")+describe(x.operand)
        return f"（{describe(x.left)} {symbols[type(x.op)]} {describe(x.right)}）"
    return describe(root)
