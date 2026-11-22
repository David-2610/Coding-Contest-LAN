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
TYPES = {
    "int": ("int", "int"),
    "long": ("long long", "long"),
    "float": ("double", "double"),
    "double": ("double", "double"),
    "bool": ("bool", "boolean"),
    "string": ("string", "String")
}
def default_signature():
    return {"params":[["nums","int[]"]],"returns":"int"}

def typename(t,lang):
    if t.endswith("[]"):
        item=typename(t[:-2],lang)
        return f"vector<{item}>" if lang=="cpp" else item+"[]"
    return TYPES[t][lang=="java"]

def py_type(t):
    if t.endswith("[]"):
        return f"list[{py_type(t[:-2])}]"
    mapping = {"int": "int", "long": "int", "float": "float", "double": "float", "bool": "bool", "string": "str"}
    return mapping.get(t, "Any")

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
    if problem.package and "languages" in problem.package and {"python":"python3","cpp":"cpp17","java":"java21"}[language] in problem.package["languages"]:
        return problem.package["languages"][{"python":"python3","cpp":"cpp17","java":"java21"}[language]]["starterCode"]
    sig=problem.signature
    fn=problem.function
    if language=="python":
        args=", ".join(f"{n}: {py_type(t)}" for n,t in sig["params"])
        ret=py_type(sig["returns"])
        return f"class Solution:\n    def {fn}(self, {args}) -> {ret}:\n        # Write your solution here\n        pass\n"
    if language=="cpp":
        args=", ".join(f"{typename(t, 'cpp')}& {n}" if t.endswith("[]") or t=="string" else f"{typename(t, 'cpp')} {n}" for n,t in sig["params"])
        return f"class Solution {{\npublic:\n    {typename(sig['returns'], 'cpp')} {fn}({args}) {{\n        // Write your solution here\n        \n    }}\n}};\n"
    if language=="java":
        args=", ".join(f"{typename(t, 'java')} {n}" for n,t in sig["params"])
        return f"class Solution {{\n    public {typename(sig['returns'], 'java')} {fn}({args}) {{\n        // Write your solution here\n        \n    }}\n}}\n"

def driver(lang,source,function,sig):
    check_signature(function,sig)
    if lang=="cpp":
        decls = "\n    ".join(f"auto p{i} = a.at({i}).get<{typename(t, 'cpp')}>();" for i, (_, t) in enumerate(sig["params"]))
        call_args = ", ".join(f"p{i}" for i in range(len(sig["params"])))
        has_class = "class Solution" in source
        body = source if has_class else f"class Solution {{\npublic:\n{source}\n}};"
        return (f"#include <bits/stdc++.h>\n#include <nlohmann/json.hpp>\nusing namespace std;\n"
                f"{body}\nint main(){{\n    auto a=nlohmann::json::parse(cin);\n    auto original=cout.rdbuf(cerr.rdbuf());\n    {decls}\n    auto value=Solution()."
                f"{function}({call_args});\n    cout.rdbuf(original);\n    cout << nlohmann::json(value).dump();\n}}")
    elif lang=="java":
        args=", ".join(f"g.fromJson(a.get({i}), {typename(t,lang)}.class)" for i,(_,t) in enumerate(sig["params"]))
        has_class = "class Solution" in source
        body = source if has_class else f"class Solution {{\n{source}\n}}"
        return ('import java.util.*;\nimport java.io.*;\nimport com.google.gson.*;\n'+body+
                f'\nclass Driver {{ public static void main(String[] unused) throws Exception {{ Gson g=new Gson(); JsonArray a=JsonParser.parseReader(new InputStreamReader(System.in)).getAsJsonArray(); PrintStream out=System.out; System.setOut(System.err); out.print(g.toJson(new Solution().{function}({args}))); }} }}')

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
    # If job has signature/typed function, use driver (LeetCode format)
    # Only legacy pure-stdio questions without function signature use raw stdio
    stdio = bool(job.problem.package and not job.problem.signature and job.problem.function == "solve")
    code = job.source if stdio else driver(job.language, job.source, job.function, job.problem.signature)
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
        payload = (args[0].encode() if isinstance(args[0], str) else json.dumps(args[0]).encode()) if stdio else json.dumps(args).encode()
        rc,output,log=launch(run,folder,payload,False,job.problem.package.get("execution") if job.problem.package else None)
        if rc:return ("Memory limit exceeded" if rc==-1001 else "Time limit" if rc in (-1002,15,143,152) else "Runtime error"),log or None
        if stdio:return "Returned",output.decode(errors="replace").rstrip()
        try:return "Returned",json.loads(output)
        except (ValueError,UnicodeError,RecursionError):return "Invalid output",None
    return execute,None
