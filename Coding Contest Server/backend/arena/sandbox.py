"""Execute one Python function case in a fresh, resource-limited Linux namespace."""
import ctypes
import errno
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import tempfile
import sys

DRIVER = """import contextlib,json,sys
source,name,args=json.loads(sys.stdin.read())
scope={"__name__":"submission"}
with contextlib.redirect_stdout(sys.stderr):
    exec(compile(source,"submission.py","exec"),scope)
    fn = scope.get(name)
    if fn is None and "Solution" in scope:
        sol = scope["Solution"]()
        fn = getattr(sol, name, None)
    if fn is None:
        raise KeyError(name)
    value=fn(*args)
sys.stdout.write(json.dumps(value,allow_nan=False))
"""

def syscall_filter(fd):
    lib = ctypes.CDLL("libseccomp.so.2")
    lib.seccomp_init.restype = ctypes.c_void_p
    ctx = ctypes.c_void_p(lib.seccomp_init(0x00050000 | errno.EPERM))
    if not ctx:
        raise RuntimeError("seccomp initialization failed")
    try:
        calls = """read write readv writev pread64 close fstat stat lstat newfstatat statx lseek mmap mprotect munmap mremap brk rt_sigaction rt_sigprocmask rt_sigreturn sigaltstack ioctl access faccessat faccessat2 openat readlink readlinkat getdents64 getcwd fcntl dup dup2 dup3 getrandom arch_prctl set_tid_address set_robust_list rseq prlimit64 getrlimit getuid geteuid getgid getegid getpid getppid gettid uname sysinfo futex clock_gettime gettimeofday times sched_getaffinity madvise execve exit exit_group""".split()
        for call in calls:
            nr = lib.seccomp_syscall_resolve_name(call.encode())
            if nr >= 0 and lib.seccomp_rule_add(ctx,0x7fff0000,nr,0) != 0:
                raise RuntimeError("seccomp rule failed")
        if lib.seccomp_export_bpf(ctx,fd) != 0:
            raise RuntimeError("seccomp export failed")
    finally:
        lib.seccomp_release(ctx)
    os.lseek(fd,0,0)

def limits():
    for kind,size in [(resource.RLIMIT_CPU,2),(resource.RLIMIT_AS,192<<20),(resource.RLIMIT_FSIZE,65536),(resource.RLIMIT_NOFILE,32),(resource.RLIMIT_CORE,0)]:
        resource.setrlimit(kind,(size,size))

def execute(source,function,args):
    with tempfile.TemporaryFile() as sec,tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
        syscall_filter(sec.fileno())
        cmd = ["bwrap","--unshare-all","--unshare-user","--disable-userns","--die-with-parent","--as-pid-1","--new-session","--cap-drop","ALL","--clearenv",
               "--dir","/usr/bin","--ro-bind","/usr/bin/python3","/usr/bin/python3","--ro-bind","/usr/lib","/usr/lib","--symlink","usr/lib","/lib","--symlink","usr/lib64","/lib64","--ro-bind","/usr/lib64","/usr/lib64","--seccomp",str(sec.fileno()),"--","/usr/bin/python3","-I","-S","-B","-c",DRIVER]
        try:
            proc = subprocess.run(cmd,input=json.dumps([source,function,args]).encode(),stdout=out,stderr=err,
                                  timeout=4,preexec_fn=limits,pass_fds=(sec.fileno(),))
        except subprocess.TimeoutExpired:
            return "Time limit",None
        err.seek(0)
        log = err.read(65536).decode(errors="replace")
        if proc.returncode:
            if log.startswith("bwrap:"):
                raise RuntimeError("Sandbox unavailable: "+log[:200])
            if proc.returncode in (-signal.SIGKILL,-signal.SIGXCPU,128+signal.SIGKILL,128+signal.SIGXCPU):
                return "Time limit",None
            return "Runtime error",log[-2000:]
        out.seek(0)
        try:
            return "Returned",json.load(out)
        except (UnicodeError,ValueError,RecursionError):
            return "Invalid output",None
