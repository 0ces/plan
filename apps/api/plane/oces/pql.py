# Copyright (c) 2026-present Edwar Plata (oces) and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Plane Query Language (PQL) -> Django Q for work item querysets.

Our own implementation of the public PQL grammar that plane-mcp-server documents
(fields, operators, functions, max 5 conditions). Errors raise PQLError; views
return them as 400 {"pql": message} so the MCP shows its reference.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from plane.db.models import (
    Cycle,
    CycleIssue,
    IntakeIssue,
    Issue,
    IssueAssignee,
    IssueLabel,
    IssueMention,
    IssueRelation,
    IssueSubscriber,
    ModuleIssue,
    ProjectMember,
    WorkspaceMember,
)

MAX_CONDITIONS = 5


class PQLError(ValueError):
    pass


# ---------------------------------------------------------------- tokenizer

TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<string>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
  | (?P<number>-?\d+(?:\.\d+)?)
  | (?P<op>!=|>=|<=|=|>|<|~)
  | (?P<punct>[()\[\],])
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
    """,
    re.VERBOSE,
)
KEYWORDS = {"AND", "OR", "NOT", "IN", "IS", "NULL", "EMPTY", "BETWEEN", "TRUE", "FALSE"}


@dataclass
class Tok:
    kind: str  # string, number, op, punct, ident, kw, end
    value: object
    pos: int


def tokenize(text):
    tokens, pos = [], 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise PQLError(f"Unexpected character {text[pos]!r} at position {pos}.")
        kind, raw = m.lastgroup, m.group()
        pos = m.end()
        if kind == "ws":
            continue
        if kind == "string":
            tokens.append(Tok("string", bytes(raw[1:-1], "utf-8").decode("unicode_escape"), m.start()))
        elif kind == "number":
            tokens.append(Tok("number", float(raw) if "." in raw else int(raw), m.start()))
        elif kind == "ident" and raw.upper() in KEYWORDS:
            tokens.append(Tok("kw", raw.upper(), m.start()))
        else:
            tokens.append(Tok(kind, raw, m.start()))
    tokens.append(Tok("end", None, len(text)))
    return tokens


# ---------------------------------------------------------------- fields

# kind: str (plain column), fk (uuid column), m2m (through-table subquery), date, datetime, bool
FIELDS = {
    "priority": ("str", "priority"),
    "stateGroup": ("str", "state__group"),
    "title": ("text", "name"),
    "text": ("text", "text"),
    "id": ("ident", None),
    "isDraft": ("bool", "is_draft"),
    "isArchived": ("bool", "archived"),
    "dueDate": ("date", "target_date"),
    "startDate": ("date", "start_date"),
    "createdAt": ("datetime", "created_at"),
    "updatedAt": ("datetime", "updated_at"),
    "state": ("fk", "state_id"),
    "project": ("fk", "project_id"),
    "createdBy": ("fk", "created_by_id"),
    "type": ("fk", "type_id"),
    "assignee": ("m2m", (IssueAssignee, "assignee_id")),
    "label": ("m2m", (IssueLabel, "label_id")),
    "cycle": ("m2m", (CycleIssue, "cycle_id")),
    "module": ("m2m", (ModuleIssue, "module_id")),
    "mention": ("m2m", (IssueMention, "mention_id")),
    "subscriber": ("m2m", (IssueSubscriber, "subscriber_id")),
}
NOT_AVAILABLE = {"milestone", "teamspaceProject"}
PRIORITIES = {"urgent", "high", "medium", "low", "none"}
STATE_GROUPS = {"backlog", "unstarted", "started", "completed", "cancelled"}
OPEN, CLOSED, ACTIVE = ["backlog", "unstarted", "started"], ["completed", "cancelled"], ["unstarted", "started"]


class Ctx:
    """What functions need: the user, workspace and (optional) project."""

    def __init__(self, user, workspace_slug, project_id=None):
        self.user, self.slug, self.project_id = user, workspace_slug, project_id
        self.now = timezone.localtime()
        self.today = self.now.date()


# ---------------------------------------------------------------- parser


class Parser:
    def __init__(self, text, ctx):
        self.toks, self.i, self.ctx, self.conditions = tokenize(text), 0, ctx, 0

    # helpers
    @property
    def tok(self):
        return self.toks[self.i]

    def take(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def accept(self, kind, value=None):
        t = self.tok
        if t.kind == kind and (value is None or t.value == value):
            self.i += 1
            return t
        return None

    def expect(self, kind, value=None, what=None):
        t = self.accept(kind, value)
        if not t:
            raise PQLError(f"Expected {what or value or kind} at position {self.tok.pos}.")
        return t

    def count(self):
        self.conditions += 1
        if self.conditions > MAX_CONDITIONS:
            raise PQLError(f"Too many conditions: PQL allows at most {MAX_CONDITIONS}.")

    # grammar
    def parse(self):
        if self.tok.kind == "end":
            raise PQLError("Empty PQL query.")
        q = self.or_expr()
        if self.tok.kind != "end":
            raise PQLError(f"Unexpected {self.tok.value!r} at position {self.tok.pos}.")
        return q

    def or_expr(self):
        q = self.and_expr()
        while self.accept("kw", "OR"):
            q = q | self.and_expr()
        return q

    def and_expr(self):
        q = self.not_expr()
        while self.accept("kw", "AND"):
            q = q & self.not_expr()
        return q

    def not_expr(self):
        if self.accept("kw", "NOT"):
            return ~self.not_expr()
        return self.primary()

    def primary(self):
        if self.accept("punct", "("):
            q = self.or_expr()
            self.expect("punct", ")")
            return q
        t = self.tok
        if t.kind != "ident":
            raise PQLError(f"Expected a field or function at position {t.pos}.")
        nxt = self.toks[self.i + 1]
        if t.value == "cf" and nxt.kind == "punct" and nxt.value == "[":
            raise PQLError("Custom property filters (cf[...]) are not available on this edition yet.")
        if nxt.kind == "punct" and nxt.value == "(":
            self.count()
            return self.predicate()
        self.count()
        return self.comparison()

    # values
    def value(self):
        t = self.take()
        if t.kind in ("string", "number"):
            return t.value
        if t.kind == "kw" and t.value in ("TRUE", "FALSE"):
            return t.value == "TRUE"
        if t.kind == "ident" and self.accept("punct", "("):
            args = self.args()
            return self.call_value(t.value, args)
        raise PQLError(f"Expected a value at position {t.pos}.")

    def args(self):
        args = []
        if self.accept("punct", ")"):
            return args
        while True:
            t = self.take()
            if t.kind not in ("string", "number"):
                raise PQLError(f"Function arguments must be strings or numbers (position {t.pos}).")
            args.append(t.value)
            if self.accept("punct", ")"):
                return args
            self.expect("punct", ",", what="',' or ')'")

    def value_list(self):
        if self.accept("punct", "("):
            items = [self.value()]
            while self.accept("punct", ","):
                items.append(self.value())
            self.expect("punct", ")")
            out = []
            for item in items:
                out.extend(item if isinstance(item, list) else [item])
            return out
        v = self.value()
        return v if isinstance(v, list) else [v]

    # functions returning values
    def call_value(self, name, args):
        ctx, today = self.ctx, self.ctx.today

        def n():
            if len(args) != 1 or not isinstance(args[0], int):
                raise PQLError(f"{name}() needs one whole number.")
            return args[0]

        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        simple = {
            "today": lambda: today,
            "now": lambda: ctx.now,
            "startOfDay": lambda: today,
            "endOfDay": lambda: today,
            "startOfWeek": lambda: week_start,
            "endOfWeek": lambda: week_start + timedelta(days=6),
            "startOfMonth": lambda: month_start,
            "endOfMonth": lambda: next_month - timedelta(days=1),
            "startOfYear": lambda: today.replace(month=1, day=1),
            "endOfYear": lambda: today.replace(month=12, day=31),
            "openStates": lambda: list(OPEN),
            "closedStates": lambda: list(CLOSED),
            "activeStates": lambda: list(ACTIVE),
            "currentUser": lambda: str(ctx.user.id),
            "workspaceMembers": lambda: [
                str(x)
                for x in WorkspaceMember.objects.filter(workspace__slug=ctx.slug, is_active=True).values_list(
                    "member_id", flat=True
                )
            ],
            "activeCycle": lambda: self.cycles(start_date__date__lte=today, end_date__date__gte=today),
            "completedCycles": lambda: self.cycles(end_date__date__lt=today),
            "upcomingCycles": lambda: self.cycles(start_date__date__gt=today),
        }
        if name in simple:
            if args:
                raise PQLError(f"{name}() takes no arguments.")
            return simple[name]()
        relative = {
            "daysAgo": lambda: today - timedelta(days=n()),
            "daysFromNow": lambda: today + timedelta(days=n()),
            "weeksAgo": lambda: today - timedelta(weeks=n()),
            "weeksFromNow": lambda: today + timedelta(weeks=n()),
            "monthsAgo": lambda: shift_months(today, -n()),
            "monthsFromNow": lambda: shift_months(today, n()),
        }
        if name in relative:
            return relative[name]()
        if name == "membersOf":
            if len(args) != 1 or not str(args[0]).startswith("project:"):
                raise PQLError('membersOf() needs "project:<uuid>".')
            project_id = as_uuid(str(args[0]).split(":", 1)[1])
            return [
                str(x)
                for x in ProjectMember.objects.filter(
                    project_id=project_id, workspace__slug=ctx.slug, is_active=True
                ).values_list("member_id", flat=True)
            ]
        raise PQLError(f"Unknown function {name}().")

    def cycles(self, **filters):
        qs = Cycle.objects.filter(workspace__slug=self.ctx.slug, **filters)
        if self.ctx.project_id:
            qs = qs.filter(project_id=self.ctx.project_id)
        return [str(x) for x in qs.values_list("id", flat=True)]

    # standalone predicates and relations
    def predicate(self):
        name = self.take().value
        self.expect("punct", "(")
        args = self.args()
        no_args = {
            "isOverdue": lambda: Q(target_date__lt=self.ctx.today, state__group__in=OPEN),
            "hasNoAssignee": lambda: ~m2m_q(IssueAssignee, "assignee_id", None),
            "hasNoLabel": lambda: ~m2m_q(IssueLabel, "label_id", None),
            "isTopLevel": lambda: Q(parent__isnull=True),
            "isSubWorkItem": lambda: Q(parent__isnull=False),
            "isEpic": lambda: Q(type__is_epic=True),
            "hasChildren": lambda: Q(id__in=Issue.issue_objects.filter(parent__isnull=False).values("parent_id")),
            "hasStartAndDueDates": lambda: Q(start_date__isnull=False, target_date__isnull=False),
            "isDraft": lambda: Q(is_draft=True),
            "isArchived": lambda: Q(archived_at__isnull=False),
            "isIntake": lambda: Q(id__in=IntakeIssue.objects.filter(deleted_at__isnull=True).values("issue_id")),
        }
        if name in no_args:
            if args:
                raise PQLError(f"{name}() takes no arguments.")
            return no_args[name]()
        relations = {"childOf", "parentOf", "linkedTo", "blockedBy", "blocks", "duplicateOf"}
        if name in relations:
            if len(args) != 1:
                raise PQLError(f'{name}() needs one work item id, e.g. {name}("WEB-5").')
            target = self.resolve_issue(str(args[0]))
            return relation_q(name, target)
        raise PQLError(f"Unknown predicate {name}().")

    def resolve_issue(self, ref):
        qs = Issue.all_objects.filter(workspace__slug=self.ctx.slug, deleted_at__isnull=True)
        m = re.fullmatch(r"([A-Za-z0-9]+)-(\d+)", ref.strip())
        if m:
            issue = qs.filter(project__identifier__iexact=m.group(1), sequence_id=int(m.group(2))).first()
        else:
            issue = qs.filter(id=as_uuid(ref)).first()
        if not issue:
            raise PQLError(f"Work item {ref!r} not found.")
        return issue

    # field comparisons
    def comparison(self):
        name = self.take().value
        if name in NOT_AVAILABLE:
            raise PQLError(f"Field {name!r} is not available on this edition.")
        if name not in FIELDS:
            raise PQLError(f"Unknown field {name!r}.")
        kind, target = FIELDS[name]
        t = self.tok
        if self.accept("kw", "IS"):
            negate = bool(self.accept("kw", "NOT"))
            if not (self.accept("kw", "NULL") or self.accept("kw", "EMPTY")):
                raise PQLError(f"Expected NULL or EMPTY after IS at position {self.tok.pos}.")
            q = is_null_q(name, kind, target)
            return ~q if negate else q
        if self.accept("kw", "NOT"):
            self.expect("kw", "IN")
            return ~self.in_q(name, kind, target, self.value_list())
        if self.accept("kw", "IN"):
            return self.in_q(name, kind, target, self.value_list())
        if self.accept("kw", "BETWEEN"):
            if self.accept("punct", "("):
                low = self.value()
                self.expect("punct", ",")
                high = self.value()
                self.expect("punct", ")")
            else:
                low = self.value()
                self.expect("kw", "AND")
                high = self.value()
            return compare_q(name, kind, target, ">=", low) & compare_q(name, kind, target, "<=", high)
        if t.kind == "op":
            op = self.take().value
            return compare_q(name, kind, target, op, self.value())
        raise PQLError(f"Expected an operator after {name!r} at position {t.pos}.")

    def in_q(self, name, kind, target, values):
        if kind in ("date", "datetime", "bool", "text"):
            raise PQLError(f"IN is not supported for {name!r}.")
        q = Q()
        for v in values:
            q |= compare_q(name, kind, target, "=", v)
        return q if values else Q(pk__in=[])


# ---------------------------------------------------------------- Q builders


def as_uuid(value):
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise PQLError(f"{value!r} is not a valid UUID.")


def shift_months(d, months):
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    for day in (d.day, 30, 29, 28):
        try:
            return d.replace(year=year, month=month, day=day)
        except ValueError:
            continue


def m2m_q(model, column, value):
    """Work items linked through a through-table (live rows only). value None = any link."""
    rows = model.objects.filter(deleted_at__isnull=True)
    if value is not None:
        rows = rows.filter(**{column: value})
    return Q(id__in=rows.values("issue_id"))


def is_null_q(name, kind, target):
    if kind == "m2m":
        return ~m2m_q(*target, None)
    if kind == "bool":
        raise PQLError(f"IS NULL is not supported for {name!r}.")
    if kind in ("text", "ident"):
        raise PQLError(f"IS NULL is not supported for {name!r}.")
    if kind == "str" and target == "priority":
        return Q(priority__isnull=True) | Q(priority="none")
    return Q(**{f"{target}__isnull": True})


def to_date(name, value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise PQLError(f'{name!r} needs a date like "2026-10-29" or a date function.')


LOOKUPS = {">": "gt", ">=": "gte", "<": "lt", "<=": "lte"}


def compare_q(name, kind, target, op, value):
    if isinstance(value, list):
        raise PQLError(f"{name!r} {op} needs a single value; use IN for lists.")
    if op == "~" and kind not in ("text", "ident"):
        raise PQLError(f"~ (contains) only works on title, text and id, not {name!r}.")
    if op in LOOKUPS and kind not in ("date", "datetime"):
        raise PQLError(f"{op} only works on date fields, not {name!r}.")

    if kind == "text":
        if op not in ("=", "!=", "~"):
            raise PQLError(f"{op} is not supported for {name!r}.")
        if target == "text":
            q = Q(name__icontains=value) | Q(description_stripped__icontains=value)
        else:
            q = Q(name__icontains=value) if op == "~" else Q(name__iexact=value)
        return ~q if op == "!=" else q

    if kind == "ident":
        ref = str(value).strip()
        m = re.fullmatch(r"([A-Za-z0-9]+)-(\d+)", ref)
        if op == "~":
            ident, _, seq = ref.partition("-")
            q = Q(project__identifier__istartswith=ident)
            if seq:
                q &= Q(sequence_id__startswith=seq) if seq.isdigit() else Q(pk__in=[])
            return q
        if not m:
            raise PQLError(f'id needs a work item identifier like "WEB-11", got {ref!r}.')
        q = Q(project__identifier__iexact=m.group(1), sequence_id=int(m.group(2)))
        return ~q if op == "!=" else q

    if kind == "bool":
        if not isinstance(value, bool) or op not in ("=", "!="):
            raise PQLError(f"{name!r} needs = true or = false.")
        value = value if op == "=" else not value
        if target == "archived":
            return Q(archived_at__isnull=not value)
        return Q(**{target: value})

    if kind == "str":
        allowed = PRIORITIES if target == "priority" else STATE_GROUPS
        if str(value) not in allowed:
            raise PQLError(f"{name!r} must be one of {sorted(allowed)}, got {value!r}.")
        q = Q(**{target: value})
        return ~q if op == "!=" else q

    if kind == "fk":
        q = Q(**{target: as_uuid(value)})
        return ~q if op == "!=" else q

    if kind == "m2m":
        q = m2m_q(*target, as_uuid(value))
        return ~q if op == "!=" else q

    # date / datetime
    if kind == "datetime" and isinstance(value, datetime):
        column, value = target, value
    else:
        column = f"{target}__date" if kind == "datetime" else target
        value = to_date(name, value)
    if op in ("=", "!="):
        q = Q(**{column: value})
        return ~q if op == "!=" else q
    return Q(**{f"{column}__{LOOKUPS[op]}": value})


def relation_q(name, target):
    rel = IssueRelation.objects.filter(deleted_at__isnull=True)
    if name == "childOf":
        return Q(parent_id=target.id)
    if name == "parentOf":
        return Q(id=target.parent_id) if target.parent_id else Q(pk__in=[])
    if name == "blockedBy":  # items that X blocks: rows (issue=I, related=X, blocked_by)
        return Q(id__in=rel.filter(related_issue=target, relation_type="blocked_by").values("issue_id"))
    if name == "blocks":  # items that block X: rows (issue=X, related=I, blocked_by)
        return Q(id__in=rel.filter(issue=target, relation_type="blocked_by").values("related_issue_id"))
    relation_type = "relates_to" if name == "linkedTo" else "duplicate"
    rows = rel.filter(relation_type=relation_type)
    return Q(id__in=rows.filter(issue=target).values("related_issue_id")) | Q(
        id__in=rows.filter(related_issue=target).values("issue_id")
    )


def parse_pql(text, user, workspace_slug, project_id=None):
    """Return a Q for the PQL text, or raise PQLError."""
    if len(text) > 2000:
        raise PQLError("PQL query is too long.")
    return Parser(text, Ctx(user, workspace_slug, project_id)).parse()
