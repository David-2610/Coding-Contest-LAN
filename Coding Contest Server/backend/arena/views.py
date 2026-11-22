import json
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import JsonResponse,HttpResponseBadRequest
from django.shortcuts import get_object_or_404,render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from .languages import LANGUAGES,starter
from .engine import standings
from .models import Contest,Draft,Entry,Job,Problem

def error(msg,code=400):
    return JsonResponse({"error":msg},status=code)

@ensure_csrf_cookie
@login_required
def home(request):
    return render(request,"workspace.html")

@login_required
def workspace(request):
    entries=Entry.objects.filter(user=request.user).select_related("contest")
    entry=(entries.filter(contest_id=request.GET["contest"]) if request.GET.get("contest") else entries.order_by("-contest__starts")).first()
    if not entry: return error("This account has no contest entry.",403)
    contest=entry.contest
    problems=[]
    if entry.acknowledged and contest.stage not in ("Draft","Scheduled","Waiting Room") and timezone.now()>=contest.starts:
        for p in Problem.objects.filter(contest=contest,published=True).order_by("id"):
            languages={}
            for lang in LANGUAGES:
                draft=Draft.objects.filter(entry=entry,problem=p,language=lang).first()
                languages[lang]=dict(source=draft.source if draft else starter(p,lang),revision=draft.revision if draft else 0)
            problems.append(dict(id=p.pk,external_id=p.external_id,title=p.title,statement=p.statement,function=p.function,signature=p.signature,details={k:p.package[k] for k in ("difficulty","topics","examples","inputFormat","outputFormat","constraints","execution","scoring") if k in p.package},samples=[c for c in p.cases if c.get("sample")],
                                 languages=languages,**languages["python"]))
    return JsonResponse(dict(eligible=entry.eligible,reason=entry.decision_reason,entry=entry.pk,name=entry.display,enrollment=entry.enrollment,contest=contest.pk,title=contest.title,ends=contest.ends.isoformat(),problems=problems))

@login_required
@require_POST
@transaction.atomic
def action(request,pid,mode):
    if mode not in ("draft","run","submit"): return error("Unknown action",404)
    p=get_object_or_404(Problem,pk=pid,published=True)
    contest=Contest.objects.select_for_update().get(pk=p.contest_id)
    entry=get_object_or_404(Entry,user=request.user,contest=contest)
    try: data=json.loads(request.body)
    except ValueError: return error("Invalid JSON")
    if not isinstance(data,dict): return error("Expected a JSON object")
    lang=data.get("language","python")
    if lang not in LANGUAGES:return error("Unknown language")
    source=data.get("source")
    if not isinstance(source,str) or len(source.encode())>48000: return error("Source exceeds 48 KB or is missing")
    token=data.get("token","")
    if mode!="draft":
        if not isinstance(token,str) or len(token)!=36: return error("Missing request ID")
        prior=Job.objects.filter(entry=entry,token=token).first()
        if prior:
            if prior.kind!=mode or prior.problem_id!=pid or prior.source!=source or prior.language!=lang: return error("Request ID conflict",409)
            return JsonResponse({"id":prior.pk})
    now=timezone.now()
    if not entry.acknowledged or contest.stage not in ("Active","automatic") or not entry.eligible or not contest.starts<=now<contest.ends: return error("Contest closed for editing",403)
    if mode=="draft":
        draft=Draft.objects.filter(entry=entry,problem=p,language=lang).first()
        rev=draft.revision if draft else 0
        if data.get("revision")!=rev: return error("Draft changed in another tab. Copy your text before reloading.",409)
        Draft.objects.update_or_create(entry=entry,problem=p,language=lang,defaults=dict(source=source,revision=rev+1))
        return JsonResponse({"revision":rev+1})
    if Job.objects.filter(entry=entry,kind=mode,state__in=["queued","running"]).count()>=3:
        return error("Three requests pending. Try again after one finishes.",429)
    cases=p.cases
    if mode=="run":
        cases=[c for c in cases if c["sample"]]
        extra=data.get("tests",[])
        if not isinstance(extra,list) or len(extra)>12: return error("Up to 12 saved tests")
        for c in extra:
            if not isinstance(c,dict) or not isinstance(c.get("args"),list) or "expected" not in c: return error("Invalid test")
            if p.package and (len(c["args"])!=1 or not isinstance(c["args"][0],str) or not isinstance(c["expected"],str)):return error("Expected stdin and stdout strings.")
            cases.append(dict(args=c["args"],expected=c["expected"],sample=True))
    if not cases: return error("No cases configured")
    job=Job.objects.create(entry=entry,problem=p,language=lang,kind=mode,source=source,token=token,cases=cases,function=p.function,received=now)
    return JsonResponse({"id":job.pk},status=201)

@login_required
def result(request,jid):
    job=get_object_or_404(Job,pk=jid,entry__user=request.user)
    result = job.result
    if job.kind == "submit" and result and result.get("cases"):
        first_failure = next((case for case in result["cases"] if case["status"] != "Passed"), None)
        result = {**result, "cases": [first_failure] if first_failure else []}
    if result:
        result={**result,"cases":[row if job.cases[row["number"]-1]["sample"] else
            {k:row[k] for k in ("number","status")} for row in result["cases"]]}
    return JsonResponse(dict(state=job.state,result=result))

def board(request,cid):
    contest=get_object_or_404(Contest,pk=cid)
    return JsonResponse(contest.final if contest.final is not None else standings(contest))

def export(request,cid):
    if not request.user.is_authenticated or not request.user.is_staff:return error("Organizer access required",403)
    c=get_object_or_404(Contest,pk=cid)
    if c.final is None: return error("Final standings pending",409)
    response=JsonResponse(c.final)
    response["Content-Disposition"]=f'attachment; filename="contest-{cid}-final.json"'
    return response

def projector(request,cid):
    get_object_or_404(Contest,pk=cid)
    return render(request,"projector.html",{"cid":cid})

@login_required
def history(request,pid):
    jobs=Job.objects.filter(problem_id=pid,entry__user=request.user,kind="submit").order_by("-received")[:20]
    return JsonResponse({"submissions":[{"id":job.pk,"received":job.received.isoformat(),"status":(job.result or {}).get("verdict",job.state)} for job in jobs]})
