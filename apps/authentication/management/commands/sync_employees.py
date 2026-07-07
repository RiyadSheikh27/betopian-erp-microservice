"""
Sync all employees from the central ERP employee directory into the local User table.

Usage:
    python manage.py sync_employees

Paste your bearer token into BEARER_TOKEN below before running, or pass --token.
"""

import math
import time

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import DataError, IntegrityError, transaction

from apps.authentication.models import User

# Paste your bearer access token here before running.
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOjY4LCJzaWQiOjEwOTgsInR5cCI6ImFjY2VzcyIsImlhdCI6MTc4MzQxMDkyOSwiZXhwIjoxNzgzNDE0NTI5fQ.mxxft6t11BHVJUkHFCkQJf9z5tZMZ-w8K_Kc2w-EWWA"

CENTRAL_BASE_URL = "https://erp.betopiagroup.com"
EMPLOYEE_DIRECTORY_URL = f"{CENTRAL_BASE_URL}/employee-directory/"
REQUEST_TIMEOUT = 30
PAGE_DELAY_SECONDS = 0.2

FIELD_MAX_LENGTHS = {
    "employee_id": 100,
    "email": 254,
    "username": 100,
    "name": 150,
    "phone": 20,
    "department": 150,
    "position": 150,
    "location": 150,
    "company": 150,
}


def _clean(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_phone(value):
    phone = _clean(value)
    if not phone:
        return ""
    for sep in (",", ";", "/", "|"):
        if sep in phone:
            phone = phone.split(sep, 1)[0].strip()
            break
    return phone[: FIELD_MAX_LENGTHS["phone"]]


def _fit_fields(fields):
    for key, max_len in FIELD_MAX_LENGTHS.items():
        value = fields.get(key)
        if value:
            fields[key] = str(value)[:max_len]
    return fields


def _resolve_employee_id(employee):
    code = _clean(employee.get("employee_code"))
    if code:
        return code
    hr_id = employee.get("hr_employee_id") or employee.get("id")
    if hr_id:
        return str(hr_id)
    return f"UNKNOWN_{employee.get('id', 'missing')}"


def _resolve_email(employee, employee_id):
    email = _clean(employee.get("work_email")).lower()
    if email and "@" in email:
        return email
    return f"emp_{employee_id}@import.betopiagroup.local"


def _resolve_username(email, employee_id):
    local_part = email.split("@", 1)[0] if "@" in email else email
    return local_part or f"user_{employee_id}"


def _ensure_unique_email(email, employee_id, exclude_pk=None):
    qs = User.objects.filter(email__iexact=email)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if not qs.exists():
        return email

    local_part, domain = email.split("@", 1)
    candidate = f"{local_part}+{employee_id}@{domain}"
    qs = User.objects.filter(email__iexact=candidate)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if not qs.exists():
        return candidate

    suffix = 2
    while True:
        candidate = f"{local_part}+{employee_id}_{suffix}@{domain}"
        qs = User.objects.filter(email__iexact=candidate)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return candidate
        suffix += 1


def _ensure_unique_username(username, employee_id, exclude_pk=None):
    qs = User.objects.filter(username=username)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if not qs.exists():
        return username

    candidate = f"{username}_{employee_id}"
    qs = User.objects.filter(username=candidate)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if not qs.exists():
        return candidate

    suffix = 2
    while True:
        candidate = f"{username}_{employee_id}_{suffix}"
        qs = User.objects.filter(username=candidate)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return candidate
        suffix += 1


def map_employee(employee):
    employee_id = _resolve_employee_id(employee)
    email = _resolve_email(employee, employee_id)
    username = _resolve_username(email, employee_id)
    name = _clean(employee.get("name")) or username

    avatar_url = employee.get("avatar_url") or None
    if avatar_url is not None:
        avatar_url = str(avatar_url).strip() or None

    fields = {
        "central_id": employee.get("id"),
        "employee_id": employee_id,
        "email": email,
        "username": username,
        "name": name,
        "phone": _normalize_phone(employee.get("work_phone")),
        "department": _clean(employee.get("department")),
        "position": _clean(employee.get("job_title")),
        "location": _clean(employee.get("work_location")),
        "company": _clean(employee.get("company_name") or employee.get("company")),
        "avatar_url": avatar_url,
        "is_online": False,
        "central_access_token": "",
        "is_active": True,
        "is_staff": False,
        "password": None,
    }
    return _fit_fields(fields)


def upsert_user(fields):
    user = User.objects.filter(employee_id=fields["employee_id"]).first()
    if user is None and fields.get("central_id"):
        user = User.objects.filter(central_id=fields["central_id"]).first()
    if user is None:
        user = User.objects.filter(email__iexact=fields["email"]).first()
    if user is None:
        user = User.objects.filter(username=fields["username"]).first()

    exclude_pk = user.pk if user else None
    fields["email"] = _ensure_unique_email(
        fields["email"], fields["employee_id"], exclude_pk
    )
    fields["username"] = _ensure_unique_username(
        _resolve_username(fields["email"], fields["employee_id"]),
        fields["employee_id"],
        exclude_pk,
    )

    if user:
        for key, value in fields.items():
            setattr(user, key, value)
        user.save()
        return "updated"

    User.objects.create(**fields)
    return "created"


class Command(BaseCommand):
    help = "Import employees from the central ERP employee directory API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--token",
            default="",
            help="Bearer access token (overrides BEARER_TOKEN in this file).",
        )
        parser.add_argument(
            "--start-page",
            type=int,
            default=1,
            help="Page number to start from (default: 1).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and map employees without writing to the database.",
        )

    def handle(self, *args, **options):
        token = options["token"] or BEARER_TOKEN
        if not token:
            raise CommandError(
                "No bearer token provided. Set BEARER_TOKEN in this file or pass --token."
            )

        session = requests.Session()
        session.headers.update({"Authorization": f"Bearer {token}"})

        first_page = self._fetch_page(session, options["start_page"])
        total = first_page.get("total", 0)
        limit = first_page.get("limit", 50) or 50
        total_pages = max(1, math.ceil(total / limit)) if total else 1

        self.stdout.write(f"Found {total} employees across {total_pages} page(s).")

        created = updated = skipped = 0
        start_page = options["start_page"]

        for page_num in range(start_page, total_pages + 1):
            payload = (
                first_page
                if page_num == start_page
                else self._fetch_page(session, page_num)
            )
            employees = payload.get("employees") or []

            self.stdout.write(
                f"Processing page {page_num}/{total_pages} ({len(employees)} employees)..."
            )

            for employee in employees:
                fields = map_employee(employee)
                if options["dry_run"]:
                    self.stdout.write(
                        f"  [dry-run] {fields['employee_id']} | {fields['email']} | {fields['name']}"
                    )
                    continue

                try:
                    with transaction.atomic():
                        result = upsert_user(fields)
                    if result == "created":
                        created += 1
                    else:
                        updated += 1
                except (IntegrityError, DataError) as exc:
                    skipped += 1
                    self.stderr.write(
                        self.style.WARNING(
                            f"  Skipped {fields['employee_id']} ({fields['email']}): {exc}"
                        )
                    )

            if page_num < total_pages:
                time.sleep(PAGE_DELAY_SECONDS)

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run complete."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync complete. Created: {created}, Updated: {updated}, Skipped: {skipped}"
            )
        )

    def _fetch_page(self, session, page):
        try:
            response = session.get(
                EMPLOYEE_DIRECTORY_URL,
                params={"page": page},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CommandError(f"Failed to fetch page {page}: {exc}") from exc

        payload = response.json()
        if "employees" not in payload:
            raise CommandError(f"Unexpected response on page {page}: {payload}")
        return payload
