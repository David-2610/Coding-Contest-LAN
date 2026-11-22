import json
import logging
import os
import re
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Contest, Entry, Job, Problem, Profile
from .ecode_client import fetch_active_contest, EcodeApiError

logger = logging.getLogger(__name__)

class ContestSyncError(Exception):
    pass

class ContestConflictError(ContestSyncError):
    pass

def get_authoritative_timezone():
    tz_name = getattr(settings, "CONTEST_TIMEZONE", None) or os.environ.get("CONTEST_TIMEZONE", "Asia/Kolkata")
    try:
        return ZoneInfo(tz_name), tz_name
    except Exception:
        return ZoneInfo("Asia/Kolkata"), "Asia/Kolkata"

def cache_banner(banner_url, contest_id):
    if not banner_url or not banner_url.startswith(("http://", "https://")):
        return ""
    try:
        static_dir = getattr(settings, "DATA", None)
        if not static_dir:
            return ""
        banners_dir = static_dir / "static" / "banners"
        banners_dir.mkdir(parents=True, exist_ok=True)
        
        safe_id = re.sub(r"[^\w-]", "_", str(contest_id))
        ext = "png"
        if ".jpg" in banner_url.lower() or ".jpeg" in banner_url.lower():
            ext = "jpg"
        elif ".webp" in banner_url.lower():
            ext = "webp"
        
        filename = f"banner_{safe_id}.{ext}"
        filepath = banners_dir / filename
        
        req = Request(banner_url, headers={"User-Agent": "CodeClash-LAN/1.0"})
        with urlopen(req, timeout=12) as resp:
            data = resp.read()
            if len(data) > 0:
                filepath.write_bytes(data)
                return f"/static/banners/{filename}"
    except (URLError, OSError, TimeoutError) as e:
        logger.warning("Could not locally cache banner for contest %s: %s", contest_id, e)
    return ""

def parse_contest_schedule(date_str, start_time_str, end_time_str, duration_minutes=None):
    """
    Parse date ("YYYY-MM-DD") and clock times ("HH:MM") in the contest's authoritative timezone.
    Returns (starts_utc, ends_utc, duration_minutes, tz_name).
    """
    tz, tz_name = get_authoritative_timezone()
    
    # Parse date and start time
    start_dt_local = datetime.strptime(f"{date_str.strip()} {start_time_str.strip()}", "%Y-%m-%d %H:%M")
    start_dt_aware = start_dt_local.replace(tzinfo=tz)
    
    if end_time_str and end_time_str.strip():
        end_dt_local = datetime.strptime(f"{date_str.strip()} {end_time_str.strip()}", "%Y-%m-%d %H:%M")
        end_dt_aware = end_dt_local.replace(tzinfo=tz)
        if end_dt_aware <= start_dt_aware:
            # End time might cross midnight
            end_dt_aware += timedelta(days=1)
        calc_duration = int((end_dt_aware - start_dt_aware).total_seconds() // 60)
    elif duration_minutes:
        calc_duration = int(duration_minutes)
        end_dt_aware = start_dt_aware + timedelta(minutes=calc_duration)
    else:
        calc_duration = 120
        end_dt_aware = start_dt_aware + timedelta(minutes=calc_duration)
        
    duration = duration_minutes or calc_duration
    
    # Convert to UTC for standard Django storage
    starts_utc = start_dt_aware.astimezone(ZoneInfo("UTC"))
    ends_utc = end_dt_aware.astimezone(ZoneInfo("UTC"))
    
    return starts_utc, ends_utc, duration, tz_name

def fetch_and_cache_contest(contest_id=None, event_id=None, force=False):
    """
    Fetches active contest from E-Code, validates schema, converts timezone,
    caches banner image, and creates/updates local Contest model record.
    """
    data = fetch_active_contest(contest_id=contest_id, event_id=event_id)
    
    remote_contest_id = str(data["contestId"]).strip()
    remote_event_id = str(data.get("eventId", remote_contest_id)).strip()
    name = str(data["name"]).strip()
    description = str(data.get("description", "")).strip()
    banner_url = str(data.get("bannerUrl", "")).strip()
    date_str = str(data["date"]).strip()
    start_time_str = str(data["startTime"]).strip()
    end_time_str = str(data.get("endTime", "")).strip()
    duration_min = data.get("durationMinutes")
    status = str(data.get("status", "UPCOMING")).strip()
    is_ended = bool(data.get("isEnded", False))
    is_published = bool(data.get("isPublished", True))
    total_problems = int(data.get("totalProblems", 0))
    batch_target = str(data.get("batchTarget", "ALL")).strip()
    
    starts_utc, ends_utc, duration, tz_name = parse_contest_schedule(
        date_str, start_time_str, end_time_str, duration_min
    )
    
    with transaction.atomic():
        existing = Contest.objects.select_for_update().filter(ecode_contest_id=remote_contest_id).first()
        
        if existing and not force:
            # Check if ongoing or has submissions
            has_activity = (
                existing.stage in ("Active", "Ended") or
                existing.final is not None or
                Job.objects.filter(entry__contest=existing).exists()
            )
            if has_activity:
                raise ContestConflictError(
                    f"Contest '{existing.title}' (ID: {remote_contest_id}) is active, ended, or has submissions. "
                    "Use confirmation (force=True) to update its details."
                )
        
        banner_cached = cache_banner(banner_url, remote_contest_id)
        
        if not existing:
            # Check if there's any active draft or local contest to link, or create new
            contest = Contest.objects.create(
                title=name,
                starts=starts_utc,
                ends=ends_utc,
                stage="Scheduled" if status == "UPCOMING" else "Active" if status == "ACTIVE" else "Draft",
                ecode_contest_id=remote_contest_id,
                ecode_event_id=remote_event_id,
                description=description,
                banner_url=banner_url,
                banner_path=banner_cached,
                duration_minutes=duration,
                ecode_status=status,
                is_ended=is_ended,
                is_published=is_published,
                total_problems=total_problems,
                batch_target=batch_target,
                sync_status="READY",
                raw_metadata=data
            )
            created = True
        else:
            contest = existing
            contest.title = name
            contest.starts = starts_utc
            contest.ends = ends_utc
            contest.ecode_event_id = remote_event_id
            contest.description = description
            contest.banner_url = banner_url
            if banner_cached:
                contest.banner_path = banner_cached
            contest.duration_minutes = duration
            contest.ecode_status = status
            contest.is_ended = is_ended
            contest.is_published = is_published
            contest.total_problems = total_problems
            contest.batch_target = batch_target
            contest.raw_metadata = data
            contest.save()
            created = False

    return {
        "contest": contest,
        "created": created,
        "timezone": tz_name,
        "startsLocal": f"{date_str} {start_time_str} ({tz_name})",
        "endsLocal": f"{date_str} {end_time_str} ({tz_name})" if end_time_str else f"+{duration}m",
        "durationMinutes": duration,
        "totalProblems": total_problems,
        "batchTarget": batch_target,
        "bannerCached": bool(contest.banner_path),
        "data": data
    }

def generate_sync_payload(contest):
    """
    Generates and validates the final result payload matching new.md.
    Does not transmit anything to the cloud.
    """
    if not contest.final:
        raise ContestSyncError("Contest standings have not been finalized yet.")
    
    contest_id = contest.ecode_contest_id
    if not contest_id:
        raise ContestSyncError("This contest has no E-Code contestId associated with it.")
    
    # Problems list
    problems = []
    configured_problems = list(contest.problem_set.all().order_by("id"))
    for idx, p in enumerate(configured_problems):
        p_id = p.external_id or chr(ord('A') + idx)
        max_pts = p.package.get("scoring", {}).get("maxScore", 100) if p.package else 100
        problems.append({
            "problemId": p_id,
            "title": p.title,
            "maxPoints": max_pts
        })
    
    # Participants list
    entries = {}
    for entry in contest.entry_set.filter(eligible=True).select_related("user"):
        key = entry.pk if contest.final_entries is not None else entry.display
        if key in entries:
            raise ContestSyncError("Ambiguous identities in this contest snapshot.")
        entries[key] = entry
    
    participants = []
    for index, row in enumerate(contest.final.get("rows", [])):
        key = contest.final_entries[index] if contest.final_entries is not None else row["name"]
        entry = entries.pop(key, None)
        if not entry:
            raise ContestSyncError(f"Standing row '{row.get('name')}' does not match any entry record.")
        
        profile = Profile.objects.filter(user=entry.user, enrollment=entry.enrollment).exclude(ecode_batch="").first()
        if not profile:
            raise ContestSyncError(f"Participant '{entry.display}' ({entry.enrollment}) has no verified E-Code profile.")
        
        # Determine solved problem IDs matching the problems list
        solved_keys = row.get("problems", {})
        if isinstance(solved_keys, dict):
            solved_ids = []
            for prob_pk_str in solved_keys.keys():
                matching_p = next((p for p in configured_problems if str(p.pk) == str(prob_pk_str)), None)
                if matching_p:
                    solved_ids.append(matching_p.external_id or chr(ord('A') + configured_problems.index(matching_p)))
                else:
                    solved_ids.append(str(prob_pk_str))
        elif isinstance(solved_keys, list):
            solved_ids = list(solved_keys)
        else:
            solved_ids = []

        participants.append({
            "rank": row["rank"],
            "enrollmentNumber": entry.enrollment,
            "username": entry.user.username,
            "fullName": entry.display,
            "batchYear": profile.ecode_batch,
            "score": row.get("score", row["solved"]),
            "problemsSolved": row["solved"],
            "timePenaltyMinutes": row.get("seconds", 0) // 60,
            "solvedProblems": solved_ids
        })
        
    duration = contest.duration_minutes or int((contest.ends - contest.starts).total_seconds() // 60)
    
    payload = {
        "contestId": contest_id,
        "title": contest.title,
        "description": contest.description or f"{contest.title} offline LAN contest",
        "startTime": contest.starts.isoformat().replace("+00:00", "Z"),
        "endTime": contest.ends.isoformat().replace("+00:00", "Z"),
        "durationMinutes": duration,
        "totalProblems": len(problems),
        "batchTarget": contest.batch_target or "ALL",
        "problems": problems,
        "participants": participants
    }
    
    warnings = []
    if contest.total_problems and contest.total_problems != len(problems):
        warnings.append(
            f"Configured problem count ({len(problems)}) does not match E-Code metadata ({contest.total_problems})."
        )
        
    return payload, warnings
