"""Optional loopback integration rehearsal on this Acer; requires Playwright and the seeded organizer account."""
from pathlib import Path
from datetime import timedelta
from io import BytesIO
import os,sys,secrets,time,uuid
from PIL import Image
from playwright.sync_api import sync_playwright,expect
from django.utils import timezone
project=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(project));os.environ.setdefault('DJANGO_SETTINGS_MODULE','contest.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from arena.models import Contest,Entry,Problem,Draft,Job,Profile,ConnectionEvent
from arena.engine import close_contest
u='candidate-'+uuid.uuid4().hex[:7];name='Rowan Demo';pw=secrets.token_urlsafe(18)
c=Contest.objects.create(title='Campus Sprint · browser rehearsal',starts=timezone.now()-timedelta(minutes=5),ends=timezone.now()+timedelta(hours=1))
template=Problem.objects.filter(published=True).first();template.pk=None;template.contest=c;template.save()
adminpw=dict(l.split() for l in (project/'var/pilot-logins').read_text().splitlines())['organizer']
root='http://127.0.0.1:8765'
bio=BytesIO();Image.new('RGB',(48,48),'tomato').save(bio,'PNG')
try:
 with sync_playwright() as w:
    b=w.chromium.launch(executable_path='/snap/brave/current/opt/brave.com/brave/brave',args=['--disable-dev-shm-usage'])
    cand=b.new_context();pg=cand.new_page();pg.set_default_timeout(25000)
    pg.goto(root);expect(pg.get_by_role('heading',name='Contest schedule')).to_be_visible()
    pg.goto(root+'/signup/');values={'Full name':name,'Enrollment number':u,'Email address':u+'@example.test','Phone number':'1234567890','Username':u,'Password':pw}
    for k,v in values.items():pg.get_by_label(k,exact=True).fill(v)
    pg.get_by_label('Profile photo (optional)').set_input_files({'name':'test.png','mimeType':'image/png','buffer':bio.getvalue()})
    pg.get_by_role('button',name='Create account').click();pg.wait_for_url(root+'/')
    assert pg.request.get(root+'/api/organizer/'+str(c.pk)).status==403
    pg.locator('article').filter(has_text=c.title).get_by_role('button',name='Enter contest').click()
    pg.locator('.cm-content').wait_for()
    mgr=b.new_context();admin=mgr.new_page()
    admin.goto(root+'/login/');admin.get_by_role('button',name='Local account').click();admin.get_by_label('Username').fill('organizer');admin.get_by_label('Password').fill(pw);admin.get_by_role('button',name='Sign in').click()
    expect(admin.get_by_role('alert')).to_have_text('Username or password is incorrect.')
    admin.get_by_label('Password').fill(adminpw);admin.get_by_role('button',name='Sign in').click();admin.wait_for_url('**/organizer/')
    admin.get_by_label('Selected contest').select_option(str(c.pk))
    expect(admin.get_by_role('cell',name=name)).to_be_visible();expect(admin.get_by_role('cell',name='Online',exact=True)).to_be_visible()
    def submit(lang,source):
        pg.get_by_label('Language').select_option(lang)
        editor=pg.locator('.cm-content');expect(editor).to_contain_text('count_even');assert '#include' not in editor.inner_text() and 'class Solution' not in editor.inner_text()
        editor.click();pg.keyboard.press('Control+a');pg.keyboard.insert_text(source)
        pg.get_by_role('button',name='Submit solution').click()
        expect(pg.get_by_text('5 / 5 passed',exact=False)).to_be_visible(timeout=60000)
    submit('cpp','int count_even(vector<int> nums) { int n=0; for(int v:nums) n+=(v%2==0); return n; }')
    submit('java','int count_even(int[] nums) { int n=0; for(int v:nums) if(v%2==0)n++; return n; }')
    submit('python','def count_even(nums):\n    return sum(n % 2 == 0 for n in nums)')
    pg.get_by_label('Language').select_option('cpp');expect(pg.locator('.cm-content')).to_contain_text('for(int v:nums)')
    pg.get_by_role('button',name='Sign out').click();pg.wait_for_url('**/logout/');expect(pg.get_by_role('heading',name='You’re signed out')).to_be_visible()
    assert pg.request.get(root+'/api/session').json()['user'] is None
    print("Passed homepage, signup with picture, role enforcement, generic login error, three submissions and logout.",flush=True)
    expect(admin.get_by_role('alert').filter(has_text='heartbeat lost')).to_be_visible(timeout=65000)
    admin.get_by_role('tab',name='Connection events').click();expect(admin.get_by_text('Heartbeat lost',exact=True)).to_be_visible()
    print("Passed live workspace timeout alert and incident history.",flush=True)
    b.close()
 assert Job.objects.filter(entry__contest=c,result__verdict='Accepted').count()==3
 assert Draft.objects.filter(entry__contest=c).count()==3
finally:
 Job.objects.filter(entry__contest=c).delete();Draft.objects.filter(entry__contest=c).delete();c.delete();get_user_model().objects.filter(username=u).delete()
