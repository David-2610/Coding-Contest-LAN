"""Typed function starters and private C++/Java judge drivers."""
import json
import re
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1] / "var/toolchain"
JDK = "/tool/usr/lib/jvm/java-21-openjdk-amd64"
GSON = "/tool/usr/share/java/gson.jar"
LANGUAGES = ("python","cpp","java")
TYPES = {"int":("int","int"),"bool":("bool","boolean"),"string":("string","String")}
def default_signature():
    return {"params":[["nums","int[]"]],"returns":"int"}

def typename(t,lang):
    if t.endswith("[]"):
        item=typename(t[:-2],lang)
        return f"vector<{item}>" if lang=="cpp" else item+"[]"
    return TYPES[t][lang=="java"]

def check_signature(name,sig):
    ident=r"[A-Za-z_][A-Za-z0-9_]*"
    if not re.fullmatch(ident,name) or not isinstance(sig,dict): raise ValueError("Invalid function name or signature")
    params=sig["params"]
    if not isinstance(params,list): raise ValueError("Parameters must be a list")
    seen=set()
    for n,t in params:
        if not re.fullmatch(ident,n) or n in seen: raise ValueError("Invalid or duplicate parameter name")
        seen.add(n);typename(t,"cpp")
    typename(sig["returns"],"cpp")

def starter(problem,language):
    if problem.package:return problem.package["languages"][{"python":"python3","cpp":"cpp17","java":"java21"}[language]]["starterCode"]
    if language=="python": return problem.starter
    sig=problem.signature
    args=", ".join(typename(t,language)+" "+n for n,t in sig["params"])
    return f'{typename(sig["returns"],language)} {problem.function}({args}) {{\n    // Write your solution here\n}}\n'

def driver(lang,source,function,sig):
    check_signature(function,sig)
    if lang=="cpp":
        args=", ".join(f"a.at({i}).get<{typename(t,lang)}>()" for i,(_,t) in enumerate(sig["params"]))
        return ('#include <bits/stdc++.h>\n#include <nlohmann/json.hpp>\nusing namespace std;\nclass Solution { public:\n'
                +source+'\n};\nint main(){ auto a=nlohmann::json::parse(cin); auto original=cout.rdbuf(cerr.rdbuf()); auto value=Solution().'
                +function+'('+args+'); cout.rdbuf(original); cout << nlohmann::json(value).dump(); }')
    args=", ".join(f"g.fromJson(a.get({i}), {typename(t,lang)}.class)" for i,(_,t) in enumerate(sig["params"]))
    return ('import java.util.*;\nimport java.io.*;\nimport com.google.gson.*;\nclass Solution {\n'+source+
            '\n}\nclass Driver { public static void main(String[] unused) throws Exception { Gson g=new Gson(); JsonArray a=JsonParser.parseReader(new InputStreamReader(System.in)).getAsJsonArray(); PrintStream out=System.out; System.setOut(System.err); out.print(g.toJson(new Solution().'+function+'('+args+'))); }}')

def launch(command,folder,data,build,execution=None):
    # Only this isolated scope sees compiler subprocesses. Its cgroup bounds the whole tree.
    cpu,wall,size=(20,35,32<<20) if build else (3,7,65536)
    memory=512
    if execution and not build:
        wall=execution["timeLimitMs"]/1000
        cpu=max(1,int(wall+0.999))
        memory=execution["memoryLimitMB"]
    sandbox=["bwrap","--unshare-all","--unshare-user","--disable-userns","--cap-drop","ALL","--die-with-parent","--new-session","--clearenv",
             "--ro-bind","/usr","/usr","--symlink","usr/bin","/bin","--symlink","usr/lib","/lib","--symlink","usr/lib64","/lib64",
             "--ro-bind",str(ROOT),"/tool","--ro-bind",str(ROOT/"etc/java-21-openjdk"),"/etc/java-21-openjdk",
             "--ro-bind",str(folder),"/job","--size","67108864","--tmpfs","/tmp","--proc","/proc","--dev","/dev","--chdir","/tmp",
             "--setenv","PATH","/usr/bin","--setenv","LD_LIBRARY_PATH","/tool/usr/lib/x86_64-linux-gnu",
             "--","prlimit",f"--cpu={cpu}:{cpu+1}",f"--fsize={size}","--nofile=128","--core=0","--",*command]
    with tempfile.TemporaryFile() as inp,tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
        inp.write(data);inp.seek(0)
        unit="codeclash-job-"+uuid4().hex+".service"
        rc=subprocess.run(["systemd-run","--user","--quiet","--pipe","--wait","--unit",unit,"-p","TasksMax=64","-p",f"MemoryMax={memory}M","-p","MemorySwapMax=0","-p",f"RuntimeMaxSec={wall}s","--",*sandbox],stdin=inp,stdout=out,stderr=err,timeout=wall+12).returncode
        if rc:
            reason=subprocess.run(["systemctl","--user","show","-p","Result","--value",unit],capture_output=True,text=True).stdout.strip()
            subprocess.run(["systemctl","--user","reset-failed",unit],capture_output=True)
            if reason=="oom-kill":rc=-1001
            elif reason=="timeout":rc=-1002
        err.seek(0);log=err.read(65536).decode(errors="replace")
        if log.startswith(("bwrap:","Failed to start transient","Failed to connect")): raise RuntimeError(log[:200])
        out.seek(0);return rc,out.read(size),log[-3000:]

def compiled(job,folder):
    stdio=bool(job.problem.package)
    code=job.source if stdio else driver(job.language,job.source,job.function,job.problem.signature)
    if job.language=="python":
        (folder/"main.py").write_text(code)
        run=["/usr/bin/python3","-I","-B","/job/main.py"]
    elif job.language=="cpp":
        (folder/"main.cpp").write_text(code)
        script="/tool/usr/bin/x86_64-linux-gnu-g++-15 -std=c++17 -O0 -I/tool/usr/include -I/tool/usr/include/c++/15 -I/tool/usr/include/x86_64-linux-gnu/c++/15 /job/main.cpp -o /tmp/main >&2 && cat /tmp/main"
        target="program"; run=["/job/program"]
    else:
        (folder/("Main.java" if stdio else "Driver.java")).write_text(code)
        opts="-XX:ActiveProcessorCount=1 -XX:+UseSerialGC -Xmx128m"
        compile_cmd=f"{JDK}/bin/javac -J-XX:ActiveProcessorCount=1 -J-Xmx128m -proc:none -cp {GSON} -d /tmp /job/Driver.java"
        if stdio:compile_cmd=compile_cmd.replace("/job/Driver.java","/job/Main.java")
        script=compile_cmd+f" >&2 && {JDK}/bin/jar -J-XX:ActiveProcessorCount=1 cf /tmp/prog.jar *.class >&2 && cat /tmp/prog.jar"
        target="prog.jar";run=[JDK+"/bin/java",*opts.split(),"-cp","/job/prog.jar:"+GSON,"Main" if stdio else "Driver"]
    if job.language!="python":
        rc,binary,log=launch(["sh","-c",script],folder,b"",True)
        if rc:return None,log or "Compile limit exceeded"
        path=folder/target;path.write_bytes(binary);path.chmod(0o500)
    def execute(args):
        rc,output,log=launch(run,folder,args[0].encode() if stdio else json.dumps(args).encode(),False,job.problem.package.get("execution"))
        if rc:return ("Memory limit exceeded" if rc==-1001 else "Time limit" if rc in (-1002,15,143,152) else "Runtime error"),log or None
        if stdio:return "Returned",output.decode(errors="replace").rstrip()
        try:return "Returned",json.loads(output)
        except (ValueError,UnicodeError,RecursionError):return "Invalid output",None
    return execute,None
