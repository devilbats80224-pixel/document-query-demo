"""Local, non-secret preferences. API access stays explicit; no network on save."""
import json,os
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

FIELDS=("embedding_url","embedding_model","chat_url","chat_model")
def path():
    return Path(os.getenv("LITEON_SETTINGS_PATH",str(Path.home()/".config"/"liteon-demo"/"model-settings.json")))

def load():
    p=path()
    if not p.is_file():return {k:"" for k in FIELDS}
    data=json.loads(p.read_text())
    return {k:str(data.get(k,"")) for k in FIELDS}

def save(data):
    if set(data)!=set(FIELDS):raise ValueError("invalid_fields")
    out={k:v.strip() for k,v in data.items()}
    for kind,endpoint in (("embedding","/embeddings"),("chat","/chat/completions")):
        url=out[kind+"_url"]; model=out[kind+"_model"]
        if bool(url)!=bool(model):raise ValueError("url_and_model_required")
        if url:
            u=urlsplit(url)
            if u.scheme!="https" or not u.hostname or u.username or u.password or u.query or u.fragment or not u.path.endswith(endpoint) or len(url)>400:
                raise ValueError("invalid_"+kind+"_url")
            if len(model)>180 or any(ord(c)<32 for c in model):raise ValueError("invalid_model")
    destination=path()
    destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with NamedTemporaryFile("w",encoding="utf-8",dir=destination.parent,delete=False) as tmp:
        json.dump(out,tmp,ensure_ascii=False,indent=2);tmp_path=Path(tmp.name)
    try:os.replace(tmp_path,destination)
    finally:tmp_path.unlink(missing_ok=True)
    return out

def apply_environment():
    data=load()
    keys={"EXAM_EMBED_URL":"embedding_url","EXAM_EMBED_MODEL":"embedding_model","EXAM_CHAT_URL":"chat_url","EXAM_MODEL":"chat_model"}
    for env,key in keys.items():
        if data[key]:os.environ.setdefault(env,data[key])
    urls={urlsplit(os.environ.get(x,"")).hostname for x in ("EXAM_CHAT_URL","EXAM_EMBED_URL") if os.environ.get(x)}
    if len(urls)==1:
        host=next(iter(urls))
        if host:os.environ.setdefault("EXAM_API_HOST",host)

def local_path():
    return path().with_name(path().stem+"-local.json")

def local_load():
    s=local_path()
    if not s.is_file():return {"chat":"off","embedding":"character"}
    raw=json.loads(s.read_text())
    chat=raw.get("chat","off");embed=raw.get("embedding","character")
    return {"chat":chat if chat in {"off","qwen"} else "off",
            "embedding":embed if embed in {"character","qwen"} else "character"}

def local_save(data):
    if set(data)!={"chat","embedding"} or data["chat"] not in {"off","qwen"} or data["embedding"] not in {"character","qwen"}:
        raise ValueError("invalid_local_model_choices")
    file=local_path();file.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with NamedTemporaryFile("w",encoding="utf-8",dir=file.parent,delete=False) as tmp:
        json.dump(data,tmp,ensure_ascii=False);temp=Path(tmp.name)
    try:os.replace(temp,file)
    finally:temp.unlink(missing_ok=True)
