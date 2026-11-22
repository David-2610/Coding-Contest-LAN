import io
import json
from datetime import timedelta
from functools import wraps
from django import forms
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import models, transaction, IntegrityError
from django.db.models import Count, Max
from django.http import HttpResponse,JsonResponse
from django.shortcuts import get_object_or_404,render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from PIL import Image,ImageOps,UnidentifiedImageError
from .models import Contest,Entry,Profile,ConnectionEvent,Problem,Job
from .engine import standings
from .views import error

import os
GRACE=timedelta(seconds=int(os.environ.get("CONTEST_DISCONNECT_SECONDS","40")))
UNSTABLE=timedelta(seconds=int(os.environ.get("CONTEST_UNSTABLE_SECONDS","20")))

@ensure_csrf_cookie
def site(request,**kwargs):
    if request.path=="/" and not request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect("/login/")
    return render(request,"workspace.html")

def organizer(fn):
    @wraps(fn)
    def view(request,*args,**kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:return error("Organizer access required",403)
        return fn(request,*args,**kwargs)
    return view

class Registration(forms.Form):
    username=forms.RegexField(r'^[\w.@+-]+$',max_length=150)
    full_name=forms.CharField(max_length=150)
    enrollment=forms.CharField(max_length=64)
    email=forms.EmailField(max_length=254)
    phone=forms.RegexField(r'^\+?[0-9 ()-]{6,29}$',max_length=30)
    password=forms.CharField(min_length=8,max_length=128,strip=False)
    def clean_password(self):
        value=self.cleaned_data['password']
        validate_password(value)
        return value

def thumbnail(photo):
    if photo is None:return b""
    if photo.size>2*1024*1024:raise ValueError("Choose an image smaller than 2 MB.")
    try:
        with Image.open(photo) as im:
            if im.format not in ("JPEG","PNG","WEBP") or im.width*im.height>8_000_000:raise ValueError("Choose a JPEG, PNG or WebP up to 8 megapixels.")
            im=ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((256,256));out=io.BytesIO();im.save(out,"JPEG",quality=85);return out.getvalue()
    except (Image.DecompressionBombError,UnidentifiedImageError,OSError) as e:raise ValueError("Invalid image.") from e

@require_POST
def signup(request):
    if request.user.is_authenticated:return error("Sign out before registering.",409)
    f=Registration(request.POST)
    if not f.is_valid():return error(" ".join(f"{k}: {' '.join(v)}" for k,v in f.errors.items()))
    d=f.cleaned_data
    try:pic=thumbnail(request.FILES.get("photo"))
    except ValueError as e:return error(str(e))
    try:
        with transaction.atomic():
            user=get_user_model().objects.create_user(username=d['username'],email=d['email'],password=d['password'])
            Profile.objects.create(user=user,full_name=d['full_name'],enrollment=d['enrollment'],phone=d['phone'],photo=pic)
    except IntegrityError:return error("This username or enrollment number is already registered.",409)
    login(request,user)
    return JsonResponse({"ok":True},status=201)

@require_POST
def signin(request):
    from django.core.cache import cache
    import logging
    key="login-attempts:"+request.META.get("REMOTE_ADDR","unknown")
    cache.add(key,0,300)
    if cache.incr(key)>30:
        logging.getLogger(__name__).warning("Contest login rate limit reached")
        return error("Too many attempts. Try again in five minutes.",429)
    identity=request.POST.get("username",request.POST.get("enrollment","")).strip()
    credential=request.POST.get("password",request.POST.get("pin",""))
    if identity=="organizer" and request.META.get("REMOTE_ADDR") not in ("::1","127.0.0.1"):
        return error("Open the organizer login on the Acer.",403)
    if identity!="organizer":
        with transaction.atomic():
            profile = Profile.objects.select_for_update().select_related("user").filter(
                user__is_active=True, user__is_staff=False, user__is_superuser=False
            ).exclude(ecode_batch="").filter(enrollment=identity).first()
            now = timezone.now()
            if profile and not (profile.pin_retry and profile.pin_retry > now):
                if profile.user.check_password(credential):
                    profile.pin_failures, profile.pin_retry = 0, None
                    profile.save(update_fields=["pin_failures","pin_retry"])
                    login(request,profile.user)
                    return JsonResponse({"staff":False})
                profile.pin_failures += 1
                if profile.pin_failures >= 5:
                    profile.pin_failures, profile.pin_retry = 0, now + timedelta(minutes=5)
                profile.save(update_fields=["pin_failures","pin_retry"])
        return error("Check your enrollment and PIN, or try again later.",401)
    if Profile.objects.filter(user__username__iexact=request.POST.get("username","")).exclude(ecode_batch="").exists():
        return error("Use enrollment and PIN for an E-Code account.",401)
    u=authenticate(request,username=request.POST.get("username",""),password=request.POST.get("password",""))
    if u is None or not u.is_staff or u.username!="organizer":
        logging.getLogger(__name__).warning("Organizer authentication failed")
        return error("Username or password is incorrect.",401)
    logging.getLogger(__name__).info("Organizer authenticated")
    login(request,u);return JsonResponse({"staff":u.is_staff})

@require_POST
def signout(request):
    logout(request)
    return JsonResponse({"ok":True})

def account_photo(request):
    if not request.user.is_authenticated:return error("Sign in required",403)
    profile=get_object_or_404(Profile,user=request.user)
    response=HttpResponse(bytes(profile.photo),content_type="image/jpeg")
    response["Cache-Control"]="private, no-store"
    return response

def session_info(request):
    user=request.user
    rows=[]
    for c in Contest.objects.order_by("-starts"):
        # Never expose Question Bank Repository or Draft contests to students/non-staff
        if (c.title == "Question Bank Repository" or c.stage == "Draft") and not user.is_staff:
            continue
        # Also hide Question Bank Repository completely from client lobby
        if c.title == "Question Bank Repository":
            continue
        now=timezone.now()
        rows.append(dict(
            id=c.pk,
            title=c.title,
            description=c.description,
            banner=c.banner_path or c.banner_url,
            duration=c.duration_minutes,
            totalProblems=c.total_problems,
            problemCount=c.problem_set.count(),
            batchTarget=c.batch_target,
            ecodeContestId=c.ecode_contest_id,
            ecodeEventId=c.ecode_event_id,
            syncStatus=c.sync_status,
            syncedAt=c.synced_at.isoformat() if c.synced_at else None,
            starts=c.starts.isoformat(),
            ends=c.ends.isoformat(),
            state=c.stage if c.stage in ("Draft","Scheduled","Waiting Room") else "Upcoming" if now<c.starts else "Ended" if now>=c.ends else "Live",
            acknowledged=user.is_authenticated and Entry.objects.filter(contest=c,user=user,acknowledged__isnull=False).exists(),
            joined=user.is_authenticated and Entry.objects.filter(contest=c,user=user).exists()
        ))
    profile=Profile.objects.filter(user=user).first() if user.is_authenticated else None
    return JsonResponse(dict(user=user.username if user.is_authenticated else None,name=profile.full_name if profile else "",photo=bool(profile and profile.photo),details=({"batch":profile.ecode_batch if profile else "", "email":user.email,"enrollment":profile.enrollment if profile else "","phone":profile.phone if profile else ""} if user.is_authenticated else {}),
                             staff=user.is_authenticated and user.is_staff,contests=rows))

@require_POST
@transaction.atomic
def enter(request,cid):
    if not request.user.is_authenticated or request.user.is_staff:return error("Sign in as a candidate.",403)
    c=get_object_or_404(Contest.objects.select_for_update(),pk=cid)
    if c.stage=="Draft" or (c.stage in ("automatic","Active","Ended") and not c.starts<=timezone.now()<c.ends):return error("Contest is outside its scheduled window.",403)
    existing=Entry.objects.filter(contest=c,user=request.user).first()
    if not existing or not existing.acknowledged:
        try: consent=json.loads(request.body or b"{}")
        except ValueError:return error("Invalid acknowledgment.")
        if not isinstance(consent,dict) or consent.get("agree") is not True:return error("Read and acknowledge the rules first.",403)
    if existing:
        if not existing.acknowledged:existing.acknowledged=timezone.now();existing.save(update_fields=["acknowledged"])
    else:
        profile=Profile.objects.filter(user=request.user).first()
        if profile is None:return error("An organizer must enroll this legacy account.",403)
        if Entry.objects.filter(contest=c,enrollment=profile.enrollment).exists():return error("Enrollment is already assigned in this contest.",409)
        Entry.objects.create(acknowledged=timezone.now(),contest=c,user=request.user,enrollment=profile.enrollment,display=profile.full_name)
    return JsonResponse({"ok":True})

def expire(entry,now):
    if entry.presence=="Online" and entry.last_seen and now-entry.last_seen>GRACE:
        entry.presence="Disconnected";entry.save(update_fields=["presence"])
        ConnectionEvent.objects.create(entry=entry,kind="Heartbeat lost")

@require_POST
@transaction.atomic
def heartbeat(request,cid):
    if not request.user.is_authenticated:return error("Sign in required",403)
    e=get_object_or_404(Entry.objects.select_for_update(),contest_id=cid,user=request.user)
    now=timezone.now()
    if not e.acknowledged or (e.contest.stage not in ("Scheduled","Waiting Room") and not e.contest.starts<=now<e.contest.ends):return error("Contest closed",403)
    expire(e,now)
    if e.presence!="Online":ConnectionEvent.objects.create(entry=e,kind="Reconnected" if e.last_seen else "Connected")
    e.presence="Online";e.last_seen=now;e.save(update_fields=["presence","last_seen"])
    return JsonResponse({"eligible":e.eligible,"reason":e.decision_reason})

@organizer
def monitor(request,cid):
    c=get_object_or_404(Contest,pk=cid);now=timezone.now()
    entries=list(Entry.objects.filter(contest=c).select_related("user").order_by("display"))
    scores=standings(c)["rows"]
    counts={r['entry']:r['count'] for r in Job.objects.filter(entry__contest=c,kind="submit").values('entry').annotate(count=Count('id'))}
    rows=[]
    reconnects=dict(ConnectionEvent.objects.filter(entry__contest=c,kind="Reconnected").values_list("entry").annotate(n=Count("id")))
    from django.db.models import Max
    live_since=dict(ConnectionEvent.objects.filter(entry__contest=c,kind__in=("Connected","Reconnected")).values_list("entry").annotate(at=Max("at")))
    for e in entries:
        rows.append(dict(id=e.pk,name=e.display,username=e.user.username if e.user else "",enrollment=e.enrollment,reconnects=reconnects.get(e.pk,0),missed=max(0,int((now-e.last_seen).total_seconds()//10)-1) if e.last_seen else None,connectedSeconds=max(0,int((e.last_seen-live_since[e.pk]).total_seconds())) if live_since.get(e.pk) and e.last_seen else None,presence=("Unstable" if e.presence=="Online" and e.last_seen and now-e.last_seen>UNSTABLE else e.presence),last=e.last_seen,eligible=e.eligible,submits=counts.get(e.pk,0)))
    events=list(ConnectionEvent.objects.filter(entry__contest=c).order_by("-id").values("id","at","kind","entry__id","entry__display")[:100])
    jobs=[dict(id=j.pk,entry__display=j.entry.display if j.entry else "Unknown",problem__title=j.problem.title if j.problem else "Unknown",language=j.language,verdict=(j.result or {}).get("verdict",j.state)) for j in Job.objects.filter(entry__contest=c,kind__in=["submit","archive"]).select_related("entry","problem").defer("source","cases").order_by("-received")[:30]]
    import subprocess
    from django.conf import settings
    workers_file = settings.DATA / "judge-workers"
    target_count = 4
    if workers_file.exists():
        try: target_count = int(workers_file.read_text().strip())
        except Exception: pass
    slots = []
    active_count = 0
    for i in range(1, target_count + 1):
        is_up = subprocess.run(["systemctl", "--user", "is-active", "--quiet", f"coding-contest-pilot-judge-{i}"]).returncode == 0
        slots.append({"slot": i, "active": is_up})
        if is_up: active_count += 1
    queued_count = Job.objects.filter(state="queued").count()
    judge_info = {"target": target_count, "active": active_count, "slots": slots}
    problems = []
    for p in c.problem_set.order_by("order", "id"):
        diff = p.package.get("difficulty") if p.package else None
        max_score = p.package.get("scoring", {}).get("maxScore") if p.package else None
        test_count = len(p.cases) if isinstance(p.cases, list) else 0
        problems.append(dict(
            id=p.pk,
            title=p.title,
            published=p.published,
            externalId=p.external_id or "",
            order=p.order,
            difficulty=diff or "Easy",
            maxScore=max_score or 100,
            testCount=test_count
        ))
    return JsonResponse(dict(activeJobs=Job.objects.filter(entry__contest=c,state="running").count(),judge=judge_info,judgeActive=active_count>0,queuedJobs=queued_count,rows=rows,events=events,scores=scores,jobs=jobs,submissions=sum(counts.values()),problems=problems,final=c.final is not None))

@organizer
@require_POST
@transaction.atomic
def reorder_problems(request, cid):
    c = get_object_or_404(Contest.objects.select_for_update(), pk=cid)
    try:
        data = json.loads(request.body.decode() if request.body else "{}")
    except Exception:
        data = request.POST.dict()
    order = data.get("order", [])
    if not isinstance(order, list):
        return error("Expected a list of problem IDs")
    for idx, pid in enumerate(order, start=1):
        c.problem_set.filter(pk=pid).update(order=idx)
    return JsonResponse({"ok": True, "count": len(order)})

@organizer
@require_POST
def judge_scale(request):
    try:
        data = json.loads(request.body.decode() if request.body else "{}")
    except Exception:
        data = request.POST.dict()
    target = int(data.get("count") or data.get("workers") or 4)
    target = max(1, min(12, target))
    from django.conf import settings
    import subprocess
    server_script = settings.BASE / "scripts" / "server"
    subprocess.run(["bash", str(server_script), "scale", str(target)], timeout=12)
    return JsonResponse({"ok": True, "target": target})

@organizer
@require_POST
def judge_restart(request):
    import subprocess
    from django.conf import settings
    from .models import Job
    Job.objects.filter(state="running").update(state="queued")
    server_script = settings.BASE / "scripts" / "server"
    subprocess.run(["bash", str(server_script), "restart"], timeout=12)
    return JsonResponse({"ok": True})

@organizer
def judge_status(request):
    from django.conf import settings
    import subprocess
    from .models import Job
    workers_file = settings.DATA / "judge-workers"
    target_count = 4
    if workers_file.exists():
        try: target_count = int(workers_file.read_text().strip())
        except Exception: pass
    slots = []
    active_count = 0
    for i in range(1, target_count + 1):
        is_up = subprocess.run(["systemctl", "--user", "is-active", "--quiet", f"coding-contest-pilot-judge-{i}"]).returncode == 0
        slots.append({"slot": i, "active": is_up})
        if is_up: active_count += 1
    return JsonResponse({
        "target": target_count,
        "active": active_count,
        "slots": slots,
        "queued": Job.objects.filter(state="queued").count(),
        "running": Job.objects.filter(state="running").count()
    })

@organizer
@require_POST
def create_contest(request):
    try:
        data = json.loads(request.body.decode() if request.body else "{}")
    except Exception:
        data = request.POST.dict()
    
    title = data.get("title", "").strip()
    if not title:
        return error("Supply a contest title.")
    
    duration = int(data.get("durationMinutes") or 60)
    starts_str = data.get("starts")
    ends_str = data.get("ends")
    
    now = timezone.now()
    if starts_str and ends_str:
        from django.utils.dateparse import parse_datetime
        starts = parse_datetime(starts_str) or now
        ends = parse_datetime(ends_str) or (starts + timedelta(minutes=duration))
    else:
        starts = now
        ends = now + timedelta(minutes=duration)
    
    if starts >= ends:
        ends = starts + timedelta(minutes=duration)
    
    stage = data.get("stage", "Waiting Room")
    if stage not in ("Draft", "Scheduled", "Waiting Room", "Active"):
        stage = "Waiting Room"
        
    c = Contest.objects.create(
        title=title,
        description=data.get("description", ""),
        duration_minutes=duration,
        starts=starts,
        ends=ends,
        stage=stage
    )
    return JsonResponse({"id": c.pk, "ok": True}, status=201)

@organizer
@require_POST
@transaction.atomic
def delete_contest(request, cid):
    c = get_object_or_404(Contest.objects.select_for_update(), pk=cid)
    if c.title == "Question Bank Repository":
        return error("The Question Bank Repository cannot be deleted.", 403)
    
    # Safe delete dependent objects
    from .models import Draft, Job, Entry, ConnectionEvent, Decision
    Draft.objects.filter(entry__contest=c).delete()
    Job.objects.filter(entry__contest=c).delete()
    c.problem_set.all().delete()
    Decision.objects.filter(entry__contest=c).delete()
    ConnectionEvent.objects.filter(entry__contest=c).delete()
    Entry.objects.filter(contest=c).delete()
    
    c.delete()
    return JsonResponse({"ok": True, "deleted": cid})

@organizer
@require_POST
@transaction.atomic
def author(request,cid):
    c=get_object_or_404(Contest.objects.select_for_update(),pk=cid)
    try:
        from jsonschema import validate, ValidationError as SchemaError
        raw=json.loads(request.body)
        items = raw if isinstance(raw, list) else [raw]
        if not items:
            return error("Supply at least one question.", 400)
        from django.conf import settings
        schema=json.loads((settings.BASE.parent/"frontend/dist/question-schema.json").read_text())
        if c.stage in ("Active","Ended") or (c.stage=="automatic" and timezone.now()>=c.starts):
            return error("Questions are locked once the round begins.",409)
        
        imported_ids = []
        for d in items:
            validate(d,schema)
            ids=[t.get("id") for t in d.get("testCases", []) if "id" in t]
            if len(set(ids))!=len(ids):return error(f"Test identifiers must be unique in {d.get('id', 'question')}.")
            if "topics" in d:
                d["topics"]=list(dict.fromkeys(" ".join(t.split()).casefold() for t in d["topics"]))
            
            # Extract function and signature
            function_name = d.get("function")
            sig = d.get("signature")
            
            # Format test cases
            cases = []
            for t in d.get("testCases", []):
                # LeetCode format: "args" list and "expected"
                if "args" in t and "expected" in t:
                    args = t["args"] if isinstance(t["args"], list) else [t["args"]]
                    expected = t["expected"]
                else:
                    # Legacy fallback
                    args = [t.get("input", "")]
                    expected = t.get("expectedOutput", "")
                sample = t.get("visibility", "public") == "public" or bool(t.get("sample", False))
                cases.append(dict(args=args, expected=expected, sample=sample))
            
            p=Problem.objects.filter(contest=c, external_id=d["id"]).first()
            if p and request.GET.get("replace")!="1":
                return error(f"Question ID '{d['id']}' already exists in this contest. Select replace to overwrite.",409)
            p=p or Problem(contest=c,external_id=d["id"])
            p.title=d["title"]
            p.statement=d.get("description", "")
            p.package=d
            p.cases=cases
            p.published=True
            
            # Function name and starter code
            p.function = function_name or "solve"
            if sig:
                p.signature = sig
            
            py_starter = d.get("languages", {}).get("python3", {}).get("starterCode")
            if py_starter:
                p.starter = py_starter
            else:
                from .languages import starter as gen_starter
                p.starter = gen_starter(p, "python")
            
            p.full_clean()
            p.save()
            imported_ids.append(p.pk)
    except SchemaError as e:return error(f"{e.json_path}: {e.message}"[:400])
    except (ValidationError,KeyError,ValueError,TypeError,IntegrityError) as e:return error(str(e))
    return JsonResponse({"ids":imported_ids, "count":len(imported_ids), "id":imported_ids[0]},status=201)

@organizer
def question_bank(request):
    """List all unique questions available across all contests (or bank) to import into any contest."""
    seen = set()
    questions = []
    for p in Problem.objects.select_related("contest").order_by("-id"):
        key = p.external_id or p.title
        if key in seen:
            continue
        seen.add(key)
        questions.append({
            "id": p.pk,
            "externalId": p.external_id or f"P{p.pk}",
            "title": p.title,
            "function": p.function,
            "signature": p.signature,
            "difficulty": p.package.get("difficulty", "Normal") if p.package else "Normal",
            "maxScore": p.package.get("scoring", {}).get("maxScore", 100) if p.package else 100,
            "topics": p.package.get("topics", []) if p.package else [],
            "testCount": len(p.cases) if isinstance(p.cases, list) else 0,
            "fromContest": p.contest.title,
            "fromContestId": p.contest.pk
        })
    return JsonResponse({"questions": questions})

@organizer
@require_POST
def bank_upload(request):
    """Upload bulk questions directly to the Question Bank (associated with bank or active contest)."""
    try:
        from jsonschema import validate, ValidationError as SchemaError
        raw = json.loads(request.body)
        items = raw if isinstance(raw, list) else [raw]
        if not items:
            return error("Supply at least one question.", 400)
        from django.conf import settings
        schema = json.loads((settings.BASE.parent/"frontend/dist/question-schema.json").read_text())
        
        # Pick or create a designated Bank contest
        bank_contest, _ = Contest.objects.get_or_create(
            title="Question Bank Repository",
            defaults={
                "stage": "Draft",
                "starts": timezone.now() - timedelta(days=365),
                "ends": timezone.now() + timedelta(days=365*10),
            }
        )
        
        imported = []
        with transaction.atomic():
            for d in items:
                validate(d, schema)
                ids = [t.get("id") for t in d.get("testCases", []) if "id" in t]
                if len(set(ids)) != len(ids):
                    return error(f"Test identifiers must be unique in {d.get('id', 'question')}.")
                if "topics" in d:
                    d["topics"] = list(dict.fromkeys(" ".join(t.split()).casefold() for t in d["topics"]))
                
                function_name = d.get("function") or "solve"
                sig = d.get("signature")
                cases = []
                for t in d.get("testCases", []):
                    if "args" in t and "expected" in t:
                        args = t["args"] if isinstance(t["args"], list) else [t["args"]]
                        expected = t["expected"]
                    else:
                        args = [t.get("input", "")]
                        expected = t.get("expectedOutput", "")
                    sample = t.get("visibility", "public") == "public" or bool(t.get("sample", False))
                    cases.append(dict(args=args, expected=expected, sample=sample))
                
                p = Problem.objects.filter(contest=bank_contest, external_id=d["id"]).first()
                if not p:
                    p = Problem(contest=bank_contest, external_id=d["id"])
                
                p.title = d["title"]
                p.statement = d.get("description", "")
                p.package = d
                p.cases = cases
                p.published = True
                p.function = function_name
                if sig:
                    p.signature = sig
                py_starter = d.get("languages", {}).get("python3", {}).get("starterCode")
                if py_starter:
                    p.starter = py_starter
                else:
                    from .languages import starter as gen_starter
                    p.starter = gen_starter(p, "python")
                p.full_clean()
                p.save()
                imported.append(p.pk)
        
        return JsonResponse({"ok": True, "count": len(imported), "ids": imported}, status=201)
    except SchemaError as e:
        return error(f"{e.json_path}: {e.message}"[:400])
    except Exception as e:
        return error(str(e))

@organizer
@require_POST
@transaction.atomic
def copy_from_bank(request, cid):
    """Copy one or more existing questions from question bank/other contests into the target contest."""
    c = get_object_or_404(Contest.objects.select_for_update(), pk=cid)
    if c.stage in ("Active", "Ended") or (c.stage == "automatic" and timezone.now() >= c.starts):
        return error("Questions are locked once the round begins.", 409)
    try:
        data = json.loads(request.body or "{}")
        pids = data.get("problemIds", [])
        replace = bool(data.get("replace", False))
        if not pids:
            return error("Select at least one problem to copy.")
        
        max_order = c.problem_set.aggregate(m=models.Max("order"))["m"] or 0
        copied_ids = []
        for idx, pid in enumerate(pids, start=1):
            source = Problem.objects.filter(pk=pid).first()
            if not source:
                continue
            ext_id = source.external_id
            existing = Problem.objects.filter(contest=c, external_id=ext_id).first() if ext_id else None
            if existing:
                if not replace:
                    continue
                target = existing
            else:
                target = Problem(contest=c, external_id=ext_id)
            
            target.title = source.title
            target.statement = source.statement
            target.package = source.package
            target.cases = source.cases
            target.function = source.function
            target.starter = source.starter
            target.signature = source.signature
            target.published = True
            target.order = max_order + idx
            target.save()
            copied_ids.append(target.pk)
        
        return JsonResponse({"ok": True, "count": len(copied_ids), "ids": copied_ids})
    except Exception as e:
        return error(f"Failed to copy questions: {e}", 500)

@organizer
@require_POST
@transaction.atomic
def remove_problem_from_contest(request, cid, pid):
    """Remove a problem from a specific contest while preserving it in the master Question Bank."""
    c = get_object_or_404(Contest.objects.select_for_update(), pk=cid)
    # Only lock removal during an ongoing live Active round
    now = timezone.now()
    if c.stage == "Active" and c.starts <= now < c.ends:
        return error("Questions are locked during an active round.", 409)
    if c.stage == "automatic" and c.starts <= now < c.ends:
        return error("Questions are locked during an active round.", 409)
    
    p = get_object_or_404(Problem, pk=pid, contest=c)
    
    # Ensure it exists in Question Bank Repository before removing from this contest
    bank_contest, _ = Contest.objects.get_or_create(
        title="Question Bank Repository",
        defaults={
            "stage": "Draft",
            "starts": timezone.now() + timedelta(days=365),
            "ends": timezone.now() + timedelta(days=365*10)
        }
    )
    if c != bank_contest:
        bank_problem = Problem.objects.filter(contest=bank_contest, external_id=p.external_id).first() if p.external_id else None
        if not bank_problem:
            Problem.objects.create(
                contest=bank_contest,
                external_id=p.external_id,
                title=p.title,
                statement=p.statement,
                package=p.package,
                cases=p.cases,
                function=p.function,
                starter=p.starter,
                signature=p.signature,
                published=True
            )
    
    # Delete dependent drafts/jobs in this contest to avoid ProtectedError
    from .models import Draft, Job
    Draft.objects.filter(problem=p).delete()
    Job.objects.filter(problem=p).delete()
    p.delete()
    
    return JsonResponse({"ok": True, "removed": pid})

@organizer
def job_detail(request,jid):
    job=get_object_or_404(Job,pk=jid)
    return JsonResponse({"source":job.source,"result":job.result})

@organizer
@require_POST
@transaction.atomic
def eligibility(request,eid):
    entry=get_object_or_404(Entry.objects.select_for_update(),pk=eid)
    if entry.contest.final is not None:return error("Final results already published.",409)
    why=request.POST.get("reason","").strip()
    if not why or len(why)>800:return error("Give a reason of up to 800 characters.")
    action=request.POST.get("action")
    if action not in ("reinstate","disqualify"):return error("Invalid eligibility action.")
    entry.eligible=action=="reinstate"
    entry.decision_reason=f"{request.user.username} · {timezone.now().isoformat()} · {why}"
    entry.save(update_fields=["eligible","decision_reason"])
    from .models import Decision
    Decision.objects.create(entry=entry,actor=request.user,eligible=entry.eligible,reason=why)
    return JsonResponse({"ok":True})

@require_POST
@transaction.atomic
def edit_profile(request):
    if not request.user.is_authenticated or request.user.is_staff:return error("Candidate sign-in required",403)
    user=request.user
    if Profile.objects.filter(user=user).exclude(ecode_batch="").exists():return error("This profile is managed by E-Code.",403)
    class Details(forms.Form):
        full_name=forms.CharField(max_length=150)
        email=forms.EmailField(max_length=254)
        phone=forms.RegexField(r'^\+?[0-9 ()-]{6,29}$',max_length=30)
        enrollment=forms.CharField(max_length=64)
    f=Details(request.POST)
    if not f.is_valid():return error("Check your name, enrollment, email and phone.")
    d=f.cleaned_data
    if Profile.objects.exclude(user=user).filter(enrollment=d["enrollment"]).exists():return error("Enrollment already registered.",409)
    existing=Profile.objects.filter(user=user).first()
    if existing and existing.enrollment!=d['enrollment'] and Entry.objects.filter(user=user).exists():return error("An enrolled contestant's enrollment number is locked.")
    try:
        pic=thumbnail(request.FILES.get("photo"))
        with transaction.atomic():
            defaults=dict(full_name=d['full_name'],enrollment=d['enrollment'],phone=d['phone'])
            if pic:defaults["photo"]=pic
            Profile.objects.update_or_create(user=user,defaults=defaults)
    except ValueError as e:return error(str(e))
    except IntegrityError:return error("Enrollment already registered.",409)
    user.email=d['email'];user.save(update_fields=["email"])
    return JsonResponse({"ok":True})

@organizer
def roster(request):
    rows = list(Profile.objects.exclude(ecode_batch="").filter(user__is_active=True)
                .order_by("full_name").values("full_name","enrollment","ecode_batch","user__username"))
    return JsonResponse({"students":rows},headers={"Cache-Control":"private, no-store"})

def online_board(request):
    from urllib.request import urlopen
    from urllib.error import URLError
    from urllib.parse import urlencode
    from django.core.cache import cache
    import re
    base = "https://ecode-backend.onrender.com/api/v1/codeclash/leaderboards"
    batch = request.GET.get("batch","all")
    page = request.GET.get("page","1")
    contest = request.GET.get("contest","")
    if not re.fullmatch(r"all|[\w-]{1,50}",batch) or not re.fullmatch(r"[1-9][0-9]{0,4}",page) or not re.fullmatch(r"[\w-]{0,100}",contest):
        return error("Invalid leaderboard selection.",400)
    url = (base+"/batches" if request.GET.get("list")=="1" else base+"/contests/"+contest if contest
           else base+"?"+urlencode(dict(batch=batch,page=page,limit=50)))
    key="ecode-board:"+url
    data=cache.get(key)
    if data is None:
        try:
            with urlopen(url,timeout=10) as response:
                result=json.load(response)
            if result["success"] is not True:raise ValueError
            data=result["data"]
            cache.set(key,data,60)
        except (URLError,OSError,ValueError,TypeError,KeyError):
            return error("Online standings are unavailable. Local contest standings remain available.",503)
    return JsonResponse({"data":data})

@organizer
@require_POST
@transaction.atomic
def transition(request,cid):
    c=get_object_or_404(Contest.objects.select_for_update(),pk=cid)
    target=request.POST.get("stage")
    allowed={"Draft":"Scheduled","Scheduled":"Waiting Room","Waiting Room":"Active","Active":"Ended","Ended":"Waiting Room"}
    if c.stage=="automatic" and c.starts<=timezone.now()<c.ends:allowed["automatic"]="Ended"
    
    # If contest time has expired or stage is Ended/Active past ends, permit restarting to Waiting Room or Scheduled
    now=timezone.now()
    is_expired = c.ends <= now
    is_restart = target in ("Waiting Room", "Scheduled")
    
    if not is_restart and c.stage=="Active" and is_expired and target!="Ended":
        return error("Contest already ended. End it first or restart to Waiting Room.",409)
    if target!=allowed.get(c.stage) and not ((c.stage=="Ended" or is_expired) and target in ("Waiting Room","Scheduled","Active")):
        return error("Invalid contest transition.",409)

    if target=="Active":
        duration=c.ends-c.starts if c.ends>c.starts and not is_expired else timedelta(minutes=c.duration_minutes or 60)
        c.starts=now
        c.ends=now+duration
        c.final=None
        c.final_entries=None
    elif target=="Ended":
        c.ends=now
    elif target in ("Waiting Room","Scheduled"):
        # Resetting or restarting contest with a fresh clock duration
        duration=timedelta(minutes=c.duration_minutes or 60)
        c.starts=now
        c.ends=now+duration
        c.final=None
        c.final_entries=None
    c.stage=target
    c.save()
    return JsonResponse({"ok":True})

@organizer
@require_POST
def fetch_contest_api(request):
    """
    Organizer endpoint to fetch and cache active contest details from E-Code.
    """
    from .ecode_contest import fetch_and_cache_contest, ContestConflictError
    from .ecode_client import EcodeApiError
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return error("Invalid JSON payload.")
    
    contest_id = data.get("contestId")
    event_id = data.get("eventId")
    force = bool(data.get("force", False))
    
    try:
        result = fetch_and_cache_contest(contest_id=contest_id, event_id=event_id, force=force)
        c = result["contest"]
        return JsonResponse({
            "ok": True,
            "created": result["created"],
            "contest": {
                "id": c.pk,
                "title": c.title,
                "ecodeContestId": c.ecode_contest_id,
                "ecodeEventId": c.ecode_event_id,
                "description": c.description,
                "banner": c.banner_path or c.banner_url,
                "starts": c.starts.isoformat(),
                "ends": c.ends.isoformat(),
                "startsLocal": result["startsLocal"],
                "endsLocal": result["endsLocal"],
                "durationMinutes": result["durationMinutes"],
                "totalProblems": result["totalProblems"],
                "batchTarget": result["batchTarget"],
                "timezone": result["timezone"],
                "status": c.ecode_status,
                "stage": c.stage,
                "syncStatus": c.sync_status
            }
        })
    except ContestConflictError as e:
        return error(str(e), 409)
    except EcodeApiError as e:
        return error(f"E-Code API error: {e}", 502)
    except Exception as e:
        return error(f"Failed to fetch contest: {e}", 500)

@organizer
def preview_remote_contest_api(request):
    """
    Organizer endpoint to preview active contest on E-Code without persisting.
    """
    from .ecode_client import fetch_active_contest, EcodeApiError
    contest_id = request.GET.get("contestId")
    event_id = request.GET.get("eventId")
    try:
        data = fetch_active_contest(contest_id=contest_id, event_id=event_id)
        return JsonResponse({"ok": True, "data": data})
    except EcodeApiError as e:
        return error(f"E-Code API error: {e}", 502)
    except Exception as e:
        return error(f"Error fetching remote contest: {e}", 500)

@organizer
def sync_preview_api(request, cid):
    """
    Organizer endpoint to preview final sync payload for a contest.
    """
    from .ecode_contest import generate_sync_payload, ContestSyncError
    c = get_object_or_404(Contest, pk=cid)
    try:
        payload, warnings = generate_sync_payload(c)
        return JsonResponse({
            "ok": True,
            "payload": payload,
            "warnings": warnings,
            "synced": c.sync_status == "SYNCED",
            "syncedAt": c.synced_at.isoformat() if c.synced_at else None
        })
    except ContestSyncError as e:
        return error(str(e), 400)
    except Exception as e:
        return error(f"Could not generate payload: {e}", 500)

@organizer
def readiness_check_api(request, cid):
    """
    Organizer endpoint to check offline LAN contest readiness.
    """
    import subprocess
    c = get_object_or_404(Contest, pk=cid)
    
    # Check problem configuration
    actual_problems = c.problem_set.filter(published=True).count()
    expected_problems = c.total_problems or actual_problems
    problems_ready = actual_problems > 0 and (actual_problems == expected_problems or expected_problems == 0)
    
    # Check roster count
    roster_count = Profile.objects.exclude(ecode_batch="").filter(user__is_active=True).count()
    
    # Check judge service
    judge_active = False
    try:
        res = subprocess.run(["systemctl", "--user", "is-active", "coding-contest-pilot-judge"],
                             capture_output=True, text=True, timeout=2)
        judge_active = res.stdout.strip() == "active"
    except Exception:
        judge_active = False
        
    return JsonResponse({
        "ok": True,
        "contest": {
            "id": c.pk,
            "title": c.title,
            "ecodeContestId": c.ecode_contest_id,
            "stage": c.stage,
            "starts": c.starts.isoformat(),
            "ends": c.ends.isoformat()
        },
        "checks": {
            "ecodeLinked": bool(c.ecode_contest_id),
            "problemsConfigured": problems_ready,
            "problemCounts": {"configured": actual_problems, "expected": expected_problems},
            "rosterImported": roster_count > 0,
            "rosterCount": roster_count,
            "judgeActive": judge_active,
            "offlineReady": bool(c.ecode_contest_id and problems_ready and roster_count > 0 and judge_active)
        }
    })
