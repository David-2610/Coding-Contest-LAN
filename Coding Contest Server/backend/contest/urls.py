from django.contrib import admin
from django.urls import path
from arena import views,portal,ecode_jobs
urlpatterns=[
 *[path(route,portal.site) for route in ("","login/","profile/","logout/","organizer/","roster/","global/","contests/<int:cid>/","leaderboard/<int:cid>/")],
 path("api/organizer/contest/fetch",portal.fetch_contest_api),
 path("api/organizer/contest/remote",portal.preview_remote_contest_api),
 path("api/organizer/contest/<int:cid>/sync-preview",portal.sync_preview_api),
 path("api/organizer/contest/<int:cid>/readiness",portal.readiness_check_api),
 path("api/organizer/bank",portal.question_bank),
 path("api/organizer/<int:cid>/copy-bank",portal.copy_from_bank),
 path("api/organizer/<int:cid>/stage",portal.transition),
 path("api/organizer/roster/refresh",ecode_jobs.transfer),
 path("api/organizer/<int:cid>/publish",ecode_jobs.transfer),
 path("api/organizer/roster",portal.roster),
 path("api/ecode/leaderboards",portal.online_board),
 path("api/session",portal.session_info),path("api/login",portal.signin),path("api/logout",portal.signout),
 path("api/profile/photo",portal.account_photo),path("api/contests/<int:cid>/enter",portal.enter),path("api/contests/<int:cid>/heartbeat",portal.heartbeat),
 path("api/organizer/<int:cid>",portal.monitor),path("api/organizer/contests",portal.create_contest),path("api/organizer/<int:cid>/problems",portal.author),
 path("api/organizer/jobs/<int:jid>",portal.job_detail),path("api/organizer/entries/<int:eid>/eligibility",portal.eligibility),path("api/workspace",views.workspace),
 path("api/problems/<int:pid>/history",views.history),path("api/problems/<int:pid>/<str:mode>",views.action),path("api/jobs/<int:jid>",views.result),
 path("api/contests/<int:cid>/leaderboard",views.board),path("organizer-export/<int:cid>",views.export)]
