from __future__ import annotations

from datetime import datetime

from src.core.auth import hash_password, verify_password
from src.storage.audit import record_audit
from src.storage.db import get_database_manager
from src.storage.models import AcademicMajor, Classroom, SchoolProfile, Student, User
from src.utils.validators import validate_username


class SettingsPermissionError(PermissionError):
    pass


class SettingsValidationError(ValueError):
    pass


def _actor(actor, counselor=False):
    fresh = User.get_by_id(actor.id)
    if not fresh.is_active or (
        fresh.role != "counselor" if counselor else not fresh.can_manage_users
    ):
        raise SettingsPermissionError("دسترسی لازم برای این عملیات را ندارید.")
    return fresh


def _transaction(actor, action, entity, target_id=None, details=None, write=None):
    manager = get_database_manager()
    with manager.transaction():
        fresh = _actor(actor)
        result = write(fresh)
        record_audit(fresh, action, entity, target_id, details() if callable(details) else details)
        return result


def update_school(actor, school_name, school_start_time=None, school_end_time=None):
    school_name = school_name.strip()
    if not 2 < len(school_name) < 50:
        raise SettingsValidationError("نام مدرسه باید بین ۳ تا ۴۹ نویسه باشد.")
    if school_start_time is None or school_end_time is None:
        profile = SchoolProfile.get_by_id(1)
        school_start_time = school_start_time or profile.school_start_time
        school_end_time = school_end_time or profile.school_end_time
    try:
        start = datetime.strptime(school_start_time.strip(), "%H:%M")
        end = datetime.strptime(school_end_time.strip(), "%H:%M")
    except ValueError as exc:
        raise SettingsValidationError("زمان مدرسه را با قالب HH:MM وارد کنید.") from exc
    if start >= end:
        raise SettingsValidationError("زمان پایان مدرسه باید بعد از زمان شروع باشد.")

    def write(_):
        profile = SchoolProfile.get_by_id(1)
        profile.school_name = school_name
        profile.school_start_time = school_start_time.strip()
        profile.school_end_time = school_end_time.strip()
        profile.save()
        return profile

    return _transaction(
        actor,
        "school.update",
        "SchoolProfile",
        None,
        lambda: (
            f"تنظیمات مدرسه به «{school_name}» و بازهٔ "
            f"{school_start_time.strip()} تا {school_end_time.strip()} تغییر کرد"
        ),
        write,
    )


def save_classroom(actor, room=None, *, grade_level, major, code, academic_year):
    code = code.strip()
    if not code:
        raise SettingsValidationError("عنوان/کد کلاس را وارد کنید.")
    if grade_level < 10:
        major = AcademicMajor.GENERAL
    if major not in AcademicMajor.VALUES:
        raise SettingsValidationError("رشته تحصیلی نامعتبر است.")
    creating = room is None

    def write(_):
        nonlocal room
        if room is not None:
            room = Classroom.get_by_id(room.id)
            if Student.select().where((Student.classroom == room) & Student.is_active).exists():
                if room.grade_level != grade_level or room.major != major:
                    raise SettingsValidationError(
                        "پایه و رشتهٔ کلاس دارای دانش آموز فعال قابل تغییر نیست."
                    )
        else:
            room = Classroom()
        room.grade_level, room.major, room.code, room.academic_year = (
            grade_level,
            major,
            code,
            academic_year,
        )
        room.save(force_insert=creating)
        return room

    action = "class.create" if creating else "class.update"
    return _transaction(
        actor,
        action,
        "Classroom",
        room.id if room else None,
        lambda: f"کلاس «{room.name}» {'ایجاد' if creating else 'ویرایش'} شد",
        write,
    )


def delete_classroom(actor, room):
    def write(_):
        current = Classroom.get_by_id(room.id)
        active = Student.select().where((Student.classroom == current) & Student.is_active).count()
        if active:
            raise SettingsValidationError(f"این کلاس {active} دانش آموز فعال دارد.")
        name, identifier = current.name, current.id
        current.delete_instance()
        return name, identifier

    return _transaction(
        actor, "class.delete", "Classroom", room.id, lambda: f"کلاس «{room.name}» حذف شد", write
    )


def save_user(
    actor, user=None, *, full_name, username=None, role=None, can_manage_users=None, password=None
):
    full_name = full_name.strip()
    if not full_name:
        raise SettingsValidationError("نام و نام خانوادگی را وارد کنید.")
    creating = user is None

    def write(fresh):
        nonlocal user
        if creating:
            if not username or not validate_username(username):
                raise SettingsValidationError("نام کاربری نامعتبر است.")
            user = User(
                username=username.lower(),
                full_name=full_name,
                role=role or "assistant",
                can_manage_users=bool(can_manage_users),
                password_hash=hash_password(password) if password else None,
            )
            user.save()
            return user
        user = User.get_by_id(user.id)
        is_self = user.id == fresh.id
        user.full_name = full_name
        if not is_self:
            if role is not None:
                user.role = role
            if can_manage_users is not None:
                if (
                    user.can_manage_users
                    and not can_manage_users
                    and User.select().where(User.can_manage_users & User.is_active).count() <= 1
                ):
                    raise SettingsValidationError("حداقل یک مدیر فعال باید باقی بماند.")
                user.can_manage_users = can_manage_users
            if password:
                user.password_hash = hash_password(password)
        user.save()
        return user

    action = (
        "user.create"
        if creating
        else (
            "user.password_reset"
            if password
            else ("user.role_change" if role is not None and role != user.role else "user.update")
        )
    )
    return _transaction(
        actor,
        action,
        "User",
        user.id if user else None,
        lambda: f"کاربر «{full_name}» ذخیره شد",
        write,
    )


def set_user_active(actor, user, is_active):
    def write(fresh):
        target = User.get_by_id(user.id)
        if target.id == fresh.id and not is_active:
            raise SettingsValidationError("نمی توانید حساب خودتان را غیرفعال کنید.")
        if (
            target.can_manage_users
            and target.is_active
            and not is_active
            and User.select().where(User.can_manage_users & User.is_active).count() <= 1
        ):
            raise SettingsValidationError("حداقل یک مدیر فعال باید باقی بماند.")
        target.is_active = is_active
        target.save()
        return target

    return _transaction(
        actor,
        "user.activate" if is_active else "user.deactivate",
        "User",
        user.id,
        lambda: f"کاربر «{user.full_name}» {'فعال' if is_active else 'غیرفعال'} شد",
        write,
    )


def change_own_password(actor, current_password, new_password):
    if len(new_password) < 8:
        raise SettingsValidationError("رمز عبور باید دست کم ۸ نویسه باشد.")

    def write(fresh):
        if fresh.password_hash and not verify_password(current_password, fresh.password_hash):
            raise SettingsValidationError("رمز عبور فعلی صحیح نیست.")
        fresh.password_hash = hash_password(new_password)
        fresh.save()
        return fresh

    return _transaction(actor, "password.self_change", "User", actor.id, None, write)


def rotate_vault_pin(actor, old_pin, new_pin):
    manager = get_database_manager()
    _actor(actor, counselor=True)
    manager.rotate_vault_pin(old_pin, new_pin)
    with manager.transaction():
        fresh = _actor(actor, counselor=True)
        record_audit(fresh, "vault.pin_change", "Vault")


_SOFT_WEIGHT_KEYS = ("s1", "s2", "s3", "s4", "s5")


def update_planner_settings(actor, *, block_minutes, weights):
    from src.storage.models import PlannerSettings

    if int(block_minutes) not in (75, 90):
        raise SettingsValidationError("طول بلوک باید ۷۵ یا ۹۰ دقیقه باشد.")
    clean = {}
    for key in _SOFT_WEIGHT_KEYS:
        value = int(weights.get(key, 0))
        if value < 0:
            raise SettingsValidationError("وزن محدودیت‌ها نمی‌تواند منفی باشد.")
        clean[key] = value

    def write(_):
        row = PlannerSettings.get_instance()
        row.block_minutes = int(block_minutes)
        row.weights = clean
        row.updated_at = datetime.now()
        row.save()
        return row

    return _transaction(
        actor,
        "planner_settings.update",
        "PlannerSettings",
        None,
        lambda: f"تنظیمات موتور برنامه‌ریزی به‌روزرسانی شد (بلوک {int(block_minutes)} دقیقه)",
        write,
    )
