from .languages import default_signature, check_signature
from django.conf import settings
from django.db import models

class Contest(models.Model):
    title = models.CharField(max_length=100)
    stage = models.CharField(max_length=16, default="automatic")
    starts = models.DateTimeField()
    ends = models.DateTimeField()
    final_entries = models.JSONField(null=True, editable=False)
    final = models.JSONField(null=True, blank=True, editable=False)
    
    # E-Code Integration fields
    ecode_contest_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    ecode_event_id = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(blank=True, default="")
    banner_url = models.CharField(max_length=500, blank=True, default="")
    banner_path = models.CharField(max_length=255, blank=True, default="")
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    ecode_status = models.CharField(max_length=32, blank=True, default="")
    is_ended = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    total_problems = models.PositiveIntegerField(default=0)
    batch_target = models.CharField(max_length=32, default="ALL")
    synced_at = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=32, default="NOT_CONFIGURED")
    sync_response = models.JSONField(null=True, blank=True)
    raw_metadata = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.title

class Entry(models.Model):
    contest = models.ForeignKey(Contest,on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    enrollment = models.CharField(max_length=64)
    display = models.CharField(max_length=80)
    acknowledged=models.DateTimeField(null=True,blank=True)
    last_seen = models.DateTimeField(null=True,blank=True)
    presence = models.CharField(max_length=20,default="Not joined")
    eligible = models.BooleanField(default=True)
    decision_reason = models.TextField(blank=True)

    class Meta:
        unique_together = (("contest","user"),("contest","enrollment"))

    def __str__(self):
        return self.display

class Problem(models.Model):
    contest = models.ForeignKey(Contest,on_delete=models.CASCADE)
    title = models.CharField(max_length=120)
    external_id=models.CharField(max_length=64, null=True, unique=True)
    package=models.JSONField(default=dict,blank=True)
    statement = models.TextField()
    function = models.SlugField(help_text="Python function name")
    starter = models.TextField()
    signature = models.JSONField(default=default_signature)
    cases = models.JSONField(help_text='List of objects with args (a positional argument list), expected, and sample (true or false).')
    published = models.BooleanField(default=False)

    def clean(self):
        import keyword
        from django.core.exceptions import ValidationError
        try: check_signature(self.function,self.signature)
        except (KeyError,ValueError,TypeError,AttributeError): raise ValidationError("Invalid typed function signature")
        if not self.function.isidentifier() or keyword.iskeyword(self.function):
            raise ValidationError("Use a valid Python function name.")
        if not isinstance(self.cases,list) or not 1 <= len(self.cases) <= 100:
            raise ValidationError("Supply 1–100 test cases.")
        for case in self.cases:
            if not isinstance(case,dict) or not isinstance(case.get("args"),list) or "expected" not in case or type(case.get("sample")) is not bool:
                raise ValidationError("Each test needs args, expected and a boolean sample flag.")

    def __str__(self):
        return self.title

class Draft(models.Model):
    entry = models.ForeignKey(Entry,on_delete=models.CASCADE)
    problem = models.ForeignKey(Problem,on_delete=models.PROTECT)
    language = models.CharField(max_length=12,default="python")
    source = models.TextField()
    revision = models.PositiveIntegerField()
    saved = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("entry","problem","language"),)

class Job(models.Model):
    entry = models.ForeignKey(Entry,on_delete=models.CASCADE)
    problem = models.ForeignKey(Problem,on_delete=models.PROTECT)
    kind = models.CharField(max_length=12)
    token = models.CharField(max_length=80)
    language = models.CharField(max_length=12,default="python")
    source = models.TextField()
    received = models.DateTimeField()
    cases = models.JSONField()
    function = models.CharField(max_length=120)
    state = models.CharField(max_length=16,default="queued")
    result = models.JSONField(null=True)
    class Meta:
        unique_together = (("entry","token"),)

class Profile(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    full_name=models.CharField(max_length=150)
    enrollment=models.CharField(max_length=64,unique=True)
    ecode_batch=models.CharField(max_length=4, default="", blank=True)
    pin_failures=models.PositiveSmallIntegerField(default=0)
    pin_retry=models.DateTimeField(null=True, blank=True)
    phone=models.CharField(max_length=30)
    photo=models.BinaryField(default=bytes,blank=True)

class ConnectionEvent(models.Model):
    entry=models.ForeignKey(Entry,on_delete=models.CASCADE)
    kind=models.CharField(max_length=24)
    at=models.DateTimeField(auto_now_add=True)

class Decision(models.Model):
    entry=models.ForeignKey(Entry,on_delete=models.CASCADE)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    eligible=models.BooleanField()
    reason=models.CharField(max_length=800)
    at=models.DateTimeField(auto_now_add=True)


class EcodeTransfer(models.Model):
    updated=models.DateTimeField(auto_now=True)
    key=models.CharField(max_length=64,unique=True)
    status=models.CharField(max_length=16,default="idle")
    message=models.CharField(max_length=300,default="")
