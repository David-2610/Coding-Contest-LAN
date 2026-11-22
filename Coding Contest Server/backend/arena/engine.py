from datetime import timezone as dt_timezone
import json
from django.db import transaction
from django.db.models import Case, When, Value, IntegerField
from django.utils import timezone
from .models import Contest,Draft,Entry,Job
from .sandbox import execute

def standings(contest,include_entries=False):
    rows=[]
    points={str(p.pk):p.package.get("scoring",{}).get("maxScore",1) for p in contest.problem_set.all()}
    for entry in Entry.objects.filter(contest=contest,eligible=True):
        solves={}
        for job in Job.objects.filter(entry=entry,kind="submit",state="done",result__verdict="Accepted").order_by("received","id"):
            solves.setdefault(str(job.problem_id),max(0,int((job.received-contest.starts).total_seconds())))
        valid_solves={k:v for k,v in solves.items() if k in points}
        rows.append(dict(name=entry.display,score=sum(points.get(k,0) for k in valid_solves),solved=len(valid_solves),seconds=sum(valid_solves.values()),problems=valid_solves))
        if include_entries:rows[-1]["entry_id"]=entry.pk
    rows.sort(key=lambda r:(-r["score"],r["seconds"],r["name"]))
    previous=None
    for index,row in enumerate(rows,1):
        key=(row["score"],row["seconds"])
        if key!=previous:
            rank=index
        row["rank"]=rank
        previous=key
    return dict(schema=1,contest=contest.title,ends=contest.ends.isoformat(),updated=timezone.now().isoformat(),rows=rows)

@transaction.atomic
def close_contest(cid):
    contest=Contest.objects.select_for_update().get(pk=cid)
    if contest.stage not in ("automatic","Active","Ended") or contest.ends>timezone.now():
        return
    for draft in Draft.objects.filter(entry__contest=contest).select_related("problem"):
        Job.objects.get_or_create(entry=draft.entry,token=(f"archive:{draft.problem_id}" if draft.language=="python" else f"archive:{draft.problem_id}:{draft.language}"),defaults=dict(
            problem=draft.problem,language=draft.language,kind="archive",source=draft.source,received=draft.saved,
            cases=draft.problem.cases,function=draft.problem.function))
    official=Job.objects.filter(entry__contest=contest,kind="submit")
    if contest.final is None and not official.filter(state__in=("queued","running")).exists():
        contest.final=standings(contest,include_entries=True)
        contest.final_entries=[row.pop("entry_id") for row in contest.final["rows"]]
        contest.save(update_fields=["final","final_entries"])

def evaluate(job):
    # Python with LeetCode format (Solution class or function)
    if job.language=="python" and (not job.problem.package or job.problem.signature):
        return evaluate_cases(job,lambda args:execute(job.source,job.function,args))
    from .languages import compiled
    from pathlib import Path
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as folder:
        runner,diagnostic=compiled(job,Path(folder))
        if diagnostic: return dict(verdict="Compile error",diagnostic=diagnostic,cases=[],total=len(job.cases),passed=0,skipped=len(job.cases))
        return evaluate_cases(job,runner)

def evaluate_cases(job,runner):
    rows=[]
    total=len(job.cases)
    is_stdio = bool(job.problem.package and not job.problem.signature and job.problem.function == "solve")
    for i,case in enumerate(job.cases):
        status,actual=runner(case["args"])
        if status=="Returned":
            if is_stdio:
                equal = json.dumps(actual,sort_keys=True)==json.dumps(case["expected"].rstrip(),sort_keys=True)
            else:
                equal = json.dumps(actual,sort_keys=True)==json.dumps(case["expected"],sort_keys=True)
            status="Passed" if equal else "Wrong answer"
        row={"number":i+1,"status":status}
        if case.get("sample"):
            row.update(args=case["args"],expected=case["expected"],actual=actual)
        rows.append(row)
        if job.kind=="submit" and status!="Passed":
            break
    passed=sum(row["status"]=="Passed" for row in rows)
    verdict="Accepted" if passed==total else "Failed"
    if passed!=total:
        first_fail = next((row["status"] for row in rows if row["status"]!="Passed"), "Failed")
        verdict = first_fail
    return dict(verdict=verdict,
                passed=passed,total=total,skipped=total-len(rows),cases=rows)

def tick():
    for cid in Contest.objects.filter(stage__in=["automatic","Active","Ended"],ends__lte=timezone.now(),final__isnull=True).values_list("id",flat=True):
        close_contest(cid)
    priority=Case(When(kind="submit",then=Value(0)),When(kind="run",then=Value(1)),default=Value(2),output_field=IntegerField())
    job=Job.objects.filter(state="queued").order_by(priority,"received","id").first()
    if not job:
        return False
    job.state="running"
    job.save(update_fields=["state"])
    try:
        job.result=evaluate(job)
        job.state="done"
    except Exception:
        import logging
        logging.exception("Judge infrastructure error for job %s",job.pk)
        job.state="error"
        job.result={"verdict":"Judge unavailable","cases":[]}
    job.save(update_fields=["state","result"])
    return True
